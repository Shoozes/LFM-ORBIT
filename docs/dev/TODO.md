# TODO

Updated **May 8, 2026**.

This is the compact backlog and integrity checklist. Keep run-by-run history in `summary_bank.json`; keep product proof in `README.md`; keep implementation contracts in focused docs.

## Current State

- LFM Orbit is a demo-ready, local-first mission-control prototype, not an unattended production deployment.
- The hackathon satellite-data API family is SimSat/Mapbox through DPhi Space SimSat. Default realtime scanning uses `simsat_sentinel`; `simsat_mapbox` is the optional SimSat imagery/context lane when a Mapbox token is configured. Sentinel Hub, NASA, and GEE-style providers are optional development or replay support only.
- Sentinel Hub must stay a development/cache-seeding path for real/realtime research data, not the hackathon default provider. Release QA should prove the app boots and runs its default path with SimSat/Mapbox plus bundled cached replay assets, without requiring Sentinel Hub credentials.
- Evidence surfaces must keep `runtime_truth_mode`, `imagery_origin`, and `scoring_basis` visible.
- Replay-cache entries are stored real API imagery with preserved metadata. They are deterministic review assets, not generated evidence.
- New runtime cache WebM/meta outputs under `source/backend/assets/seeded_data/` are ignored by default; promote only reviewed fixtures with forced git add plus docs and summary-bank updates.
- Replay Cache excludes cached WebMs that fail timelapse-integrity checks.
- Cloud, no-data, malformed spectral bands, and RGB-only inputs must abstain instead of fabricating indices.
- Ground Agent mutating actions use proposal cards before state changes.
- Mission packs can declare a `proof_replay_id`; normal chat requests for those showcase packs load the deterministic proof replay by default, while explicit live/current/fresh requests still start a realtime scan.
- Mission target packs remain backend/proof metadata and appear through alerts, replays, dataset rows, and Proof Mode; the normal Mission tab stays focused on plan, replay, progress, and timelapse.
- Mission date windows are use-case aware: long-term change missions can keep annual/history windows, while operational Fire Watch presets default to the last 30 days through current date.
- Clean startup is idle by contract: the app opens on the Atacama mining context without auto-playing a replay, starting a mission, or letting the telemetry websocket scan the legacy default region.
- Area selection is a first-class map control: the map-side Area Tools card shows selected/drawing/scanning state, selected-cell count, bbox, Draw, and Clear without requiring the Mission tab.
- Launchers are defensive: option 1 / `-Install` stops stale repo-owned Orbit process trees on `8000` and `5173`, refuses unrelated port owners, starts Vite with `--strictPort`, captures backend run logs under `runtime-data/logs/` on Windows, and fails fast if backend health never comes up.
- `.\run.ps1 -Verify` is the release gate and now fails on external command exit codes from `uv`, `npm`, `npx`, Playwright, model fetch, or frontend dev startup.
- Public model/status APIs expose artifact filenames, repo metadata, capability flags, and presence booleans without leaking local absolute paths or secret-adjacent directories.
- Florida Fire/Drought Readiness Watch is candidate-only unless smoke, active-fire, burn-scar, hotspot, or fireline-specific source evidence is present; generic proxy vegetation changes are filtered before downlink.
- Wildfire smoke/fire replay proof now includes a confidence-assist lane and smoke/cloud review seeding: active wildfire frames can be retained as `review_only` when dataMask is valid but SCL flags white smoke as cloud. The backend stores B02/B03/B04/B08/B11/B12/SCL/CLD/CLP/dataMask summaries, and the assist can defer ambiguous white plumes without discarding the real frame.
- The retired target/monitor subtabs and visual-evidence tools panel must stay out of the submission UI unless deliberately reintroduced after review.
- Frontend reloads must not restart an active mission from the first scan cell or let stale demo query params override a live mission.
- Public README proof currently centers on Critical Minerals, target-pack proof, payload reduction, orbital eclipse queueing, provenance, abstain safety, Greenland timelapse context, Ground Agent flow, and semantic map context.
- The current trained LiquidAI Leap Tune-compatible bundle is fetched from `Shoozes/lfm2.5-450m-vl-orbit-satellite`; SAT/GND GGUF calls remain evidence-packet reasoning. `/api/inference/image` provides a separate opt-in retained-frame LiquidAI/LFM2.5-VL-450M image-text-to-text review path when `image_conditioned_runtime_enabled=true`.
- Proof Mode asks the backend for the retained visual-review image, then calls the image-review endpoint with `image_b64`, renders enabled/unavailable/abstain status, and includes `visual_model_review` in proof JSON. Alert persistence, replay snapshots, dataset export, and SFT-style training JSONL preserve the compact visual-review payload when present.
- The backend `vision` extra and launchers support `LFM_ORBIT_INSTALL_IMAGE_RUNTIME=true`; the extra includes Transformers `5.8+`, Torch, Torchvision, Accelerate, and Pillow. `scripts/smoke_image_review.py --require-present` is the real-runtime smoke gate, and `scripts/probe_live_observation.py` proves configured live SimSat imagery without fallback.
- Replay rescans rerun current prompt/model review over cached replay evidence, keep `runtime_truth_mode=replay` and `imagery_origin=cached_api`, rehydrate alerts/gallery/pins/messages/metrics, and return current model review metadata (`review_model_filename`, `review_model_revision`, `reviewed_at`, presence booleans) without exposing local paths.
- Option 1 / `-Install` / `--install` refresh moving Hugging Face model refs such as `main` instead of assuming the installed manifest is current.
- The shared trained GGUF runtime serializes completion calls so simultaneous satellite/ground-agent generations cannot crash the native llama.cpp context.
- Docs are split by audience: `docs/user/` is for demo/review operators, `docs/dev/` is for active architecture, data/model handoff, and backlog work; older planning notes stay under `docs/dev/archive/`.
- Tracked ad hoc backend scratch probes are pruned; use maintained scripts, tests, or documented manual provider probes instead.
- Manual Sentinel WMS connectivity/evalscript checks live in `source/backend/scripts/probe_sentinel_wms.py`; root-level `test_*.py` probes are intentionally blocked by import-contract tests.
- Manual Sentinel Hub cache refreshes are allowed for development/source-backed replay assets only. The May 5 Lochloosa West Fire seed attempt proved this path stays manual: `sh.txt` credentials resolved, the pre-fire Sentinel-2 L2A frame loaded, the May 4-5 event window was rejected for no-data/insufficient valid pixels, and no one-frame timelapse was written. The SR-26/Balu Forest fire seed succeeded as `sh_83e3aea2`. The May 7 South Georgia refresh promoted Highway 82 (`sh_4015e8b8`) and Pineland Road (`sh_af5954b2`) as real Sentinel-2 L2A burn-scar/smoke-cloud review replays with frame PNGs, richer band stats, and candidate-only curated replay wiring.
- The promoted real-provider cache keys, bbox/date windows, and reuse rules are tracked in [SEEDED_DATA_REGISTRY.md](SEEDED_DATA_REGISTRY.md). Check it before using Sentinel Hub credentials during replay polishing, training export, or threshold tuning.
- The May 7 Spain check promoted Larouco/Seadur (`sh_09384ab0`) as a real Sentinel-2 L2A burn-scar replay with baseline, active, and postfire frames; it is a review-strength burn-index case, not an active-fire confirmation.
- The May 7 wildfire proof pitfalls and fixes are logged in [archive/QA_PITFALLS.md](archive/QA_PITFALLS.md), including stale backend ports, Vite launch argument mistakes, invalid two-frame timelapses, smoke/cloud review handling, ignored seeded assets, and transient Playwright artifacts.
- The May 7 full integrity pass validated the staged repo from clean Windows and WSL/Linux clones. Playwright backend servers now use `uv run --locked`, and WSL requires native Linux `node`/`npm`/`npx`, `uv` on non-login PATH, and Playwright Chromium/deps before browser smoke tests.
- The May 7 Hugging Face dataset refresh published a larger `Shoozes/LFM-Orbit-SatData` training set and logged the export pitfalls in [archive/QA_PITFALLS.md](archive/QA_PITFALLS.md). The upload helper now validates JSONL, image references, local path leaks, orphaned images, and empty README-configured JSONL splits before upload.

