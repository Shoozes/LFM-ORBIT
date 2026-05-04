"""Object count delta helpers for compact evidence packets."""

from __future__ import annotations

from core.contracts import DetectionSummary, ObjectDelta


def _counts(summary: DetectionSummary | dict | None) -> dict[str, int]:
    if not isinstance(summary, dict):
        return {}
    raw_counts = summary.get("counts_by_label")
    if not isinstance(raw_counts, dict):
        return {}
    counts: dict[str, int] = {}
    for label, value in raw_counts.items():
        text = str(label).strip()
        if not text:
            continue
        try:
            counts[text] = max(0, int(value))
        except (TypeError, ValueError):
            counts[text] = 0
    return counts


def _action_hint(baseline_count: int, current_count: int, delta_count: int) -> str:
    if current_count <= 0:
        return "discard"
    if baseline_count <= 0 and current_count > 0:
        return "defer"
    if delta_count >= 5 or delta_count / max(1, baseline_count) >= 0.5:
        return "downlink_now"
    if delta_count > 0:
        return "defer"
    return "discard"


def compute_object_deltas(
    baseline_summary: DetectionSummary | dict | None,
    current_summary: DetectionSummary | dict | None,
) -> list[ObjectDelta]:
    """Compare baseline/current detection summaries without inventing evidence."""
    baseline_counts = _counts(baseline_summary)
    current_counts = _counts(current_summary)
    labels = sorted(set(baseline_counts) | set(current_counts))
    deltas: list[ObjectDelta] = []
    for label in labels:
        baseline_count = baseline_counts.get(label, 0)
        current_count = current_counts.get(label, 0)
        delta_count = current_count - baseline_count
        if baseline_count > 0:
            delta_percent = (delta_count / baseline_count) * 100.0
        elif current_count > 0:
            delta_percent = 100.0
        else:
            delta_percent = 0.0
        deltas.append(
            {
                "label": label,
                "baseline_count": baseline_count,
                "current_count": current_count,
                "delta_count": delta_count,
                "delta_percent": round(delta_percent, 2),
                "action_hint": _action_hint(baseline_count, current_count, delta_count),  # type: ignore[typeddict-item]
            }
        )
    return deltas
