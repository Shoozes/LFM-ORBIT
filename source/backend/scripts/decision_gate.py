import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.metrics import read_metrics_summary


def _counter_total(counter: dict) -> int:
    return sum(int(value) for value in counter.values())


def _sorted_counter(counter: dict) -> list[tuple[str, int]]:
    return sorted(
        ((str(key), int(value)) for key, value in counter.items()),
        key=lambda item: (-item[1], item[0]),
    )


def _format_reason(reason: str) -> str:
    return reason.replace("_", " ")


def generate_decision_gate():
    state = read_metrics_summary()

    print("========================================")
    print(" LFM ORBIT : PIPELINE DECISION GATE     ")
    print("========================================")

    scans = state.get("total_cells_scanned", 0)
    rejection_rate = state.get("pct_scenes_rejected", 0.0)
    low_coverage_rate = state.get("pct_low_valid_coverage", 0.0)
    latency = state.get("average_inference_latency_ms", 0.0)
    memory = state.get("peak_memory_mb", 0.0)
    failures = state.get("runtime_failures_by_stage", {})
    rejection_reasons = state.get("runtime_rejections_by_reason", {})

    measurement_valid = (
        scans > 10 and
        rejection_rate > 0.0 and
        latency > 0.0 and
        memory > 0.0
    )

    print(f"Total Scans Performed:       {scans}")
    print(f"Scene Rejection Rate (QC):   {rejection_rate * 100:.1f}%")
    print(f"Low Valid Coverage Rate:     {low_coverage_rate * 100:.1f}%")
    print(f"Avg Stage Latency:           {latency:.2f} ms")
    print(f"Peak Memory Demand (Stage):  {memory:.2f} MB")
    print("\n--- FAULT ANALYSIS ---")
    if not failures:
        print("  All stages stable. No runtime exceptions.")
    else:
        for stage, count in failures.items():
            print(f"  {stage}: {count} failures")

    print("\n--- QC REJECTION BREAKDOWN ---")
    if not rejection_reasons:
        print("  No runtime scene rejects recorded.")
    else:
        total_rejections = max(1, _counter_total(rejection_reasons))
        for reason, count in _sorted_counter(rejection_reasons):
            pct = (count / total_rejections) * 100
            print(f"  {_format_reason(reason)}: {count} ({pct:.1f}%)")

    print("\n--- ROADMAP RECOMMENDATION ---")

    if not measurement_valid:
        print("STATUS: OBSERVABILITY DEFEATED")
        print("RECOMMENDATION: continue hardening current stack")
        print("REASON: The telemetry counters reflect impossible physical metrics (0 latency/0 rejection). Check instrumentation.")
    elif failure_count(failures) > 0:
        print("STATUS: PIPELINE UNSTABLE")
        print("RECOMMENDATION: continue hardening current stack")
        print("REASON: Address stage failures before expanding capability.")
    elif latency > 1500 or memory > 800:
        print("STATUS: RESOURCES CONSTRAINED")
        print("RECOMMENDATION: continue hardening current stack")
        print("REASON: Edge hardware thermal limits approached. Optimize inference latency and memory ceiling.")
    elif rejection_rate > 0.40 and low_coverage_rate > 0.25:
        print("STATUS: OPTICAL PIPELINE BLOCKED BY CLOUDS")
        print("RECOMMENDATION: proceed to SAR")
        print("REASON: Substantial low-valid-coverage dropout requires radar-based bypass.")
    elif rejection_rate > 0.40:
        print("STATUS: OPTICAL PIPELINE REJECTION RATE HIGH")
        print("RECOMMENDATION: tune provider/QC filters before adding new capability")
        print("REASON: Rejections are high, but low-valid-coverage is not the dominant measured blocker.")
    else:
        print("STATUS: OPTICAL PIPELINE STABLE")
        print("RECOMMENDATION: proceed to concession overlays")
        print("REASON: High scene validity and stable runtime means focus can shift to land-rights attribution.")

def failure_count(f: dict) -> int:
    return sum(f.values())

if __name__ == "__main__":
    generate_decision_gate()
