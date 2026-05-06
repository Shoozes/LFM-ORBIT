# LFM-ORBIT

LFM-ORBIT scans selected Earth areas tile-by-tile across a chosen time frame, looking for configured concerns such as wildfire evidence, mineral expansion, biomass loss, flooding, maritime activity, and other Earth-observation targets.

It uses real satellite/timelapse evidence when configured, prunes low-value cells before downlink, reviews retained evidence with dual agents, and packages findings into compact proof JSON.

[Demo guide](docs/user/DEMO_GUIDE.md) | [Validation](#validation-snapshot) | [Release](https://github.com/Shoozes/LFM-ORBIT/releases/latest)

![What is LFM-ORBIT?](docs/media/infographics/what-is-lfm-orbit-info.png)

## Run The Showcase

```bash
cd source/frontend
npm ci
npm run demo:showcase
```

The showcase loads deterministic Critical Minerals Expansion Watch replay evidence and writes video, screenshot, trace, and `proof.json` artifacts. No Sentinel Hub credentials are needed for the showcase path.

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
- Saved and tagged evidence for export, retagging, tuning, replay, and rescan.

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
| Backend tests | `480 passed` |
| Frontend | typecheck + build passing |
| Playwright E2E | `101 passed`, `6 skipped` |
| Docs/import guards | `22 passed` |
| Clean-start smoke | idle on Atacama context, no auto replay, no default scan |
| Recorded demos | showcase, payload, provenance, abstain, eclipse, tutorial |
| Dataset export | `33` raw replay/cache samples, `26` timelapse rows |
| Retagged training set | `179` assets, `26` temporal sequences |
| Dataset | [Shoozes/LFM-Orbit-SatData](https://huggingface.co/datasets/Shoozes/LFM-Orbit-SatData) |
| Trained model | [Shoozes/lfm2.5-450m-vl-orbit-satellite](https://huggingface.co/Shoozes/lfm2.5-450m-vl-orbit-satellite) |

## Model + Training Loop

LFM-ORBIT uses a manifest-resolved GGUF for SAT/GND evidence-packet reasoning. Optional retained-frame image review uses LiquidAI/LFM2.5-VL-450M through the backend `vision` extra when enabled.

```powershell
.\run.ps1 -Install
```

```bash
./run.sh --install
```

Enable visual review:

```powershell
$env:LFM_ORBIT_INSTALL_IMAGE_RUNTIME="true"
$env:ORBIT_IMAGE_CONDITIONED_INFERENCE="true"
$env:ORBIT_IMAGE_INFERENCE_BACKEND="transformers_vlm"
$env:ORBIT_IMAGE_VLM_MODEL="LiquidAI/LFM2.5-VL-450M"
.\run.ps1 -Install
```

The status APIs report `image_conditioned_runtime_enabled=true` only after a real image adapter call succeeds.

Orbit exports reviewed evidence for retagging and tuning. The updated model handoff can be fetched back into Orbit and used to replay or rescan prior sessions.

## Run Locally

```powershell
.\run.ps1 -Install
```

```bash
./run.sh --install
```

App: `http://127.0.0.1:5173`

API: `http://127.0.0.1:8000`

Prerequisites are Python `3.10+` and Node.js `20.19.0` from `.nvmrc` or Node.js `22.12.0+`. The launchers bootstrap repo-local `uv` when it is not already installed.

## Limits

- Demo-ready research prototype, not unattended production autonomy.
- DPhi SimSat scoring is labeled `proxy_bands`.
- Replay fixtures are deterministic review assets, not live scans.
- Fallback paths stay labeled as fallback and must not become high-confidence detections.
- Image-conditioned review is claimed only when the image runtime reports enabled.

## Docs

- [Docs index](docs/README.md)
- [Demo guide](docs/user/DEMO_GUIDE.md)
- [Architecture](docs/dev/ARCHITECTURE.md)
- [Model handoff](docs/dev/MODEL_HANDOFF.md)
- [Dataset cycle](docs/dev/DATASET_CYCLE_TUTORIAL.md)
- [Current backlog](docs/dev/TODO.md)
