# LFM-ORBIT

LFM-ORBIT is a professional-product-style MVP for satellite evidence triage. It is not a production surveillance system; it is a reproducible mission-control prototype showing how local Liquid AI reasoning can reduce satellite downlink load, retain only useful evidence, and produce compact proof packets with provenance.

The product journey is simple: an operator selects a mission area, Orbit scans satellite tiles, low-value cells are pruned before downlink, retained evidence is reviewed by SAT/GND agents, and the final output is compact proof JSON with imagery provenance.

[Demo guide](docs/user/DEMO_GUIDE.md) | [Validation](#validation-snapshot) | [Release](https://github.com/Shoozes/LFM-ORBIT/releases/latest)

![What is LFM-ORBIT?](docs/media/infographics/what-is-lfm-orbit-info.png)

## Run The App

```powershell
.\run.ps1
```

Choose **1. Install/Repair + Fetch trained Orbit GGUF -> Run**.

Direct Windows command:

```powershell
.\run.ps1 -Install
```

Linux/macOS:

```bash
./run.sh --install
```

App: `http://127.0.0.1:5173`

The default hackathon path uses SimSat/Mapbox plus bundled cached replay proof. Sentinel Hub credentials are not required.

Option 1 reuses an existing valid trained GGUF after the first download. Set `LFM_ORBIT_REFRESH_MODEL=true` only when you intentionally want to refresh the moving Hugging Face `main` handoff.

## Reviewer Path

1. Open **Mission**.
2. Choose **Replay**.
3. Load **Critical Minerals Expansion Watch** or **Spain Larouco Wildfire Burn-Scar Replay**.
4. Review **Logs** and **Inspect** for the downlinked alert, retained timelapse, source metadata, and agent notes.
5. Open **Agent -> Proof Mode** for the compact proof JSON and visual evidence.

This is the intended judging path: one mission, one scan/proof story, and clear source/runtime boundaries. The supporting tabs and demos exist to prove the same product loop, not to broaden the claim.

## Record The Showcase

```bash
cd source/frontend
npm ci
npm run demo:showcase
```

The showcase loads deterministic Critical Minerals Expansion Watch replay evidence and writes video, screenshot, trace, and `proof.json` artifacts. No Sentinel Hub credentials are needed for the showcase path.

## Watch The Main Videos

The primary videos are linked instead of embedded because they are larger tutorial artifacts:

- [Tutorial walkthrough](docs/media/videos/tutorial_video.webm): plain-English product run-through from mission selection to scan, SAT/GND handoff, retained evidence, Proof Mode, compact JSON, and tagged data.
- [Training journey](docs/media/videos/training-journey.webm): shows how reviewed Orbit evidence becomes reusable training data.
- [Media index](docs/media/README.md): all promoted videos, screenshots, story plates, and timelapse highlights.

Full repo verification:

```powershell
.\run.ps1 -Verify
```

```bash
./run.sh --verify
```

## What It Proves

- Tile scan over selected area and time window.
- Dual-agent triage: satellite-side prune, ground-side review.
- Retained timelapse evidence with provenance.
- Optional LiquidAI/LFM2.5-VL-450M retained-frame review when the image runtime is enabled.
- Compact proof JSON instead of raw-image downlink.
- Saved and tagged evidence for export, retagging, tuning, replay, and cached-data rescan with newer prompts or models.

The hackathon artifact is treated like a product contract: install path, deterministic demo, source-backed evidence, proof output, and honest runtime boundaries.

## Proof Gallery

### 01. Critical Minerals Expansion Watch

![Critical minerals expansion evidence](docs/media/story-plates/story-critical-minerals-expansion.png)

Region-level mining expansion evidence with provenance, target-pack context, and compact proof output.

### 02. Payload Reduction

![Payload reduction proof](docs/media/readme/readme-payload-reduction.png)

Raw frame evidence is reduced to compact alert JSON before downlink.

### 03. Orbital Eclipse Queue

![Orbital eclipse proof](docs/media/readme/readme-orbital-eclipse.png)

Alerts queue during link loss and flush after contact returns.

### 04. Target-Pack Proof

![Port activity CV object evidence](docs/media/story-plates/story-object-evidence-port.png)

Target-pack metadata travels with alerts, replay snapshots, dataset rows, and Proof Mode.

### 05. Provenance And Audit

![Provenance proof](docs/media/readme/readme-provenance.png)

Each alert keeps provider, capture time, bbox, confidence, model metadata, and payload accounting attached.

### 06. Timelapse Context

![Greenland ice/snow Sentinel-2 timelapse](docs/media/timelapse/highlight-greenland-ice-timelapse.gif)

Timelapse review uses sequential imagery slices, not static color-shift videos.

### 07. Ground Operations

![Ground Agent operator playbook](docs/media/readme/readme-ground-agent-playbook.png)

Ground Agent handles replay loads, mission packs, link simulation, and operator review cards before state changes.

### 08. Semantic Location Context

![Ground Agent semantic location camera context](docs/media/readme/readme-location-camera-context.png)

Known map targets carry mission context and safe evidence guidance with the camera move.

## Validation Snapshot

| Check | Current State |
|---|---|
| Root verify | `.\run.ps1 -Verify` passing |
| Backend tests | `499 passed` |
| Frontend | typecheck + build passing |
| Playwright E2E | `104 passed`, `6 skipped` |
| Docs/import guards | passing |
| Option 1 launch | backend `8000` and app `5173` ready |
| Clean-start smoke | idle on Atacama context, no auto replay, no default scan |
| Recorded demos | showcase, payload, provenance, abstain, eclipse, tutorial |
| Dataset export | `46` raw replay/cache samples, `34` timelapse rows |
| Retagged training set | `265` assets, `33` temporal sequences |
| Dataset | [Shoozes/LFM-Orbit-SatData](https://huggingface.co/datasets/Shoozes/LFM-Orbit-SatData) |
| Trained model | [Shoozes/lfm2.5-450m-vl-orbit-satellite](https://huggingface.co/Shoozes/lfm2.5-450m-vl-orbit-satellite) |

## Model + Training Loop

LFM-ORBIT uses a manifest-resolved GGUF for SAT/GND evidence-packet reasoning. Optional retained-frame image review uses LiquidAI/LFM2.5-VL-450M through the backend `vision` extra when enabled.

The status APIs report `image_conditioned_runtime_enabled=true` only after a real image adapter call succeeds.

Orbit exports reviewed evidence for retagging and tuning. The updated model handoff can be fetched back into Orbit and used to replay or rescan prior sessions.

## Requirements

Python `3.10+` and Node.js `20.19.0` from `.nvmrc` or Node.js `22.12.0+`. The launchers bootstrap repo-local `uv` when it is not already installed.

## Docs

- [Demo Videos and Other Media](https://github.com/Shoozes/LFM-ORBIT/tree/main/docs/media)
- [Docs index](docs/README.md)
- [Demo guide](docs/user/DEMO_GUIDE.md)
- [Architecture](docs/dev/ARCHITECTURE.md)
- [Model handoff](docs/dev/MODEL_HANDOFF.md)
- [Dataset cycle](docs/dev/DATASET_CYCLE_TUTORIAL.md)
- [Current backlog](docs/dev/TODO.md)
