import json
import logging
import os
import time
from contextlib import contextmanager
from threading import Lock
from typing import Any, Dict

logger = logging.getLogger("orbit.observability")
_THROTTLED_LOG_STATE: Dict[str, Dict[str, float]] = {}
_THROTTLED_LOG_LOCK = Lock()

def check_is_production() -> bool:
    env = os.getenv("RUNTIME_ENV", "local").lower()
    return env in ("edge", "staging")

def setup_production_logging():
    """Converts the root logger to output JSON lines for edge/staging environments."""
    if check_is_production():
        # Remove existing handlers
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        handler = logging.StreamHandler()

        # Simple JSON formatter
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": self.formatTime(record, self.datefmt),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                if hasattr(record, "run_id"):
                    log_data["run_id"] = record.run_id
                if hasattr(record, "metrics"):
                    log_data["metrics"] = record.metrics

                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_data)

        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
        root.setLevel(logging.INFO)


def reset_throttled_logs():
    with _THROTTLED_LOG_LOCK:
        _THROTTLED_LOG_STATE.clear()


def log_throttled(
    target_logger: logging.Logger,
    level: int,
    key: str,
    message: str,
    *args: Any,
    interval_seconds: float = 30.0,
    now: float | None = None,
) -> bool:
    current_time = time.monotonic() if now is None else now
    rendered = message % args if args else message

    with _THROTTLED_LOG_LOCK:
        state = _THROTTLED_LOG_STATE.get(key)
        if state and (current_time - state["last_emit"]) < interval_seconds:
            state["suppressed"] += 1
            return False

        suppressed = int(state["suppressed"]) if state else 0
        _THROTTLED_LOG_STATE[key] = {"last_emit": current_time, "suppressed": 0}

    if suppressed:
        rendered = f"{rendered} (suppressed {suppressed} similar events)"

    target_logger.log(level, rendered)
    return True

class RuntimeObserver:
    """Tracks latency, stage failures, memory constraints, and deterministic outputs for a single cell processing pass."""
    def __init__(self, run_id: str, cell_id: str):
        self.run_id = run_id
        self.cell_id = cell_id
        self.timings: Dict[str, float] = {}
        self.failures: Dict[str, str] = {}
        self._start_time = time.perf_counter()
        self.total_time = 0.0
        self.peak_memory_mb = 0.0
        self.is_rejected = False
        self.rejection_reason = ""
        self.attributes: Dict[str, Any] = {}

    @contextmanager
    def Stage(self, stage_name: str):
        """Context manager to trace latency and failures of a specific execution stage."""
        start = time.perf_counter()
        try:
            yield
        except Exception as e:
            self.failures[stage_name] = type(e).__name__
            raise
        finally:
            elapsed = time.perf_counter() - start
            self.timings[stage_name] = elapsed

    def reject(self, reason: str):
        self.is_rejected = True
        self.rejection_reason = reason

    def finalize(self):
        self.total_time = time.perf_counter() - self._start_time

        try:
            import tracemalloc
            if tracemalloc.is_tracing():
                _, peak = tracemalloc.get_traced_memory()
                self.peak_memory_mb = peak / (1024 * 1024)
        except Exception:
            logger.debug("Unable to collect tracemalloc peak memory.", exc_info=True)

        # In a real environment, we'd log this structurally.
        try:
            from core.metrics import record_observability_telemetry
            record_observability_telemetry(
                total_time_ms=self.total_time * 1000,
                peak_memory_mb=getattr(self, "peak_memory_mb", 0.0),
                is_rejected=self.is_rejected,
                failures=self.failures,
                stage_times=self.timings,
                rejection_reason=self.rejection_reason,
            )
        except Exception:
            logger.debug("Unable to persist observability telemetry.", exc_info=True)

        if check_is_production() or os.getenv("EMIT_OBSERVABILITY_LOGS") == "1":
            extra = {
                "run_id": self.run_id,
                "metrics": {
                    "cell_id": self.cell_id,
                    "total_time_ms": round(self.total_time * 1000, 3),
                    "timings": {k: round(v * 1000, 3) for k, v in self.timings.items()},
                    "failures": self.failures,
                    "is_rejected": self.is_rejected,
                    "rejection_reason": self.rejection_reason,
                    "peak_memory_mb": getattr(self, "peak_memory_mb", 0.0),
                    **self.attributes
                }
            }
            logger.info("Pass completed", extra=extra)
