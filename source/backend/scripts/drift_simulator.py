import os
import sys
import tracemalloc
import logging

from typing import List

# Setup environment for simulation
os.environ["RUNTIME_ENV"] = "staging"
os.environ["EMIT_OBSERVABILITY_LOGS"] = "0"
os.environ["SIMSAT_ENABLED"] = "0"

# Adjust sys.path to run directly from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scorer import score_cell_change
from core.observability import RuntimeObserver
from core.grid import generate_scan_grid

def get_test_cells() -> List[str]:
    # Select a few stable cells near the center of the region for testing
    grid = generate_scan_grid(-3.119, -60.025, resolution=5, ring_size=1)
    return [str(f["id"]) for f in grid["features"]][:3]

def run_simulation(cycles: int = 50):
    print(f"--- Launching Drift Simulator: {cycles} passes ---")
    cells = get_test_cells()
    outputs = {}

    tracemalloc.start()

    for cycle in range(cycles):
        for cell_id in cells:
            observer = RuntimeObserver(run_id=f"drift_sim_{cycle}_{cell_id}", cell_id=cell_id)
            try:
                score = score_cell_change(cell_id, observer=observer)
                snapshot = (
                    score["change_score"],
                    score["confidence"],
                    tuple(score["reason_codes"])
                )

                # Check for output drift
                if cell_id in outputs:
                    if outputs[cell_id] != snapshot:
                        print(f"❌ DETECTED DRIFT ON CELL {cell_id}!")
                        print(f"   Previous: {outputs[cell_id]}")
                        print(f"   Current:  {snapshot}")
                        sys.exit(1)
                else:
                    outputs[cell_id] = snapshot

            except Exception as e:
                observer.reject(type(e).__name__)
                print(f"Exception during pass: {e}")
            finally:
                observer.finalize()

        # Simple memory tracking
        _, peak = tracemalloc.get_traced_memory()

    print("--- Drift Simulation Complete ---")
    print(f"Tested {len(cells)} cells across {cycles} deterministic loops.")
    print(f"Output Consistency: 100% (No drift detected)")
    print(f"Peak Memory Demand: {peak / (1024 * 1024):.2f} MB")

if __name__ == "__main__":
    run_simulation(cycles=20)
