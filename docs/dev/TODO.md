# TODO

Updated **August 4, 2026**.

This is the compact backlog and integrity checklist. Keep current context routing in `summary_bank.json`, historical route notes in `archive/summary_bank_history.json`, product proof in `README.md`, and implementation contracts in focused docs.

## Current State

- LFM Orbit is a demo-ready, local-first mission-control prototype, not an unattended production deployment.
- The default satellite-data API family is SimSat/Mapbox through DPhi Space SimSat. Default realtime scanning uses `simsat_sentinel`; `simsat_mapbox` is the optional SimSat imagery/context lane when a Mapbox token is configured. Sentinel Hub, NASA, and GEE-style providers are optional development or replay support only.
- Sentinel Hub must stay a development/cache-seeding path for real/realtime research data, not the default provider. Release QA should prove the app boots and runs its default path with SimSat/Mapbox plus bundled cached replay assets, without requiring Sentinel Hub credentials.
- Evidence surfaces must keep `runtime_truth_mode`, `imagery_origin`, and `scoring_basis` visible.
- Replay-cache entries are stored real API imagery with preserved metadata. They are deterministic review assets, not generated evidence.
- New runtime cache WebM/meta outputs under `source/backend/assets/seeded_data/` are ignored by default; the tracked `nasa_aa01bc81.webm` file is the explicit frontend E2E context-timelapse fixture, and other generated NASA assets require forced promotion plus docs and summary-bank updates.
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
- The hosted portfolio route is separate from the full app: the normal build keeps the full app at `/` and the browser-only alias at `/hosted`; `npm run build:hosted` emits an isolated static bundle at `/` with Wllama/WebAssembly, a pinned small GGUF manifest, validated saved packages, and no backend/provider controls. The browser runtime is text reasoning over saved evidence, not image-conditioned VLM inference.
- The hosted route reads the static model manifest before any GGUF request, displays the pinned model identity/size/license/capability, and exposes separate download and generation cancellation states so a stopped response can reuse the loaded browser instance.
- Mission confirmation overrides are now persisted through `core/mission.py` and `/api/mission/start`; omitted policy still falls back to the conservative `distinct_acquisition` region setting, while explicitly requested `single_acquisition` is available for one-shot callers.
- The repository boundary is explicit: LFM-ORBIT `main` carries the public application, GenUni remains the separate training-cycle/producer repository, and `.tools/project.json` points publish/pull helpers at public LFM-ORBIT while recording GenUni as `trainingRemote`.
- Boundary, remote-target, and cross-history recovery pitfalls are recorded in [PITFALL_LEDGER.md](PITFALL_LEDGER.md); keep it focused on regression prevention rather than progress reporting.
- Generated observations and timelapse caches are runtime-owned under `CANOPY_SENTINEL_RUNTIME_DIR`; committed seeded replay fixtures remain read-only inputs, and JSON/metadata writes use replace-safe temporary files.
- Replay snapshot imports validate shape, row limits, numeric finiteness, and payload ranges before reset; reset failures attempt a compensating restore so malformed imports do not silently erase the prior runtime.
- Proof Mode asks the backend for the retained visual-review image, then calls the image-review endpoint with `image_b64`, renders enabled/unavailable/abstain status, and includes `visual_model_review` in proof JSON. Alert persistence, replay snapshots, dataset export, and SFT-style training JSONL preserve the compact visual-review payload when present.
- The backend `vision` extra and launchers support `LFM_ORBIT_INSTALL_IMAGE_RUNTIME=true`; the extra includes Transformers `5.8+`, Torch, Torchvision, Accelerate, and Pillow. `scripts/smoke_image_review.py --require-present` is the real-runtime smoke gate, and `scripts/probe_live_observation.py` proves configured live SimSat imagery without fallback.
- Replay rescans rerun current prompt/model review over cached replay evidence, keep `runtime_truth_mode=replay` and `imagery_origin=cached_api`, rehydrate alerts/gallery/pins/messages/metrics, and return current model review metadata (`review_model_filename`, `review_model_revision`, `reviewed_at`, presence booleans) without exposing local paths. Mission Control labels replay provenance and can hide the catalog for live-only QA; the rescan comparison is additive and preserves the source replay.
- Option 1 / `-Install` / `--install` refresh moving Hugging Face model refs such as `main` instead of assuming the installed manifest is current.
- The shared trained GGUF runtime serializes completion calls so simultaneous satellite/ground-agent generations cannot crash the native llama.cpp context.
- Proof Mode hydration is keyed to stable mission identity; high-frequency mission and telemetry refreshes must not cancel the current mission's related-timelapse request.
- Docs are split by audience: `docs/user/` is for demo/review operators, `docs/dev/` is for active architecture, data/model handoff, and backlog work; older planning notes stay under `docs/dev/archive/`.
- Tracked ad hoc backend scratch probes are pruned; use maintained scripts, tests, or documented manual provider probes instead.
- Broadcast bus rows now use per-recipient receipts, so ground and satellite consumers can each receive the same broadcast without the first reader hiding it from the other.
- Candidate persistence is keyed by `(mission_id, cell_id)`; an old candidate table without `mission_id` is discarded as transient state during migration instead of leaking anomaly streaks into a new mission.
- Alert records now preserve `mission_id`, `use_case_id`, and `target_pack_id`; dataset export honors explicit mission use cases and falls back to generic temporal-change labels rather than deforestation labels.
- SAT triage prompts now derive category, task, signals, and temporal methods from the active temporal-use-case contract; they no longer assume deforestation when a mission is wildfire, maritime, flood, or generic change review.
- Generated timelapse caches use a versioned key over effective months, bbox, and provider preference. Legacy bbox-only keys remain available only to committed replay-fixture readers.
- Telemetry WebSocket clients share one bounded scan producer and receive a replay of the latest published state on subscribe; the optional boot-time SAT agent still needs an explicit single-engine policy before it is enabled alongside live telemetry scanning.
- Image and depth request decoding share bounded base64/byte limits, pixel checks, and readable-image validation. Mutating and resource-heavy POST routes are local-request guarded and bounded by process-wide concurrency/time budgets exposed through health; replay snapshot boolean imports use strict text coercion.
- Manual Sentinel WMS connectivity/evalscript checks live in `source/backend/scripts/probe_sentinel_wms.py`; root-level `test_*.py` probes are intentionally blocked by import-contract tests.
- Manual Sentinel Hub cache refreshes are allowed for development/source-backed replay assets only. The May 5 Lochloosa West Fire seed attempt proved this path stays manual: `sh.txt` credentials resolved, the pre-fire Sentinel-2 L2A frame loaded, the May 4-5 event window was rejected for no-data/insufficient valid pixels, and no one-frame timelapse was written. The SR-26/Balu Forest fire seed succeeded as `sh_83e3aea2`. The May 7 South Georgia refresh promoted Highway 82 (`sh_4015e8b8`) and Pineland Road (`sh_af5954b2`) as real Sentinel-2 L2A burn-scar/smoke-cloud review replays with frame PNGs, richer band stats, and candidate-only curated replay wiring.
- The promoted real-provider cache keys, bbox/date windows, and reuse rules are tracked in [SEEDED_DATA_REGISTRY.md](SEEDED_DATA_REGISTRY.md). Check it before using Sentinel Hub credentials during replay polishing, training export, or threshold tuning.
- The May 7 Spain check promoted Larouco/Seadur (`sh_09384ab0`) as a real Sentinel-2 L2A burn-scar replay with baseline, active, and postfire frames; it is a review-strength burn-index case, not an active-fire confirmation.
- The May 7 wildfire proof pitfalls and fixes are logged in [archive/QA_PITFALLS.md](archive/QA_PITFALLS.md), including stale backend ports, Vite launch argument mistakes, invalid two-frame timelapses, smoke/cloud review handling, ignored seeded assets, and transient Playwright artifacts.
- The May 7 full integrity pass validated the staged repo from clean Windows and WSL/Linux clones. Playwright backend servers now use `uv run --locked`, and WSL requires native Linux `node`/`npm`/`npx`, `uv` on non-login PATH, and Playwright Chromium/deps before browser smoke tests.
- The May 7 Hugging Face dataset refresh published a larger `Shoozes/LFM-Orbit-SatData` training set and logged the export pitfalls in [archive/QA_PITFALLS.md](archive/QA_PITFALLS.md). The upload helper now validates JSONL, image references, local path leaks, orphaned images, and empty README-configured JSONL splits before upload.

