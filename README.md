# LFM-ORBIT

**Local-first satellite mission control for the Liquid AI x DPhi Space Hackathon: Hack #05, AI in Space.**

LFM-ORBIT turns satellite imagery into compact, evidence-backed orbital alerts. The satellite-side agent scans large areas, filters noisy scenes, invokes a local Liquid VLM path for the important frame, and downlinks compact proof JSON instead of raw imagery.

This is a demo-ready research prototype, not an unattended production deployment. Evidence surfaces keep `runtime_truth_mode`, `imagery_origin`, and `scoring_basis` separate so realtime imagery, cached API replay, and fallback paths are never confused.

[Hackathon event](https://luma.com/n9cw58h0) | [Judging criteria](docs/Liquid_AI_x_DPhi_Space_Judging_Criteria.md) | [Judge demo guide](docs/JUDGE_DEMO.md)

![LFM-ORBIT Judge Mode proof surface](docs/readme-judge-mode.png)

## Run The Judge Proof

```bash
cd source/frontend
npm ci
npm run demo:judge
```

This starts the app, loads a deterministic replay from cached real API imagery, runs the proof flow, and writes video, screenshot, trace, and `proof.json` artifacts. The proof uses saved replay assets, so the judge path does not need fresh provider API calls.

| Artifact | Path |
|---|---|
| Demo video | `docs/judge-mode-demo.webm` |
| Tutorial video | `docs/tutorial_video.webm` |
| Screenshot | `source/frontend/e2e/artifacts/judge-mode/final-screen.png` |
| Evidence frame | `source/frontend/e2e/artifacts/judge-mode/evidence-frame.png` |
| Proof JSON | `source/frontend/e2e/artifacts/judge-mode/proof.json` |

Run every recorded proof from `source/frontend`:

```bash
npm run demo:record
```

## Screenshots

<table>
  <tr>
    <td width="50%"><img src="docs/readme-payload-reduction.png" alt="Payload reduction proof with satellite frame, bbox, raw bytes, alert JSON bytes, and downlink reduction" /></td>
    <td width="50%"><img src="docs/readme-provenance.png" alt="Atacama provenance proof with provider, capture time, bbox, prompt, model, and output JSON" /></td>
  </tr>
  <tr>
    <td><strong>Payload reduction</strong><br />Raw imagery stays local; only compact alert JSON is downlinked.</td>
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

## What Judges Should Notice

| Area | What is shown |
|---|---|
| Space constraint | The edge agent compresses a raw satellite frame into a small alert payload before downlink. |
| Real imagery | Sentinel-2 L2A replay assets are cached from API imagery and keep date/provenance metadata. |
| Agent loop | Satellite Pruner Agent and Ground Validator Agent exchange visible SAT/GND mission context. |
| Evidence contract | Every alert separates truth mode, imagery origin, and scoring basis. |
| Show path | One command records a reproducible proof with video, screenshots, trace, and JSON. |

## Product Surface

- Mission Control map with bbox selection, Fast Replay load/rescan, and mission presets.
- SAT/GND agent dialogue with compact orbital telemetry and ground validation.
- Evidence gallery with imagery, timelapse, provenance, alert analysis, and VLM tools.
- Judge Mode proof panel with stable artifact export.
- Delay-tolerant link outage simulator.
- Dataset export, Qwen/Ollama retagging, replay-cache packaging, and Hugging Face upload tooling.

Current proof missions include deforestation, flood extent, mining expansion, maritime activity, wildfire candidates, urban expansion, volcano/lake events, and the new Greenland ice/snow extent lane.

## Ice/Snow Extent

The cryosphere lane is long-window ice and snow extent monitoring, not a visual-only ice-growth claim. It uses cached Sentinel-2 L2A replay metadata with:

- NDSI from Green and SWIR1 bands.
- SCL cloud, shadow, no-data, and snow/ice support.
- NDWI/SWIR water-ice ambiguity flags.
- Multi-frame persistence before any extent-change review label.
- Static-video rejection so color-shift-only clips are not treated as timelapse proof.

## Evidence Modes

| Field | Purpose |
|---|---|
| `runtime_truth_mode` | `realtime`, `replay`, `fallback`, or `unknown`. |
| `imagery_origin` | Provider/source family such as `sentinelhub`, `simsat`, `nasa_gibs`, `gee`, or `cached_api`. |
| `scoring_basis` | `multispectral_bands`, `proxy_bands`, `visual_only`, `fallback_none`, or `unknown`. |

Replay means stored real API imagery with preserved date/provenance for deterministic review and cost control. Fallback means degraded runtime behavior and must not be presented as realtime evidence.

## Validation

| Check | Result |
|---|---|
| Cold-start verification | `.\run.ps1 -Verify` passing |
| Backend tests | `299 passed` |
| Frontend lint/build | passing |
| Normal Playwright E2E | `73 passed`, `1 skipped` |
| Recorded demo suite | `5 passed` |
| Dataset export | `56` samples, `24` replay-cache rows |
| Retagged training export | `179` assets, `26` temporal sequences |
| Hugging Face dataset | [Shoozes/LFM-Orbit-SatData](https://huggingface.co/datasets/Shoozes/LFM-Orbit-SatData), including `mission_metadata=1` |

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
