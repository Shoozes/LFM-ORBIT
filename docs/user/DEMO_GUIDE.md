# Hackathon Demo

This is the recorded showcase path for the Liquid AI x DPhi Space Hackathon submission.

Frame the product as one clear operator journey: select a mission area, scan satellite tiles, prune low-value cells before downlink, review retained evidence with SAT/GND agents, and produce compact proof JSON with imagery provenance. Avoid showing the whole app in the main cut; every visible screen should support that path.

The hackathon satellite-data API target is SimSat/Mapbox through DPhi Space SimSat. The default lane is SimSat Sentinel, with SimSat Mapbox available as the optional imagery/context lane when a Mapbox token is configured. The recorded showcase does not require Sentinel Hub credentials; bundled replay fixtures and SimSat/Mapbox runtime defaults keep the demo deterministic and quota-free. Sentinel Hub is used only for development real-data seeding and cached replay refreshes, not as the default hackathon provider.

Normal app startup is intentionally idle. It opens on the Atacama mining context so the strongest story is ready to inspect, but it does not auto-play the last replay, launch a mission, or begin scanning until the operator confirms a mission proposal.

Run the main recorded showcase:

```bash
cd source/frontend
npm ci
npm run demo:showcase
```

Refresh the visual use-case proof grid:

```bash
cd ../backend
python scripts/build_visual_story_proofs.py --force-fetch
```

Run the live-app visual story guard:

```bash
cd ../frontend
npx playwright test e2e/visual-stories.spec.ts
```

What it proves:

1. Critical Minerals Expansion Watch as the main product story
2. Deterministic satellite replay
3. Edge triage
4. Liquid evidence reasoning over retained packets
5. Payload reduction
6. Provenance
7. Screenshot, video, and proof JSON artifacts
8. Tutorial-style subtitles and visible UI flow before the proof panel
9. Abstain and backend-derived link-outage queue behavior in the full demo set
10. Target-pack proof metadata attached to alerts, replays, datasets, and Proof Mode without a separate Mission-tab evidence workspace
11. Optional retained-frame image-conditioned review when the LiquidAI/LFM2.5-VL-450M Transformers runtime is installed and enabled

Main media checklist:

1. Product name and one-line value proposition
2. Mission selection
3. Scan/progress moment
4. Retained evidence or timelapse moment
5. Payload-reduction and proof JSON moment
6. Replay/live/source-mode boundary
7. Closing frame: local-first, reproducible, compact satellite proof

Artifacts:

```txt
source/frontend/e2e/artifacts/showcase/final-screen.png
source/frontend/e2e/artifacts/showcase/evidence-frame.png
source/frontend/e2e/artifacts/showcase/video.webm
source/frontend/e2e/artifacts/showcase/proof.json
docs/media/videos/showcase-demo.webm
```

Payload accounting: `raw_payload_bytes` represents the local satellite frame payload. `alert_payload_bytes` represents the compact alert JSON that would be downlinked. The larger proof artifact envelope, screenshots, video, trace, and UI-only audit fields are intentionally excluded and are listed in `proof.json` under `payload_accounting.excluded_from_alert_payload_bytes`.

Use all recorded demos:

```bash
npm run demo:record
```

That writes one folder per demo under:

```txt
source/frontend/e2e/artifacts/
```

Docs video exports:

| Demo | Video |
|---|---|
| Main Showcase | `docs/media/videos/showcase-demo.webm` |
| Payload Reduction | `docs/media/videos/payload-reduction-demo.webm` |
| Provenance | `docs/media/videos/provenance-demo.webm` |
| Greenland Abstain Safety | `docs/media/videos/abstain-safety-demo.webm` |
| Legacy Target-Pack Port Audit | `docs/media/videos/object-evidence-demo.webm` |
| Suez Maritime Eclipse | `docs/media/videos/orbital-eclipse-demo.webm` |
| Tutorial Walkthrough | `docs/media/videos/tutorial_video.webm` |
| README Timelapse Highlight | `docs/media/timelapse/highlight-greenland-ice-timelapse.gif`, `docs/media/timelapse/highlight-greenland-ice-timelapse.webm` |

