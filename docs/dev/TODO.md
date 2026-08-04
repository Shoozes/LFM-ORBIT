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
- The hosted portfolio route is separate from the full app: the normal build keeps the full app at `/` and the browser-only alias at `/hosted`; `npm run build:hosted` emits an isolated static bundle at `/`, while `npm run build:pages` emits the same browser-only route under a configurable project base such as `/LFM-ORBIT/`. The browser runtime is text reasoning over saved evidence, not image-conditioned VLM inference.
- Every promoted hosted package has a repo-local visual asset and accessible alt text; the fireline card uses the reviewed `fireline_sentinel.png` source frame and remains candidate/review-only.
- The hosted route has one parsed deployment capability and a fail-closed model gate. Local hosted builds keep the manifest-first browser fetch lane; Pages builds default to the model-free `hosted-main.tsx` entry and emit no model manifest, Wllama chunk, or WASM unless `VITE_HOSTED_MODEL_ENABLED=true` is explicitly supplied.
- Model-enabled browser loading requires a secure context and selects single-thread Wllama mode when cross-origin isolation is unavailable; iOS Safari compatibility remains an external physical-device proof, with saved packages as the safe fallback.
- Mission confirmation overrides are persisted through `core/mission.py` and `/api/mission/start`; one-shot missions default to `single_acquisition`, while recurring monitors can explicitly choose `distinct_acquisition`, which counts stable acquisition fingerprints rather than repeated cached evidence.
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
- Frontend mission and Agent Dialogue polling share a request gate that aborts superseded/unmounted work and ignores late responses; telemetry JSON refreshes time out, and agent-dialogue WebSocket payloads are validated, bounded, and retried with capped backoff.
- Docs are split by audience: `docs/user/` is for demo/review operators, `docs/dev/` is for active architecture, data/model handoff, and backlog work; older planning notes stay under `docs/dev/archive/`.
- Tracked ad hoc backend scratch probes are pruned; use maintained scripts, tests, or documented manual provider probes instead.
- Broadcast bus rows now use per-recipient receipts, so ground and satellite consumers can each receive the same broadcast without the first reader hiding it from the other.
- Candidate persistence is keyed by `(mission_id, cell_id, acquisition_key)`; legacy candidate tables without acquisition identity are discarded as transient state during migration instead of counting the same cached evidence twice or leaking a streak into a new mission.
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

## Completed Local Integrity Items

- [x] Task: Restore the locked backend verification environment. **P1 / developer-environment gate.**
  - What/Why: The Windows project environment had been linked to a missing uv-managed Python executable, which prevented fresh backend/import/docs verification and left the locked `httpx2` warning unresolved.
  - Where: `source/backend/.venv-windows` (ignored), `source/backend/pyproject.toml`, `source/backend/uv.lock`, and the repo-local uv bootstrap under `runtime-data/tools/uv-venv/`.
  - How: Recreated the ignored Windows environment with repo-local `uv sync --locked --extra dev` using the declared lockfile and verified the focused contracts plus the full suite.
  - Done when: `uv run --locked pytest -q` starts from a clean/resynchronized environment, the `httpx2` warning is absent, and the focused import/docs/CI guards pass.
  - Verification: focused import/docs/CI gate `33 passed`; full locked backend suite `557 passed` with no application failures.

- [x] Task: Keep seeded-cache export metadata portable.
  - What/Why: Export records must identify the seeded metadata file without leaking a workspace or temporary-directory prefix when fixtures are generated outside the repository.
  - Where: `source/backend/scripts/export_orbit_dataset.py` and `source/backend/tests/test_export_orbit_dataset.py`.
  - How: Serialize the seeded metadata filename directly and retain the workspace-owned temporary-path regression coverage.
  - Done when: seeded-cache export records always emit the metadata filename and the exporter regression passes from an in-repository temporary directory.
  - Verification: focused exporter regression passed; full locked backend suite passed `557` tests.

- [x] Task: Harden frontend agent-bus and telemetry refresh boundaries.
  - What/Why: Browser WebSocket JSON and periodic API responses are external input; malformed agent fields could reach JSX, dialogue history could grow without a limit, and fixed/infinite retries could waste resources during a backend outage.
  - Where: `source/frontend/utils/agentBusCore.js`, `source/frontend/hooks/useAgentBus.ts`, `source/frontend/hooks/useTelemetry.ts`, and `source/frontend/components/AgentDialogue.tsx`.
  - How: Validate and normalize supported envelopes, retain only the latest 200 messages, cap reconnect attempts with exponential backoff, bound telemetry JSON calls to five seconds, and cancel/timeout operator injection.
  - Done when: malformed envelopes are ignored without render errors, late/unmounted requests cannot repaint state, reconnects stop after the configured cap, and focused tests cover normalization, deduplication, and retention.
  - Verification: frontend lint/build passed; `npm run test:unit` passed `17` tests including three agent-bus boundary cases.

