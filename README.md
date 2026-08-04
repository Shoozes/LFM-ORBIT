# LFM-ORBIT

LFM-ORBIT is a professional-product-style MVP for satellite evidence triage. It is not a production surveillance system; it is a reproducible mission-control prototype showing how local Liquid AI reasoning can reduce satellite downlink load, retain only useful evidence, and produce compact proof packets with provenance. GenUni is the separate training-cycle/producer repository; it is not the LFM-ORBIT application repository.

The product journey is simple: an operator selects a mission area, Orbit scans satellite tiles, low-value cells are pruned before downlink, retained evidence is reviewed by SAT/GND agents, and the final output is compact proof JSON with imagery provenance.

[Hosted browser demo](docs/user/HOSTED_DEMO.md) | [Demo guide](docs/user/DEMO_GUIDE.md) | [Validation](#validation-snapshot) | [LFM-ORBIT on GitHub](https://github.com/Shoozes/LFM-ORBIT) | [Repository boundary](docs/dev/REPOSITORY_BOUNDARY.md)

![What is LFM-ORBIT?](docs/media/infographics/what-is-lfm-orbit-info.png)

## Run The App

For the lightweight portfolio presentation, start the browser-only hosted route:

```powershell
.\run.ps1 -Hosted
```

```bash
./run.sh --hosted
```

Open `http://127.0.0.1:5173/hosted`. It loads a validated saved-package manifest and starts the pinned small browser-model fetch only when the visitor chooses it. The current browser path performs text reasoning over saved evidence; it is not image-conditioned VLM inference. It does not require the backend, provider credentials, or an Orbit API. See the [hosted demo handoff](docs/user/HOSTED_DEMO.md).

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

The default full-app path uses SimSat/Mapbox plus bundled cached replay proof. Sentinel Hub credentials are not required.

Option 1 reuses an existing valid trained GGUF after the first download. Set `LFM_ORBIT_REFRESH_MODEL=true` only when you intentionally want to refresh the moving Hugging Face `main` handoff.

## Mission Stories

Orbit is not a single canned demo. The app ships with several reviewable mission stories so an operator can pick the signal that best explains the product loop:

| Story | What To Look For | Best Use |
|---|---|---|
| Critical Minerals Expansion Watch | evaporation pond regions, tailings regions, open-pit expansion, roads, facility clusters | clearest main showcase and provenance proof |
| Deforestation / Rondonia Frontier | canopy-loss boundary, road-edge expansion, exposed soil, retained timelapse frames | end-to-end tutorial from chat-launched mission to proof JSON |
| Fire Watch / Wildfire | burn-scar, smoke/cloud ambiguity, fireline or readiness indicators | emergency-relevance story with cautious evidence wording |
| Flood / Waterline | new surface water, overflow regions, shoreline movement | payload-reduction and visible boundary-change story |
| Maritime Activity | vessel-queue or port activity regions, link outage queueing | orbital-eclipse and compact-packet queue proof |
| Glacier / Ice-Snow | snow/ice extent, spectral-confidence guardrails, sequential timelapse context | slower science-context and abstain-safety story |
| Urban / Lifeline / Transport | road corridors, facility regions, infrastructure context | secondary operator-planning and map-context stories |

The recommended public showcase is still **Critical Minerals Expansion Watch** because it is visually clear and source-bound. The other stories use the same app mechanics: select an area, scan or rescan cached evidence, let SAT/GND agents review retained packets, then open Proof Mode.

## Reviewer Path

1. Open **Mission**.
2. Choose **Replay**.
3. Load **Critical Minerals Expansion Watch** for the shortest proof path, or choose another mission story such as **Deforestation**, **Fire Watch**, **Flood**, **Maritime**, **Glacier**, or **Urban**.
4. Review **Logs** and **Inspect** for the downlinked alert, retained timelapse, source metadata, and agent notes.
5. Open **Agent -> Proof Mode** for the compact proof JSON and visual evidence.

For judging, one complete mission is enough. The extra stories are there to show the product is a reusable mission-control prototype, not a rigid one-off recording.

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

The portfolio artifact is treated like a product contract: install path, deterministic demo, source-backed evidence, proof output, and honest runtime boundaries.

## Proof Gallery

The four strongest surfaces are below. The [media index](docs/media/README.md) owns the full screenshot, story-plate, timelapse, and video inventory so this README stays focused on the product contract.

### Critical minerals and payload reduction

![Critical minerals expansion evidence](docs/media/story-plates/story-critical-minerals-expansion.png)

Region-level evidence keeps provenance and target-pack context attached while raw imagery is reduced to compact proof JSON.

![Payload reduction proof](docs/media/readme/readme-payload-reduction.png)

### Replay and target-pack proof

![Orbital eclipse proof](docs/media/readme/readme-orbital-eclipse.png)

Link loss queues compact alerts until contact returns. Target-pack metadata travels with replay snapshots, dataset rows, and Proof Mode.

![Port activity CV object evidence](docs/media/story-plates/story-object-evidence-port.png)

### Hosted boundary

The hosted route presents saved evidence packages without backend controls. Pages is intentionally saved-packages-only until the browser-model redistribution decision is complete; use the [hosted handoff](docs/user/HOSTED_DEMO.md) for deployment details.

## Validation Snapshot

The current local baseline has a locked backend suite (`561 passed`), `17` frontend unit tests, TypeScript/build checks, and a fail-closed Pages artifact. The required Playwright suite now excludes media production and release-only hosted/model specs; run it from `source/frontend` when browser dependencies are available. This managed desktop environment currently blocks Chromium launch with `spawn EPERM`, so no browser pass is claimed here.

```powershell
cd source/frontend
npm run lint
npm run test:unit
npm run build:pages
npm run test:e2e
```

The Pages workflow separately runs hosted smoke, deploys the model-free project-path artifact, and performs a live static-origin check. The current deployed HTTPS project path is [shoozes.github.io/LFM-ORBIT](https://shoozes.github.io/LFM-ORBIT/); model licensing and iOS Safari model proof remain external release gates in [TODO.md](docs/dev/TODO.md).

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