Current mission split:

1. Main Showcase uses `Critical Minerals Expansion Watch` over the Salar de Atacama / Escondida / Atacama mining corridor. It boxes region-level extraction evidence: evaporation pond regions, tailings regions, open-pit expansion, industrial roads, facility clusters, exposed soil, and surface color change.
2. Fireline-to-Lifeline Watch stays second. Wildfire remains useful proof-of-work and emergency relevance, but it is no longer the centerpiece.
3. Maritime Activity Watch stays third and uses activity-level wording for vessel-like regions, wakes, and port clusters. It should not imply exact boat counts when resolution is insufficient.
4. Glacier / Ice Retreat Watch is fourth and should use slower long-form pacing. Columbia Glacier is the stronger later candidate because NASA has a long Landsat-backed retreat series; the current Greenland replay remains a spectral-confidence guard.
5. Waterline Watch is fifth. Great Salt Lake or Lake Mead are better long-term water/lifeline examples than garbage-patch mass monitoring because the water boundary is visible and measurable.
6. Coastal Debris / Slick Candidate Watch is experimental only. Use coastal, river-mouth, port, storm-aftermath, foam-line, slick, or debris-accumulation candidates. Do not frame it as Great Pacific Garbage Patch mass from optical imagery.

The Critical Minerals story is the strongest current main example because it is visually clear, long-term, commercially relevant, environmentally relevant, non-wildfire, non-maritime, and object/region-detection friendly. Public source backing is explicit: USGS shows Salar de Atacama lithium mining expansion between 1993 and 2015 with blue evaporation ponds visible in Landsat imagery, and ties lithium demand to rechargeable batteries, smartphones, mobile computers, and electric cars. NASA Earthdata identifies Salar de Atacama as Chile's largest salt flat, the world's third-largest salt flat, and one of the world's largest active lithium brine sources. NOAA's Great Pacific Garbage Patch guidance is the opposite kind of source: it says the patch is not a continuous visible trash island and may not be evident to the naked eye, so garbage-patch mass is not a safe main optical-satellite demo claim.

Sources:

- USGS: [Lithium Mining in Salar de Atacama, Chile](https://www.usgs.gov/media/before-after/lithium-mining-salar-de-atacama-chile)
- NASA Earthdata: [Lithium Mining in the Salar de Atacama, Chile](https://www.earthdata.nasa.gov/news/worldview-image-archive/lithium-mining-salar-de-atacama-chile)
- NOAA National Ocean Service: [What is the Great Pacific Garbage Patch?](https://oceanservice.noaa.gov/facts/garbagepatch.html)

The tutorial walkthrough is now the plain-English product run-through. It starts from clean app state with the Rondonia area selected, uses Ground Agent chat to launch a deforestation mission, shows the grid scan and space/ground agent handoff, then loads the replay-backed proof story for timelapse evidence, CV boxes, local model summary, compact proof JSON, and tagged training data. The main showcase video still leads with Critical Minerals Expansion Watch; the tutorial is optimized for showing what the app does end to end.

Replay-backed proof mode can now keep the active replay instead of forcing Rondonia, so mission-specific proof copy stays attached to maritime, mining, flood, wildfire, and urban replay packs. Some development replay fixtures use visible Sentinel-2 L2A frames and explicitly reject invalid still-image color-shift timelapses. Their real monthly WebMs are kept in the legacy `source/backend/assets/seeded_data/` cache for dataset export and training, but they are not a Sentinel Hub dependency for the default demo.

Current runtime wording: SimSat/Mapbox is the main hackathon satellite-data API family. SimSat Sentinel is the default realtime lane, SimSat Mapbox is optional imagery/context through the same SimSat path, and replay fixtures are used for deterministic demos. The SAT/GND GGUF runtime reasons over scored evidence packets. The separate `/api/inference/image` lane passes retained frames into LiquidAI/LFM2.5-VL-450M through Transformers when the optional image runtime is installed and enabled.

Enable and smoke-test retained-frame image review. This uses the backend `vision` extra, which installs Transformers, Torch, Torchvision, Accelerate, and Pillow:

```bash
cd ../..
export LFM_ORBIT_INSTALL_IMAGE_RUNTIME=true
export ORBIT_IMAGE_CONDITIONED_INFERENCE=true
export ORBIT_IMAGE_INFERENCE_BACKEND=transformers_vlm
export ORBIT_IMAGE_VLM_MODEL=LiquidAI/LFM2.5-VL-450M
./run.sh --install
cd source/backend
uv run --extra dev --extra model --extra vision python scripts/smoke_image_review.py --require-present
```

PowerShell equivalent:

```powershell
$env:LFM_ORBIT_INSTALL_IMAGE_RUNTIME="true"
$env:ORBIT_IMAGE_CONDITIONED_INFERENCE="true"
$env:ORBIT_IMAGE_INFERENCE_BACKEND="transformers_vlm"
$env:ORBIT_IMAGE_VLM_MODEL="LiquidAI/LFM2.5-VL-450M"
.\run.ps1 -Install
cd source\backend
uv run --extra dev --extra model --extra vision python scripts\smoke_image_review.py --require-present
```

Probe live SimSat Sentinel imagery without falling back to fixtures:

```bash
cd source/backend
uv run --no-sync python scripts/probe_live_observation.py \
  --provider simsat_sentinel \
  --bbox="-63.1,-10.1,-62.9,-9.9" \
  --start "2025-01-01" \
  --end "2025-02-01"
```

Target-pack wording: target packs are attached to missions, alerts, replay snapshots, dataset exports, and Proof Mode. They are no longer a separate Mission-tab operator tool. The main public showcase pack is `critical_minerals`; `deforestation`, `fireline`, `port`, `glacier`, `waterline`, `lifeline`, `camp`, and cautious `plastic`/coastal-debris packs remain available through presets and backend contracts.

Legacy target-pack port recordings live under `source/frontend/e2e/artifacts/object-evidence/` for audit history only. They must not be treated as normal Mission-tab UX, and they must not reopen exact/singular object boxes such as the rejected `channel vessel` box.

The visual use-case story builder writes every generated story plate and manifest under `source/backend/assets/seeded_data/visual_story_frames/`. Only promoted, visually audited public plates are copied to `docs/media/story-plates/`; currently that public set is Critical Minerals Expansion Watch and the port target-pack plate. Public plates must carry `visual_audit_status=approved`, and their box labels must read as areas, groups, zones, samples, corridors, or candidates unless a true object-scale model path supports a singular-object claim. Development-only Sentinel Hub credentials are loaded from environment variables or ignored local secret files, then reusable frames and provenance are stored in `source/backend/assets/seeded_data/visual_story_frames/`.

The story plates are visual proof assets, not hidden model claims. Sentinel Hub is used for broad satellite-context plates and timelapse-friendly development frames. Esri World Imagery context is used only where object-scale roofs/shelters need to be visible; those plates label `imagery_origin=esri_context`. All story boxes label `box_source=visual_story_fixture`, and the roof plate calls out sample boxes rather than an exhaustive roof count, so they are not confused with live model-backed detections. The cached story frames can be recycled into dataset exports with `python scripts/export_orbit_dataset.py --include-seeded-cache ...`, and the Playwright visual-story spec still verifies the real app can draw glowing CV boxes, legends, and provenance tooltips without overwriting README proof plates.

Replay WebMs may include cloudy context frames, but the proof panel keeps playback inside a clearer evidence window for final screenshots. Cloudy/no-data frames remain quality-gated in seeded creation and do not become positive detections.

Each recorded demo also saves `evidence-frame.png` beside `final-screen.png` and rejects blank or washed-out proof frames before copying the promoted WebM into `docs/media/videos/`.

Recorded demos preload their target mission or replay before the browser connects to telemetry. Demo config also disables the boot-time live agent pair, so recordings should not open on the legacy Amazonas sweep.

Live Florida Fire/Drought Readiness Watch is a smoke-testable readiness path, not a public proof claim. It defaults to a recent 30-day window and filters proxy-only vegetation changes before downlink; only source-backed smoke, active-fire, burn-scar, hotspot, or fireline-specific evidence should become retained fire candidates.

Cloud policy: cloudy or no-data windows are not allowed to become positive detections. For wildfire burn-scar seeds, active/ignition frames with valid dataMask can be retained as review-only smoke/cloud candidates when SCL flags a white plume as cloud; the confidence-assist layer then surfaces the cloud support and can defer the smoke claim instead of discarding the real frame.

Refresh the tutorial video:

```bash
npm run demo:tutorial
```

Refresh the README-safe Greenland timelapse highlight:

```bash
cd ../backend
uv run --no-sync python scripts/build_docs_timelapse_highlight.py
```

Optional development only: refresh high-quality Sentinel Hub replay cache after adding OAuth credentials:

```bash
cd source/backend
uv run --no-sync python scripts/seed_sentinel_cache.py --target rondoniaWS --grid 3 --cell-dim 0.05 --start 2023-01 --end 2025-01 --force --skip-vlm-metadata
```

This is useful for local real-data testing and dataset refreshes. It is not part of the DPhi SimSat showcase path. The Process API path needs a Sentinel Hub OAuth client id and client secret through environment variables or ignored local secret files. A single OGC/WMS instance id is only usable if its `GetCapabilities` endpoint is valid; it is not enough for Process API seeding.

Current cached development replay assets:

| Demo | Use case | WebM |
|---|---|---|
| Main Showcase | `mining_expansion` | `source/backend/assets/seeded_data/sh_fbe644a9.webm` |
| Tutorial Walkthrough | `deforestation` | `source/backend/assets/seeded_data/sh_07da3a0b.webm` cached into `docs/media/videos/tutorial_video.webm` by `npm run demo:tutorial` |
| Payload Reduction | `flood_extent` | `source/backend/assets/seeded_data/sh_24541539.webm` |
| Provenance | `mining_expansion` | `source/backend/assets/seeded_data/sh_fbe644a9.webm` |
| Florida Firewatch Replay | `wildfire` | `source/backend/assets/seeded_data/sh_83e3aea2.webm` with frame PNGs under `source/backend/assets/seeded_data/sh_83e3aea2_frames/` |
| Highway 82 Wildfire Replay | `wildfire` | `source/backend/assets/seeded_data/sh_4015e8b8.webm` with review-only smoke/cloud frame PNGs under `source/backend/assets/seeded_data/sh_4015e8b8_frames/` |
| Pineland Road Wildfire Replay | `wildfire` | `source/backend/assets/seeded_data/sh_af5954b2.webm` with review-only smoke/cloud frame PNGs under `source/backend/assets/seeded_data/sh_af5954b2_frames/` |
| Spain Larouco Wildfire Replay | `wildfire` | `source/backend/assets/seeded_data/sh_09384ab0.webm` with burn-scar frame PNGs under `source/backend/assets/seeded_data/sh_09384ab0_frames/` |
| Greenland Abstain Safety | `ice_cap_growth` | Local static preview; static WebM is excluded from Replay Cache |
| Greenland Ice/Snow Extent | `ice_snow_extent` | Metadata-scored curated replay with `source/frontend/public/demo-assets/greenland-ice-timelapse.webm` used as secondary science context |
| Suez Maritime Eclipse | `maritime_activity` | `source/backend/assets/seeded_data/sh_2d990c6b.webm` |
