import os
import tracemalloc
import uvicorn
import logging
from core.observability import setup_production_logging

if __name__ == "__main__":
    # Ensure RUNTIME_ENV is edge by default if executed via this file
    os.environ["RUNTIME_ENV"] = os.environ.get("RUNTIME_ENV", "edge")
    os.environ["SIMSAT_ENABLED"] = os.environ.get("SIMSAT_ENABLED", "0")
    os.environ["EMIT_OBSERVABILITY_LOGS"] = "1"

    # Start tracemalloc for memory tracking during observability
    tracemalloc.start()

    # Setup structured JSON logging
    setup_production_logging()
    logger = logging.getLogger("orbit.edge")
    logger.info("Initializing Canonical Edge Deployment Scaffold")

    # Start Uvicorn headless natively
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info(f"Starting uvicorn on {host}:{port} in {os.environ['RUNTIME_ENV']} mode...")
    uvicorn.run("api.main:app", host=host, port=port, log_level="info")