## Active Backlog

- Task: Prove the deployed Pages origin. **Owner/runtime evidence required.**
  - What/Why: Local project-path proof cannot establish public-origin CORS, MIME, caching, browser-storage, or model-download behavior.
  - Where: the successful `github-pages` deployment, the deployed HTTPS project URL, `source/frontend/playwright.hosted.pages.live.static.config.ts`, `source/frontend/e2e/hosted.pages.live.static.spec.ts`, and the release-only model harness.
  - How: Let the workflow run the no-weight static-origin smoke after deployment, then set `HOSTED_PAGES_URL` to the exact trailing-slash HTTPS project URL for the opt-in model proof; verify project-path HTML/JS/CSS/JSON/images MIME, explicit absence of model runtime assets, no backend/API/WebSocket/provider requests, and measurable cached model reuse only after licensing is approved.
  - When: After the Pages workflow is deployed and GitHub reports the environment URL.
  - Subtasks: `[x]` Build the fail-closed live harness and timing attachment. `[x]` Add Chromium/dependency installation and post-deploy static smoke. `[x]` Make Pages model-free by default and audit the no-runtime artifact. `[ ]` Deploy the workflow and retain the static-origin proof. `[ ]` Run the first/cached model proof on an owner-approved HTTPS model-enabled release.
  - Done when: the public Pages origin completes the saved-only static smoke; the later model-enabled HTTPS release completes initial and cached local model loads with recorded browser/runtime timing and the proof is retained with the release record.
  - Verification: release-only or scheduled Playwright run using the deployed URL; do not add the model download to every commit.

- Task: Link the verified Pages URL from public entry points. **Owner/runtime evidence required.**
  - What/Why: The repository intentionally does not invent a live URL before deployment, but a verified public demo should be discoverable from the README and hosted-demo guide.
  - Where: `README.md`, `docs/user/HOSTED_DEMO.md`, and the repository About/Homepage field.
  - How: After the Pages workflow completes, copy the exact environment URL into the public links and keep the local `/LFM-ORBIT/` path contract documented separately.
  - When: Immediately after the deployed-origin proof succeeds.
  - Done when: every public entry point uses the same verified URL and the link checker/browser smoke can open it without redirect or base-path errors.
  - Verification: open the final URL from each linked document and rerun the deployed-origin smoke.

- Task: Resolve model redistribution and attribution metadata. **Owner/legal evidence required.**
  - What/Why: The derivative handoff currently advertises `mit`, while the upstream LiquidAI model card advertises `lfm1.0`; the repository must not infer inherited terms from one label.
  - Where: `source/frontend/hosted/model-manifest.json`, `docs/legal/THIRD_PARTY_NOTICES.md`, `docs/user/HOSTED_DEMO.md`, `docs/dev/MODEL_HANDOFF.md`, and the Shoozes Hugging Face model card.
  - How: Confirm derivative artifact, base-model, quantization, redistribution, attribution, and naming terms; publish a corrected immutable model revision if required, then update manifest identity and tests together. Until then, keep Pages on the saved-packages-only build gate while local model tests remain opt-in.
  - When: Before public model promotion or any live-origin proof is treated as release-ready.
  - Done when: owner/legal sign-off, model-card metadata, browser manifest, displayed copy, and third-party notices agree for the exact pinned revision.
  - Verification: pinned pointer/byte/hash proof plus a manifest/license consistency test and recorded owner decision.

- Task: Verify preserved hackathon archive references. **Owner/repository evidence required.**
  - What/Why: Modern `main` is the public app, but the original submission must remain independently recoverable.
  - Where: remote `hackathon` branch, immutable release tag, `docs/dev/REPOSITORY_BOUNDARY.md`, and CI branch triggers.
  - How: Resolve the branch and tag to the intended pre-modernization submission commit in a clean clone; create missing references only with explicit owner authorization.
  - When: Before the next public release or repository-boundary migration.
  - Done when: a clean clone can check out modern `main` and the preserved submission state, and active CI does not run the modern gate for the immutable archive unless requested.
  - Verification: `git ls-remote`, annotated-tag/object verification, clean-clone checkout, and boundary-doc update.

## External Gates (not local stubs)