## Completed in This Pass

- Hosted package/model manifests, isolated production entry, static-safe browser preview, and no-backend/MIME smoke proof are complete. Done when: `npm run verify:hosted` passes with FastAPI stopped and `dist-hosted` contains no full-app chunks.
- Browser artifact identity is sealed to the pinned Hugging Face revision, SHA-256, byte count, license, and text-only capability contract. Done when: the browser validates the manifest, pointer, and byte count before Wllama loads.
- Telemetry producer cleanup is generation-safe, the lifespan supervisor keeps live missions scanning with zero viewers, confirmation policy is explicit, mission-persisted, and replay-snapshot-preserved, and expensive backend work has deterministic concurrency/timeout responses. Done when: focused scanner/resource/mission/API/replay tests and health metadata prove the contracts.
- Runtime-owned atomic artifacts use collision-resistant temporary names for concurrent Windows writers. Done when: the metrics writer regression passes under synchronized concurrent writes and the replay browser path no longer loses mission state to a temp-file permission race.
- Active portfolio copy no longer uses competition-only runtime framing; historical QA remains archived in the context bank. Done when: active data/agent copy passes the retired-term guard and archived records remain attributable.
- Summary-bank routing is consolidated into a small default orientation route plus focused workflow/feature/issue routes; historical groups remain recoverable in `docs/dev/archive/summary_bank_history.json`. Done when: the context audit reports no missing references, no archived default groups, and the project controller opens a live default group.
- Runtime SQLite helpers now commit successful work, roll back failures, and close every connection through one shared lifecycle helper. Done when: the lifecycle regression covers agent bus, DTN queue, and debug connections and the warnings-enabled API suite emits no runtime database-leak warnings.
- Telemetry refreshes now abort superseded work and ignore stale/unmounted responses; metrics polling and WebSocket callbacks stop updating state after cleanup. Done when: frontend typecheck/build passes and the browser guard remains green.
- The hosted hero action now starts the browser-local Wllama fetch directly after manifest identity is visible, with separate generation cancellation and an opt-in real-model smoke proving the static route needs no FastAPI/model server. Done when: the real hosted fetch reaches local-ready state, generation returns a response, and no `/api`, `/ws`, or port-8000 requests occur.
- The production hosted proof now covers the built preview, browser-local generation, executable JavaScript MIME, and `application/wasm` MIME. Done when: `npm run test:hosted:model:build` passes after `npm run build:hosted`.
- Current-state docs now distinguish the August 4 root-launcher rerun from the historical May release gate and the optional trained-GGUF smoke lane; target-pack contracts carry the current review date. Done when: docs/media guards pass and no current doc conflates `run.ps1 -Verify` with the optional trained-GGUF smoke.
- GitHub Actions and CodeQL workflow pins now target Node-24-native action majors, while heavyweight real hosted model fetches remain outside normal E2E. Done when: the CI summary passes without a Node-20 runtime annotation and the normal test list excludes the opt-in model-fetch specs.
- Hosted browser capability probing now gates WebAssembly, browser storage, and device-memory risk before fetch; unsupported or incomplete signals keep the saved-package route usable and preserve `imageInput=false`. Done when: `npm run test:unit`, hosted contract smoke, and actionable fallback copy all pass without a backend request.
- Hosted saved evidence is schema-v2 and traces each promoted card to a local replay manifest, bbox, observation window, scoring basis, runtime truth, imagery origin, and retention decision. Done when: package validation, source-replay inventory tests, and hosted static smoke pass offline.
- Cached replay QA now has a local visibility switch plus an additive prior/current model comparison with source replay identity and scoring bases preserved. Done when: focused replay tests and Playwright prove hidden replay entries, live-only copy, and comparison output without overwriting the original proof.
- Mission Control now lets an operator deliberately choose distinct-acquisition or one-shot confirmation and displays the persisted policy after launch. Done when: API/scanner/replay persistence tests and serialized browser wiring prove the selected policy and safe default.
- The hosted proof cut is captured as `docs/media/videos/hosted-demo.webm`, linked from the README/media inventory, and generated without a model fetch. Done when: the capture passes and media guards confirm duration, temporal change, and nonblank samples.
- The current vetted location registry and explicitly unavailable future Sentinel lanes are covered by contract tests and archive guards. Done when: target/location tests pass and no provider or marine/HAB action is half-wired.
- The public/private repository boundary is documented and synchronized. Done when: LFM-ORBIT `main` is the app remote, GenUni `main` retains its pre-migration training app state, links and controller policy point to the correct repositories, and the handoff note records both histories.

