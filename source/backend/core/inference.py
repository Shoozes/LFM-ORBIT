"""
inference.py -- Self-contained LFM inference engine for the satellite backend.

Loads LFM2.5-1.2B-Thinking-Q4_K_M.gguf from runtime-data/models/ via
llama-cpp-python. This is the satellite's own inference stack, independent
of the frontend wllama instance.

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
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

# Model path resolved relative to the repo root
_MODELS_DIR = Path(__file__).resolve().parents[3] / "runtime-data" / "models" / "lfm2.5-vlm-450m"
_MODEL_FILENAME = "LFM2.5-VL-450M-Q4_0.gguf"
_MODEL_PATH = _MODELS_DIR / _MODEL_FILENAME

# Generation defaults
_CTX_SIZE = 4096
_MAX_TOKENS = 512
_TEMPERATURE = 0.6
_TOP_P = 0.9

_model = None
_model_lock = threading.Lock()
_load_attempted = False


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
            if not _MODEL_PATH.exists():
                logger.warning("[INF] Model not found at %s -- satellite reasoning disabled", _MODEL_PATH)
                return None
            logger.info("[INF] Loading LFM model: %s", _MODEL_PATH.name)
            _model = Llama(
                model_path=str(_MODEL_PATH),
                n_ctx=_CTX_SIZE,
                n_threads=max(1, (os.cpu_count() or 4) - 1),
                verbose=False,
            )
            logger.info("[INF] LFM model loaded successfully.")
        except Exception as exc:
            logger.error("[INF] Failed to load LFM model: %s", exc)
            _model = None
    return _model


def model_status() -> dict:
    """Return load status for the debug dashboard."""
    global _load_attempted
    if _model is not None:
        return {"loaded": True, "path": str(_MODEL_PATH), "name": _MODEL_FILENAME}
    if not _MODEL_PATH.exists():
        return {"loaded": False, "reason": "model file not found", "path": str(_MODEL_PATH)}
    if _load_attempted:
        return {"loaded": False, "reason": "load failed", "path": str(_MODEL_PATH)}
    return {"loaded": False, "reason": "not yet attempted", "path": str(_MODEL_PATH)}


# ---------------------------------------------------------------------------
# Thinking-tag parser
# ---------------------------------------------------------------------------

_THINK_OPEN = re.compile(r"<think>", re.IGNORECASE)
_THINK_CLOSE = re.compile(r"</think>", re.IGNORECASE)
# Tool call: JSON block with a "tool" key
_TOOL_CALL_PATTERN = re.compile(
    r"```json\s*(\{.*?\})\s*```|(\{[^{}]*\"tool\"[^{}]*\})",
    re.DOTALL,
)


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
    for m in _TOOL_CALL_PATTERN.finditer(response_text):
        blob = m.group(1) or m.group(2)
        try:
            parsed = json.loads(blob)
            if isinstance(parsed, dict) and "tool" in parsed:
                tool_calls.append({
                    "name": parsed.get("tool", "unknown"),
                    "arguments": parsed.get("arguments", parsed),
                })
        except json.JSONDecodeError:
            pass

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
    Falls back to a stub response when the model is unavailable.
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
