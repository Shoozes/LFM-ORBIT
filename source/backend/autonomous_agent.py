"""
autonomous_agent.py — Experimental standalone satellite agent.

STATUS: NOT PART OF THE MAIN RUN PATH.

This script was an early prototype for an autonomous timelapse-generation
loop that ran outside the main FastAPI process.  It is NOT imported or
started by the main application (api/main.py uses core/satellite_agent.py
and core/ground_agent.py instead).

Known issues that make it non-functional in the current repo:
  - Reads sentinel.txt as a plain instance_id (not KEY=VALUE format used
    by config.py's _parse_secrets_file).
  - References SAT_TIMELAPSE_DIR four levels up from the repo root —
    this external directory is not part of this repository.
  - Mutates the alerts DB schema directly (adds timelapse_generated column)
    outside of the queue.py migration path.

Kept for reference.  Do not run this file directly; the production satellite
agent is core/satellite_agent.py.
"""

import os
import time
import subprocess
import sqlite3
from core.grid import cell_to_boundary, cell_to_latlng
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "runtime-data" / "dtn_queue.sqlite"
SECRETS_PATH = Path(__file__).resolve().parents[3] / ".tools" / ".secrets" / "sentinel.txt"
TIMELAPSE_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public" / "timelapses"
SAT_TIMELAPSE_DIR = Path(__file__).resolve().parents[4] / "SatTimelapse"
VENV_PYTHON = SAT_TIMELAPSE_DIR / ".venv" / "Scripts" / "python.exe"
HEADLESS_SCRIPT = SAT_TIMELAPSE_DIR / "headless.py"

def get_db_connection():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def cell_to_bbox(cell_id):
    boundary = cell_to_boundary(cell_id)
    lats = [p[0] for p in boundary]
    lngs = [p[1] for p in boundary]
    buffer = 0.02
    return f"{min(lngs)-buffer},{min(lats)-buffer},{max(lngs)+buffer},{max(lats)+buffer}"

def run_agent():
    print("🚀 Satellite Autonomous Agent Booted.")
    print("Waiting for ground station to assign targets (alerts)...")
    
    if not SECRETS_PATH.exists():
        print("❌ Instance ID not found in .tools/.secrets/sentinel.txt")
        return

    instance_id = SECRETS_PATH.read_text().strip()
    TIMELAPSE_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            with get_db_connection() as conn:
                # Add timelapse_generated column if not exists
                columns = [col["name"] for col in conn.execute("PRAGMA table_info(alerts)").fetchall()]
                if "timelapse_generated" not in columns:
                    conn.execute("ALTER TABLE alerts ADD COLUMN timelapse_generated BOOLEAN DEFAULT 0")

                unprocessed = conn.execute(
                    "SELECT id, cell_id FROM alerts WHERE timelapse_generated = 0 AND change_score > 0.3 ORDER BY id DESC LIMIT 1"
                ).fetchone()

                if subprocess.call("exit 0", shell=True) != 0: pass # dummy

            if unprocessed:
                alert_id = unprocessed["id"]
                cell_id = unprocessed["cell_id"]
                print(f"\n🛰️ [Autonomous Agent] Commencing deep analysis on priority target: {cell_id}")
                
                outdir = TIMELAPSE_DIR / cell_id
                bbox = cell_to_bbox(cell_id)

                # Process the job
                print(f"📡 Executing SatTimelapse workflow...")
                result = subprocess.run(
                    [str(VENV_PYTHON), str(HEADLESS_SCRIPT), "--instance-id", instance_id, "--cell-id", cell_id, "--bbox", bbox, "--outdir", str(outdir)],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    print(f"✅ Decoding successful. Timelapse created for {cell_id}.")
                else:
                    print(f"⚠️ Decoding encountered errors. \n{result.stderr}")

                with get_db_connection() as conn:
                    conn.execute("UPDATE alerts SET timelapse_generated = 1 WHERE id = ?", (alert_id,))
                    conn.commit()
            
        except Exception as e:
            print(f"Agent error: {e}")
        
        time.sleep(5)

if __name__ == "__main__":
    run_agent()