## External Gates (not local stubs)

- Task: Revalidate wildfire source evidence before promotion. **Owner/provider evidence required.**
  - What/Why: The current Fire/Drought Watch correctly defers smoke/cloud ambiguity, but the Lochloosa seed has not earned stronger-than-candidate wording.
  - Where: Sentinel seed manifests, `source/backend/assets/replays/`, `source/backend/core/wildfire_smoke.py`, and wildfire confidence tests.
  - How: An owner must rerun the next accepted post-event pass, record source/frame provenance, and tune thresholds against exported labels while preserving candidate-only behavior.
  - Done when: A reviewed replay has accepted source-backed frames, stable confidence metrics, updated provenance docs, and tests prove ambiguous smoke remains review-only.
  - Verification: `uv run --no-sync pytest tests/test_wildfire_smoke.py tests/test_seed_sentinel_cache.py tests/test_replay.py -q` plus a reviewed manifest/frame audit and owner acceptance.

- Task: Audit model licensing and publishable handoff metadata. **Owner/legal evidence required.**
  - What/Why: The hosted manifest reports `mit` for the Shoozes handoff repository while the upstream Liquid AI base model is labeled `lfm1.0`; repository metadata must not settle inherited model or artifact redistribution terms.
  - Where: `source/frontend/public/model-manifest.json`, `docs/user/HOSTED_DEMO.md`, `docs/dev/MODEL_HANDOFF.md`, the Shoozes Hugging Face handoff repo, and `docs/legal/THIRD_PARTY_NOTICES.md`.
  - How: The repository owner/legal reviewer must confirm the handoff model card, base-model license, quantization/artifact terms, and required attribution, then encode approved license-source fields without runtime inference.
  - Done when: one owner-approved decision covers the published GGUF, base model, quantization, hosted redistribution, and displayed attribution, with matching model-card/docs/tests.
  - Verification: manifest/license consistency test, third-party-notices review, pinned handoff revision audit, and explicit owner sign-off.

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
- Resource-limit guard: `uv run --no-sync pytest tests/test_request_limits.py -q` from `source/backend`
- Optional real image runtime smoke: `uv run --extra dev --extra model --extra vision python scripts/smoke_image_review.py --require-present` from `source/backend`
- Optional live provider probe: `uv run --no-sync python scripts/probe_live_observation.py --provider simsat_sentinel --bbox="-63.1,-10.1,-62.9,-9.9" --start "2025-01-01" --end "2025-02-01"` from `source/backend`
- Frontend type/build guard: `npm run lint` and `npm run build` from `source/frontend`
- Hosted static guard: `npm run verify:hosted` from `source/frontend` (`build:hosted` followed by the static preview smoke)
- Full browser guard: `npm run test:e2e` from `source/frontend`
- Demo refresh: `npm run demo:record` and `npm run demo:tutorial` from `source/frontend`
- README timelapse refresh: `uv run --no-sync python scripts/build_docs_timelapse_highlight.py` from `source/backend`
- Offline story-plate refresh, dev only: `uv run --no-sync python scripts/build_visual_story_proofs.py --offline` from `source/backend`

