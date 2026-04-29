# LFM-ORBIT

**Local-first satellite mission control for the Liquid AI x DPhi Space Hackathon: Hack #05, AI in Space.**

LFM-ORBIT turns satellite imagery into compact, evidence-backed orbital alerts. The edge agent scans too much data, ignores low-value noise, asks a Liquid VLM to inspect the important frame, and downlinks proof JSON instead of raw imagery.

It is demo-ready and research-oriented, not an unattended production deployment. Runtime surfaces expose `runtime_truth_mode`, `imagery_origin`, and `scoring_basis` so realtime provider imagery, replayed cached API imagery, and fallback paths stay distinguishable.

[Hackathon event](https://luma.com/n9cw58h0) | [Judging criteria](docs/Liquid_AI_x_DPhi_Space_Judging_Criteria.md) | [Judge demo guide](docs/JUDGE_DEMO.md)

![LFM-ORBIT Judge Mode proof surface](docs/readme-judge-mode.png)

## Run The Proof

```bash
cd source/frontend
npm install
npm run demo:judge
```

That command launches the app, loads a deterministic replay from cached real API imagery, runs the VLM proof flow, and writes screenshot, video, trace, and `proof.json` artifacts.

| Artifact | Path |
|---|---|
| Demo video | `docs/judge-mode-demo.webm` |
| Tutorial video | `docs/tutorial_video.webm` |
| Screenshot | `source/frontend/e2e/artifacts/judge-mode/final-screen.png` |
| Evidence frame | `source/frontend/e2e/artifacts/judge-mode/evidence-frame.png` |
| Proof JSON | `source/frontend/e2e/artifacts/judge-mode/proof.json` |

Run every recorded proof:

```bash
npm run demo:record
```

## What It Shows

<table>
  <tr>
    <td width="50%"><img src="docs/readme-payload-reduction.png" alt="Payload reduction proof with satellite frame, bbox, raw bytes, alert JSON bytes, and downlink reduction" /></td>
    <td width="50%"><img src="docs/readme-provenance.png" alt="Atacama provenance proof with provider, capture time, bbox, prompt, model, and output JSON" /></td>
  </tr>
  <tr>
    <td><strong>Payload reduction</strong><br />Raw satellite frame stays local; compact alert JSON is downlinked.</td>
    <td><strong>Provenance chain</strong><br />Provider, capture time, bbox, prompt, model, confidence, and JSON stay attached.</td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/readme-orbital-eclipse.png" alt="Orbital eclipse proof with maritime satellite frame, offline link state, queued alerts, and restore flow" /></td>
    <td width="50%"><img src="docs/readme-visual-grid.png" alt="Four-panel visual grid of Judge Mode, payload reduction, provenance, and orbital eclipse demos" /></td>
  </tr>
  <tr>
    <td><strong>Delay-tolerant downlink</strong><br />Alerts queue while the link is offline, then flush after restore.</td>
    <td><strong>Replay proof pack</strong><br />Recorded app flows with real satellite evidence, not static mockups.</td>
  </tr>
</table>

## Why It Fits

| Criterion | Evidence |
|---|---|
| Satellite imagery | Real Sentinel-2 L2A replay assets cached from API imagery, plus provider lanes for SimSat, Sentinel Hub, NASA, and GEE-style flows. |
| Innovation | The app attacks the core space constraint: satellites cannot downlink everything, so the edge agent triages before transmission. |
| Implementation | FastAPI backend, React/Vite frontend, SQLite runtime stores, autonomous SAT/GND agents, telemetry WebSockets, replay loading, tests, and CI-ready checks. |
| Communication | One command records a self-contained judge proof with video, screenshots, trace, and proof JSON. |

## Product Surface

- Mission Control map with bbox selection, Fast Replay load/rescan, and location presets.
- Satellite Pruner Agent and Ground Validator Agent with visible SAT/GND dialogue.
- Evidence gallery with imagery, timelapse, provenance, alert analysis, and VLM tools.
- Judge Mode proof panel with stable artifact export.
- Delay-tolerant link outage simulator.
- Dataset export, Qwen/Ollama retagging, replay-cache packaging, and Hugging Face upload tooling.

Current proof missions include Rondonia deforestation, Pakistan Manchar Lake flooding, Atacama mining, Greenland abstain safety, Suez maritime outage, Singapore maritime replay, Georgia wildfire candidate, Mauna Loa, Lake Urmia, Black Rock City, Lahaina, Kakhovka, Kilauea, and Lake Mead.

## Evidence Modes

| Field | Values |
|---|---|
| `runtime_truth_mode` | `realtime`, `replay`, `fallback`, `unknown` |
| `imagery_origin` | `sentinelhub`, `simsat`, `nasa_gibs`, `gee`, `cached_api`, `fallback_none`, etc. |
| `scoring_basis` | `multispectral_bands`, `proxy_bands`, `visual_only`, `fallback_none`, `unknown` |

Replay means stored real API imagery with preserved date/provenance for deterministic review and cost control. Fallback means degraded runtime behavior such as provider error, quality gate, heuristic response, or VLM compatibility fallback.

## Validation

| Check | Result |
|---|---|
| Backend tests | `289 passed` |
| Frontend lint | passing |
| Frontend build | passing |
| Normal Playwright E2E | `73 passed`, `1 skipped` |
| Recorded demo suite | `5 passed` |
| Dataset export | `56` samples, `24` replay-cache rows |
| Retagged training export | `179` assets, `26` temporal sequences |
| Hugging Face dataset | [Shoozes/LFM-Orbit-SatData](https://huggingface.co/datasets/Shoozes/LFM-Orbit-SatData) |

## Run Locally

```powershell
.\run.ps1 -Install
.\run.ps1 -Run
```

The app starts at `http://127.0.0.1:5173`; the API starts at `http://127.0.0.1:8000`.

Useful checks:

```powershell
.\run.ps1 -Verify
```

```bash
./run.sh --run
./run.sh --verify
```

## Docs

| Doc | Purpose |
|---|---|
| [docs/JUDGE_DEMO.md](docs/JUDGE_DEMO.md) | Demo commands, artifacts, and replay assets |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Runtime map and design notes |
| [docs/TODO.md](docs/TODO.md) | Active backlog and edge-case watchlist |
| [docs/DATASET_CYCLE_TUTORIAL.md](docs/DATASET_CYCLE_TUTORIAL.md) | Seed, export, Qwen retag, and Hugging Face cycle |
| [docs/MODEL_HANDOFF.md](docs/MODEL_HANDOFF.md) | Model bundle and dataset handoff contract |