## Active Backlog

- Rerun and review the Lochloosa West Fire Sentinel Hub seed after the next accepted post-event Sentinel pass before promoting Florida Fire/Drought Readiness Watch beyond candidate triage.
- Tune the wildfire confidence-assist thresholds with exported labels; current replay behavior intentionally defers smoke/cloud ambiguity instead of escalating it without hotspot or stronger burn-index support.
- Add a simple Settings/backlog-controlled switch to hide or disable cached replay data for live-provider testing. Keep it out of the default hackathon flow unless release QA shows operators are confusing cached replay proof with live SimSat/Mapbox scans.
- Add post-run Replay Cache diff output that compares completed current-model results against prior replay proof without overwriting the original proof.
- Keep the optional LiquidAI/LFM2.5-VL-450M image smoke in the release gate whenever the model revision, Transformers stack, or `vision` lockfile changes.
- Seed longer source-backed Atacama, Columbia Glacier, Great Salt Lake, and Lake Mead story assets before promoting those as README-level long-form proof.
- Expand object-evidence eval fixtures beyond the first replay-safe fireline/port cases and add stable CI thresholds.
- Extend responsive coverage into Proof Mode and long evidence panels. The main app shell now covers wide desktop, 16:9 mobile landscape, and 9:16 mobile portrait.
- Add a small frontend unit/component layer for high-churn pure logic and hooks.
- Keep import/export guards current whenever scripts, entrypoints, or dataset row types change.
- Add an optional upload polling helper that waits for Hugging Face Dataset Viewer `/size` to report no pending/failed configs and records the verified row counts automatically.
- Keep the docs user/dev split enforced when adding new markdown files.
- Keep Proof Mode media pre-warmed or trimmed so recorded videos do not linger on black loading states.
- Promote additional camera/location targets only with semantic profiles: aliases, bbox, center, camera, location type, terrain context, mission context, safe evidence guidance, and tags.
- Add optional external geocoding behind `/api/location/resolve` only if arbitrary place lookup becomes required. Keep the vetted local registry as the offline/default provider.
- Keep `marine_debris` and live HAB scoring as post-handoff Sentinel lanes. Planning notes are archived under [archive/FUTURE_SENTINEL_LANES.md](archive/FUTURE_SENTINEL_LANES.md).