## Latest Validation Snapshot

- Prior recorded release verification: `.\run.ps1 -Verify` passed end-to-end on May 8 with backend `499 passed`, GGUF runtime smoke, frontend typecheck/build, and full Playwright E2E with intentional skips. Treat that as historical until the current environment reruns the launcher gate.
- August 4 backend verification: `python -m pytest -q` recorded `552 passed`; coverage includes queue, prompt, cache, image-safety, local-boundary, path, replay-validation, additive cached-rescan comparison, project-config, CI workflow, clean-checkout assets, scenario-registry, model-handoff identity, hosted package wiring, telemetry-coordinator contracts, mission-owned scanning, persisted/replay-safe confirmation-policy API wiring, resource-limit behavior, SQLite lifecycle closure, and concurrent runtime-artifact writes.
- August 4 hosted verification: `npm run lint`, `npm run build:hosted`, `npm run test:hosted`, and `npm run test:hosted:build` passed from `source/frontend`; the hosted smoke does not start FastAPI or require the backend model runtime, the static preview proves JSON/JavaScript/WebAssembly MIME types, and the manifest identity is visible before a model request.
- August 4 hosted production browser-model verification: `npm run test:hosted:model:build` passed after the real 219 MB GGUF fetch; the built preview reached local-ready state and generated a local response with no backend/API/WebSocket requests. This remains opt-in and excluded from the normal/full E2E configs because it depends on network, device memory, and browser cache state.
- August 4 full-app launcher verification: `.\run.ps1 -Verify` passed with `108 passed, 6 skipped` and intentional skips; the replay-replacement case passed after the Windows-safe atomic runtime-writer fix, the 7-minute tutorial capture passed, and the tracked README/tutorial media was regenerated by the verification suite.
- The GitHub E2E job allows 35 minutes so clean runners can install Playwright OS/browser dependencies before the serialized full suite; this is a CI budget, not a hosted-demo requirement.
- August 3 hosted media verification: `npm run demo:hosted` passed and regenerated the nonblank README stills for the hero and saved-evidence sections; the capture path does not fetch the GGUF.
- August 3 frontend dependency verification: `npm audit --omit=dev` reported zero vulnerabilities after the Vite/PostCSS update.
- The full-app launcher/Playwright gate requires the backend `uv` environment; optional trained-GGUF smoke and browser model-fetch lanes remain separate. Do not report any of these as current hosted-demo requirements.
- Prior launcher verification: `.\run.ps1 -Install` launched option-1 flow successfully; backend `8000` and frontend `5173` became ready, then the launched process tree was stopped cleanly.
- Cold staged-content verification: fresh Windows and WSL/Linux clones passed before the final wildfire/docs guard additions; those historical runs covered `uv sync --extra dev`, `npm ci`, frontend build, Playwright Chromium/deps install, and responsive/replay smoke.
- Current runtime boundary: SAT/GND GGUF calls remain text evidence-packet reasoning; `/api/inference/image` is optional LiquidAI/LFM2.5-VL-450M image-conditioned retained-frame review and only reports enabled after a real adapter passes image pixels.
- Current media verification: `npm run demo:record` passed `5`, `npm run demo:tutorial` passed `1`, the regenerated tutorial is about `267s`, and sampled contact sheets/screenshots are nonblank with expected Proof Mode fallback wording.
- Current export boundary: alert persistence, replay snapshots, dataset samples, and training JSONL carry `visual_model_review` when present; rows with successful visual review export as image/text SFT rows, and rows without visual review remain valid evidence-packet rows.
- Current public media boundary: generated WebMs stay tracked under `docs/media/videos/` for release assets and local audit; public playback is handled outside GitHub.
- Historical run-by-run details live in `summary_bank.json`; keep this section limited to the latest release-relevant validation state.