- Task: Revalidate wildfire source evidence before promotion. **Owner/provider evidence required.**
  - What/Why: The current Fire/Drought Watch correctly defers smoke/cloud ambiguity, but the Lochloosa seed has not earned stronger-than-candidate wording.
  - Where: Sentinel seed manifests, `source/backend/assets/replays/`, `source/backend/core/wildfire_smoke.py`, and wildfire confidence tests.
  - How: An owner must rerun the next accepted post-event pass, record source/frame provenance, and tune thresholds against exported labels while preserving candidate-only behavior.
  - When: At the next accepted post-event source window, before stronger-than-candidate wording is published.
  - Done when: A reviewed replay has accepted source-backed frames, stable confidence metrics, updated provenance docs, and tests prove ambiguous smoke remains review-only.
  - Verification: `uv run --no-sync pytest tests/test_wildfire_smoke.py tests/test_seed_sentinel_cache.py tests/test_replay.py -q` plus a reviewed manifest/frame audit and owner acceptance.

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
- Hosted Pages guard: `npm run build:pages` followed by `npm run test:hosted:pages` from `source/frontend`; the default Pages artifact must omit the model manifest, Wllama chunk, and WASM
- Deployed Pages guard: set `HOSTED_PAGES_URL` to the exact trailing-slash Pages URL, then run `npm run test:hosted:pages:live` from `source/frontend`; this is release-only because it downloads the model twice.
- Deployed Pages static guard: set `HOSTED_PAGES_URL` to the exact trailing-slash Pages URL, then run `npm run test:hosted:pages:live:static`; this checks the public origin without downloading model weights.
- Full browser guard: `npm run test:e2e` from `source/frontend`
- Demo refresh: `npm run demo:record` and `npm run demo:tutorial` from `source/frontend`
- README timelapse refresh: `uv run --no-sync python scripts/build_docs_timelapse_highlight.py` from `source/backend`
- Offline story-plate refresh, dev only: `uv run --no-sync python scripts/build_visual_story_proofs.py --offline` from `source/backend`

## Latest Validation Snapshot

- Prior recorded release verification: `.\run.ps1 -Verify` passed end-to-end on May 8 with backend `499 passed`, GGUF runtime smoke, frontend typecheck/build, and full Playwright E2E with intentional skips. Treat that as historical until the current environment reruns the launcher gate.
- August 4 backend verification: the repo-local Windows environment was resynchronized with `uv sync --locked --extra dev`; the focused import/docs/CI gate passed `33` tests and the full locked repository gate passed `557` tests with no application failures or `httpx2` warning. Coverage includes queue migration/idempotency, acquisition-aware scanner confirmation, mission defaults, prompt, cache, image-safety, local-boundary, path, replay-validation, additive cached-rescan comparison, project-config, CI workflow, clean-checkout assets, scenario-registry, model-handoff identity, hosted package wiring, telemetry-coordinator contracts, resource-limit behavior, SQLite lifecycle closure, concurrent runtime-artifact writes, seeded-cache export portability, and default Playwright Pages-spec exclusion.
- August 4 current hosted implementation: `npm run lint`, `npm run test:unit`, `npm run build`, `npm run build:hosted`, and the default saved-packages-only `npm run build:pages` passed from `source/frontend`; the explicit model-enabled Pages build also emitted its manifest and Wllama runtime. The project-path browser smoke was listed but local Chromium failed to launch with `spawn EPERM`, so no new browser pass is claimed.
- August 4 frontend unit verification: `npm run test:unit` passed 17 tests, covering 9 browser-model cases, 3 build-policy cases, 2 shared request-gate cases, and 3 agent-bus boundary cases.
- Prior August 4 enabled hosted model verification: `npm run test:hosted:model:build` fetched the pinned 219 MB artifact, reached local-ready state, and generated a local response with no backend/API/WebSocket traffic. This remains an opt-in local proof; the Pages artifact stays model-disabled pending licensing, and the current single-thread mobile path still needs a fresh device run.
- August 4 Pages artifact audit: the default `dist-pages` contains no model manifest, Wllama chunk, model WASM, or Hugging Face URL; the deployed-static harness checks the same absence on the public origin. The managed browser lane remains unavailable locally because Chromium launch returned `spawn EPERM`.
- August 4 live-origin harness: implemented but not confirmed against a public deployment in this local pass; it fails closed without `HOSTED_PAGES_URL`, retains listeners safely, and records model transfer bytes plus disk/service-worker/prefetch cache provenance across two model/chat passes when supplied.
- August 4 default browser verification: `npm run test:e2e` reran with `108 passed, 6 skipped` and no failures; the two release-only Pages specs are excluded from the port-owning default config, while the long tutorial case completed in `6.4m`.
- August 4 Mission Control QA verification: the focused `qa_verification.spec.ts` suite passed `27` tests against direct Windows venv servers, including the persisted one-acquisition default, replay/agent flows, responsive shell, and area tools. The repo-local uv shim is now restored; no new browser QA pass is claimed because managed Chromium launch still returns `spawn EPERM`.
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
- Current context-bank audit: one compact default orientation route expands to 111.1 KB across 67 groups; focused active routes have no missing references, broad groups, or advisory budget overages, and large binary/media payloads stay out of those routes.
- Historical run-by-run details live in `summary_bank.json`; keep this section limited to the latest release-relevant validation state.
