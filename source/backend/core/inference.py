"""
inference.py -- Self-contained LFM inference engine for the satellite backend.

Loads the configured GGUF artifact from runtime-data/models/ via
llama-cpp-python. This is the satellite's own inference stack, independent
of the frontend runtime.

Provides:
  - Lazy singleton model load (first call triggers load)
  - Streaming token generation with thinking-tag parsing
  - Tool-call extraction from model output
  - Thread-safe synchronous API (async wrappers in satellite_agent use run_in_executor)
"""

import json
import logging
import os
import re
import threading
from typing import Iterator

from core.model_manifest import resolve_satellite_model_artifact

logger = logging.getLogger(__name__)

# Generation defaults
_CTX_SIZE = 4096
_MAX_TOKENS = 512
_TEMPERATURE = 0.6
_TOP_P = 0.9

_model = None
_model_lock = threading.Lock()
_load_attempted = False


def _llama_init_kwargs(model_path: str) -> dict:
    chat_format = os.getenv("CANOPY_SENTINEL_LLAMACPP_CHAT_FORMAT", "chatml").strip() or "chatml"
    return {
        "model_path": model_path,
        "n_ctx": _CTX_SIZE,
        "n_threads": max(1, (os.cpu_count() or 4) - 1),
        "chat_format": chat_format,
        "verbose": False,
    }


def _should_patch_llama_chat_templates() -> bool:
    raw = os.getenv("CANOPY_SENTINEL_LLAMACPP_PATCH_CHAT_TEMPLATE", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _load_llama_model(llama_cls, kwargs: dict):
    if not _should_patch_llama_chat_templates():
        return llama_cls(**kwargs)

    import llama_cpp.llama_chat_format as chat_format_module

    original_formatter = chat_format_module.Jinja2ChatFormatter
    fallback_format = str(kwargs.get("chat_format") or "chatml")

    class _OrbitSafeJinjaFormatter:
        def __init__(self, *args, **kwargs):
            pass

        def to_chat_handler(self):
            return chat_format_module.get_chat_completion_handler(fallback_format)

    chat_format_module.Jinja2ChatFormatter = _OrbitSafeJinjaFormatter
    try:
        return llama_cls(**kwargs)
    finally:
        chat_format_module.Jinja2ChatFormatter = original_formatter


def _get_model():
    global _model, _load_attempted
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        if _load_attempted:
            return None
        _load_attempted = True
        try:
            from llama_cpp import Llama
            artifact = resolve_satellite_model_artifact()
            if not artifact.model_path.exists():
                logger.warning(
                    "[INF] Model not found at %s -- satellite reasoning disabled",
                    artifact.model_path,
                )
                return None
            logger.info("[INF] Loading LFM model: %s", artifact.model_path.name)
            _model = _load_llama_model(Llama, _llama_init_kwargs(str(artifact.model_path)))
            logger.info("[INF] LFM model loaded successfully.")
        except Exception as exc:
            logger.error("[INF] Failed to load LFM model: %s", exc)
            _model = None
    return _model


def model_status() -> dict:
    """Return load status for the debug dashboard."""
    global _load_attempted
    artifact = resolve_satellite_model_artifact()
    payload = artifact.to_status_dict()
    payload["name"] = artifact.model_filename
    payload["path"] = str(artifact.model_path)
    if _model is not None:
        payload["loaded"] = True
        return payload
    if not artifact.model_path.exists():
        payload["loaded"] = False
        payload["reason"] = "model file not found"
        return payload
    if _load_attempted:
        payload["loaded"] = False
        payload["reason"] = "load failed"
        return payload
    payload["loaded"] = False
    payload["reason"] = "not yet attempted"
    return payload


# ---------------------------------------------------------------------------
# Thinking-tag parser
# ---------------------------------------------------------------------------

_THINK_OPEN = re.compile(r"<think>", re.IGNORECASE)
_THINK_CLOSE = re.compile(r"</think>", re.IGNORECASE)
# Tool calls can appear as fenced JSON blocks with nested arguments or as
# simple inline JSON objects. Keep the fallback intentionally conservative.
_FENCED_JSON_PATTERN = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_INLINE_TOOL_PATTERN = re.compile(r"(\{[^{}]*\"tool\"[^{}]*\})", re.DOTALL)


def _iter_tool_json_blobs(response_text: str) -> Iterator[str]:
    seen: set[str] = set()
    for match in _FENCED_JSON_PATTERN.finditer(response_text):
        blob = match.group(1).strip()
        if blob and blob not in seen:
            seen.add(blob)
            yield blob

    without_fenced_blocks = _FENCED_JSON_PATTERN.sub("", response_text)
    for match in _INLINE_TOOL_PATTERN.finditer(without_fenced_blocks):
        blob = match.group(1).strip()
        if blob and blob not in seen:
            seen.add(blob)
            yield blob


def parse_output(raw: str) -> dict:
    """
    Parse raw model output into structured fields:
      thinking: text inside <think>...</think>
      response: text outside think tags (stripped)
      tool_calls: list of dicts extracted from JSON blocks
    """
    thinking_parts = []
    response_parts = []

    remainder = raw
    while True:
        m_open = _THINK_OPEN.search(remainder)
        if not m_open:
            response_parts.append(remainder)
            break
        response_parts.append(remainder[: m_open.start()])
        after_open = remainder[m_open.end():]
        m_close = _THINK_CLOSE.search(after_open)
        if m_close:
            thinking_parts.append(after_open[: m_close.start()].strip())
            remainder = after_open[m_close.end():]
        else:
            thinking_parts.append(after_open.strip())
            break

    thinking = "\n\n".join(t for t in thinking_parts if t)
    response_text = " ".join(r.strip() for r in response_parts if r.strip())

    tool_calls = []
    for blob in _iter_tool_json_blobs(response_text):
        try:
            parsed = json.loads(blob)
            if isinstance(parsed, dict) and "tool" in parsed:
                tool_calls.append({
                    "name": parsed.get("tool", "unknown"),
                    "arguments": parsed.get("arguments", parsed),
                })
        except json.JSONDecodeError:
            logger.debug("Ignoring malformed tool-call JSON: %s", blob[:120], exc_info=True)

    return {
        "thinking": thinking,
        "response": response_text,
        "tool_calls": tool_calls,
        "raw": raw,
    }


# ---------------------------------------------------------------------------
# Streaming generator
# ---------------------------------------------------------------------------

def stream_tokens(prompt: str, max_tokens: int = _MAX_TOKENS) -> Iterator[str]:
    """
    Yield raw tokens from the model one at a time.
    Returns empty iterator if the model is not available.
    """
    model = _get_model()
    if model is None:
        return

    try:
        messages = [
            {"role": "user", "content": prompt}
        ]
        stream = model.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=_TEMPERATURE,
            top_p=_TOP_P,
            stream=True,
        )
        for chunk in stream:
            if "content" in chunk["choices"][0]["delta"]:
                token = chunk["choices"][0]["delta"]["content"]
                if token:
                    yield token
    except Exception as exc:
        logger.error("[INF] Stream error: %s", exc)


