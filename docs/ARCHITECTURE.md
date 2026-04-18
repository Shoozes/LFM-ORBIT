# LFM Orbit Architecture

## Overview
LFM Orbit (Canopy Sentinel) is a dual-stack web application for satellite telemetry and spatial deforestation triage. It is designed to install once online and run fully offline thereafter. No external AI API is required at runtime.

## Stack
- **Frontend:** Vite + React + TypeScript + Vanilla CSS. Contains mapping visualization (`MapVisualizer.tsx`), timeline viewer (`TimelapseViewer.tsx`), and a telemetry-bound mission control UI (`MissionControl.tsx`).
- **Backend:** Python + FastAPI + Uvicorn. Located in `source/backend/`. Handles spatial queries, caching, and local model inference.
- **Testing:** Playwright for E2E user flows (`npm run test:e2e`). Pytest for backend logic (`python -m pytest`).

## Directory Structure
- `source/frontend/`: React single-page app.
- `source/backend/`: FastAPI Python backend.
- `runtime-data/models/`: Local model weights fetched at install time. `runtime-data/models/lfm2.5-vlm-450m/LFM2.5-VL-450M-Q4_0.gguf` is the expected path.
- `docs/`: Project documentation and TODO tracking logs.
- `runtime-data/`: Local SQLite or cached states for development runs.
- `.tools/`: Agent generation, LLM context tools, and PowerShell helpers.

## Install vs. Runtime Networking

| Phase | Internet Required |
|---|---|
| Install (first-time) | Yes — downloads model weights and vendors SimSat |
| Runtime (all subsequent runs) | No — fully local/offline |

## Local Model & Inference

The system uses two inference paths, both fully offline:

- **Satellite Inference Engine:** `llama-cpp-python` with `LFM2.5-VL-450M-Q4_0.gguf`. Loaded at startup from `runtime-data/models/lfm2.5-vlm-450m/`. Used by the satellite agent for live orbital triage reasoning. Reports load status at `/api/analysis/status` via `satellite_inference_loaded`.
- **Ground Analysis Engine (`offline_lfm_v1`):** Deterministic signal analyzer using spectral band deltas (NDVI, NIR, NBR). Always available, CPU-only, requires no model file. Used by `core/analyzer.py` for all ground-side alert analysis.

Model readiness is checked at startup by `core/inference.py`. A missing or incomplete model file disables satellite reasoning but does not block ground analysis.

## Satellite Provider Pipeline

Providers are **imagery/data sources**, not AI dependencies. The fallback chain is:

1. **SimSat** (`simsat_sentinel`) — official hackathon satellite API provider.
2. **Sentinel Hub** (`sentinelhub_direct`) — direct WMS access; requires credentials.
3. **NASA GIBS** (`nasa_api_direct`) — HLS 30m / MODIS 250m; public API with rate limits.

When offline, all provider tiers degrade cleanly and the system falls back to edge-cached (semi-real) observations. Provider availability is reported separately from model availability at `/api/provider/status`.

## Dual-Agent System

- **Satellite Agent (Edge):** Runs autonomously simulating low-power orbital hardware (`core/satellite_agent.py`). Monitors spectral deltas, triggers local LFM inference, and downlinks compressed JSON flags (~15 bytes).
- **Ground Agent (Surface):** Validates flags (`core/ground_agent.py`, `core/analyzer.py`). Runs fully offline using `offline_lfm_v1`. Capable of processing timelapse evidence.

## Dependencies
- `llama-cpp-python` — local GGUF inference.
- `sentinelhub` — Sentinel Hub SDK (imagery source, optional).
- `httpx` — HTTP client for SimSat and ESRI imagery.
- `imageio`, `av` — timelapse video generation.
- `h3` — spatial hex grid.
- `fastapi`, `uvicorn` — backend API server.