## Scope Lock

Allowed before handoff:

- stability fixes
- broken import/export fixes
- reproducibility fixes
- small UI polish
- sharper SAT/GND/CV/LFM wording that keeps evidence boundaries honest
- docs pruning and link repair

Not allowed before handoff:

- new provider integrations
- new mission categories
- new dashboards
- half-added action kinds
- claims that imply the SAT/GND GGUF agents directly see images

## Edge Cases To Keep Covered

Evidence and provenance:

- Replayed cached API imagery must be `runtime_truth_mode=replay`, not "live".
- Realtime provider paths must name the provider/API family through `imagery_origin`.
- Fallback paths must carry fallback provenance and must not become high-confidence detections.
- Payload-reduction proof must keep `payload_accounting` explicit.
- Link-offline mode must queue compact JSON alerts locally and flush only after link recovery.

Object evidence:

- Target-pack controls remain backend/dev contracts and Proof Mode metadata, not first-run Mission-tab tools.
- Disabled targets stay skipped.
- Returned boxes normalize to `unit_xyxy`.
- Degenerate boxes are discarded after clamping.
- Unsafe labels such as people, weapons, protected wildlife, or population targets are rejected before custom packs or mission targets are saved.
- Candidate group/area language stays in place unless model/replay/operator provenance supports stronger claims.
- Story plates must disclose `box_source=visual_story_fixture` unless they come from a real model-backed detection path.

Maps and missions:

- Confirmed Ground Agent missions must interrupt boot/default scans quickly enough that the selected area becomes the visible scan.
- App reloads during an active scan must resume from saved mission progress and repaint previously scanned cells from mission state plus persisted alerts.
- Stale demo URLs such as `?demo=1&demoCase=forest` must not override active live missions.
- The app must not auto-play the last replay on normal startup.
- Running a showcase proof mission from chat after another mission must replace the prior mission/replay proof context and select the new replay primary evidence cell.
- The telemetry websocket must stay idle with an empty grid when no active mission exists; no backend scoring should happen just because the browser opened.
- Firewatch scans must not promote proxy-only canopy/vegetation deltas into map pins, ground confirmations, or fire claims.
- Stopped missions, replay contexts, and camera-only navigation show paused/idle scan state.
- Live missions show explicit starting, scanning, and complete status while cells arrive.
- Camera-only flyovers that populate a bbox must keep area state visible and clearable from the map, not hidden inside the Mission tab.
- Fire Watch and similar operational readiness missions use a recent 30-day default unless the operator explicitly requests historical trend analysis.
- Basemap render/tile/WebGL failures must stay visible and must not alter scoring or provenance.

Safety wording:

- Critical-minerals outputs stay region-level unless externally validated.
- Coastal debris/slick outputs stay candidate evidence; do not claim open-ocean garbage-patch mass growth from optical imagery.
- Algae/HAB prompts stay candidate-only without NOAA/FDEP or field confirmation.
- Protected-wildlife prompts redirect to habitat/access context only.
- Florida Fire/Drought Readiness Watch remains readiness/candidate triage until source-backed imagery confirms smoke, active fire, or burn scar.

Media and docs:

- Public docs markdown links resolve relative to the owning file.
- Promoted README images pass nonblank visual guards.
- Promoted WebMs show visible content and frame-to-frame change.
- Public docs media belongs under `docs/media/` and must be linked from markdown.
- Recorded demos preload their intended mission or replay before opening the browser.
- Fixed sleeps are acceptable only for intentional visual/video pacing.
- Docs must not describe retired normal-UI surfaces such as Mission Evidence panels, target/monitor subtabs, or the removed object-evidence demo script.