def generate(prompt: str, max_tokens: int = _MAX_TOKENS) -> dict:
    """
    Blocking generation. Returns parsed output dict.
    Falls back to a deterministic status response when the model is unavailable.
    """
    model = _get_model()
    if model is None:
        return {
            "thinking": "",
            "response": "[LFM model not loaded -- spectral signal analysis only]",
            "tool_calls": [],
            "raw": "",
        }

    try:
        # Wrap the legacy flat prompt string into a chat context
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        result = model.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=_TEMPERATURE,
            top_p=_TOP_P,
        )
        raw = result["choices"][0]["message"]["content"]
        return parse_output(raw)
    except Exception as exc:
        logger.error("[INF] Generate error: %s", exc)
        return {
            "thinking": "",
            "response": f"[Inference error: {exc}]",
            "tool_calls": [],
            "raw": "",
        }


# ---------------------------------------------------------------------------
# Satellite-specific prompt builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an orbital satellite agent performing autonomous spectral triage. "
    "Scan H3 grid cells for deforestation signals using change scores and confidence bounds. "
    "IMPORTANT: Differentiate between true deforestation (structural decay, loss of primary canopy, long-term degradation) "
    "vs seasonal changes (brown-out, leaf-off winter seasons, phenology shifts). Do not trigger alerts for normal seasonal variations. "
    "If the change appears seasonal, use the discard_cell tool or explicitly output 'discard' and 'seasonal'. "
    "When you detect an true anomaly, reason carefully, then decide: flag for ground validation, "
    "call a tool, or discard. "
    "Available tools: flag_cell(cell_id, severity), request_imagery(cell_id), discard_cell(cell_id, reason). "
    "Format tool calls as JSON: {\"tool\": \"<name>\", \"arguments\": {...}}. "
    "Think step by step inside <think>...</think> tags before responding. Be concise."
)


def build_satellite_prompt(cell_id: str, score: dict) -> str:
    reason_str = ", ".join(score.get("reason_codes", [])) or "none"
    analysis = score.get("timelapse_analysis", "")
    analysis_block = f"  timelapse_analysis: {analysis}\n" if analysis else ""
    return (
        f"[SYSTEM] {_SYSTEM_PROMPT}\n\n"
        f"[OBSERVATION] Cell {cell_id}\n"
        f"  change_score: {score.get('change_score', 0):.4f}\n"
        f"  confidence:   {score.get('confidence', 0):.4f}\n"
        f"  reason_codes: {reason_str}\n"
        f"  source:       {score.get('observation_source', 'unknown')}\n"
        f"{analysis_block}\n"
        f"[TASK] Triage this cell. Reason in <think> tags, then issue your decision.\n"
        f"[RESPONSE]"
    )