Model/runtime:

- Image-trained artifacts are not described as image-conditioned Orbit inference unless `/api/analysis/status` reports `image_conditioned_runtime_enabled=true`.
- `/api/inference/image` stays structured and provenance-rich when unavailable.
- The image-conditioned adapter must prove different image inputs affect output before enabling runtime image claims.
- Shared local GGUF inference must remain process-serialized unless the runtime is replaced with a concurrency-safe server or per-agent model context.
- Replay rescans must preserve the source replay id, cached replay provenance, current model review metadata, and `cached_rescan_current_model` scoring basis; completed comparison output must be additive so prior replay proof remains auditable.
- Playwright suites that own the default backend/debug/frontend ports must run one at a time unless explicit alternate ports are configured.
- Playwright must be launched from `source/frontend` so `playwright.config.ts` starts backend/debug/frontend web servers. Running from repo root with `npx --prefix` bypasses webServer setup and produces false `ECONNREFUSED` failures.
- WSL browser tests require native Linux browser dependencies. If Chromium fails with missing `libnspr4`, `libnss3`, `libatk`, `libgbm`, `libxkbcommon`, or `libasound2`, install them with `npx playwright install-deps chromium` from the frontend package.

## Verification Commands

- Full local verification: `.\run.ps1 -Verify` or `./run.sh --verify`
- Backend: `uv run --no-sync pytest -q` from `source/backend`
- Docs/media guard: `uv run --no-sync pytest tests/test_docs_artifacts.py -q` from `source/backend`
- Import/export guard: `uv run --no-sync pytest tests/test_import_contracts.py -q` from `source/backend`
- Image review API guard: `uv run --no-sync pytest tests/test_multimodal_inference.py tests/test_inference_image_api.py -q` from `source/backend`
- Optional real image runtime smoke: `uv run --extra dev --extra model --extra vision python scripts/smoke_image_review.py --require-present` from `source/backend`
- Optional live provider probe: `uv run --no-sync python scripts/probe_live_observation.py --provider simsat_sentinel --bbox="-63.1,-10.1,-62.9,-9.9" --start "2025-01-01" --end "2025-02-01"` from `source/backend`
- Frontend type/build guard: `npm run lint` and `npm run build` from `source/frontend`
- Full browser guard: `npm run test:e2e` from `source/frontend`
- Demo refresh: `npm run demo:record` and `npm run demo:tutorial` from `source/frontend`
- README timelapse refresh: `uv run --no-sync python scripts/build_docs_timelapse_highlight.py` from `source/backend`
- Offline story-plate refresh, dev only: `uv run --no-sync python scripts/build_visual_story_proofs.py --offline` from `source/backend`

## Latest Validation Snapshot

- Current local verification: `.\run.ps1 -Verify` passed end-to-end. Backend `499 passed`; GGUF runtime smoke passed; frontend typecheck/build passed; full Playwright passed `104 passed` with `6 skipped`. The latest May 8 integrity spot-check passed import contracts, docs artifacts, frontend typecheck/build, full replay backend tests, and the focused Ground Agent replay/rescan browser flow.
- Current launcher verification: `.\run.ps1 -Install` launched option-1 flow successfully; backend `8000` and frontend `5173` became ready, then the launched process tree was stopped cleanly.
- Cold staged-content verification: fresh Windows and WSL/Linux clones passed before the final wildfire/docs guard additions; the current release gate is the full local `499 passed` backend suite plus option-1 launcher smoke. Windows covered `uv sync --extra dev`, `npm ci`, frontend build, and responsive/replay smoke. WSL/Linux covered native Linux Node/uv setup, `npm ci`, frontend build, Playwright Chromium/deps install, and the same responsive/replay smoke.
- Current runtime boundary: SAT/GND GGUF calls remain text evidence-packet reasoning; `/api/inference/image` is optional LiquidAI/LFM2.5-VL-450M image-conditioned retained-frame review and only reports enabled after a real adapter passes image pixels.
- Current media verification: `npm run demo:record` passed `5`, `npm run demo:tutorial` passed `1`, the regenerated tutorial is about `265s`, and sampled contact sheets/screenshots are nonblank with expected Proof Mode fallback wording.
- Current export boundary: alert persistence, replay snapshots, dataset samples, and training JSONL carry `visual_model_review` when present; rows with successful visual review export as image/text SFT rows, and rows without visual review remain valid evidence-packet rows.
- Current public media boundary: generated WebMs stay tracked under `docs/media/videos/` for release assets and local audit; public playback is handled outside GitHub.
- Historical run-by-run details live in `summary_bank.json`; keep this section limited to the latest release-relevant validation state.
