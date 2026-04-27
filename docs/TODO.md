# TODO

Updated **April 27, 2026**.

## Completed This Pass

- [x] Fixed GitHub Actions frontend install failure by refreshing `source/frontend/package-lock.json` with the CI Node/npm lane; `source/frontend` now passes `npm ci` under Node `20.19.0` and npm `10.8.2`.
- [x] Reworked the root README opening into a visual proof, purpose, capabilities, and quick-start story with direct operator-facing details.
- [x] Replaced stale README-facing screenshots in `docs/` and added lifeline, maritime, timelapse, and VLM proof images from the Playwright capture set.
- [x] Corrected the maritime proof path so the screenshot uses the Suez/channel target map context and maritime task text instead of appearing over the default forest replay map.
- [x] Re-ran `.\run.ps1 -Verify`: backend tests, frontend typecheck/build, and Playwright E2E all pass.
- [x] Split the frontend bundle, lazy-loaded major panels, and cleared the old Vite large-chunk warning.
- [x] Added manifest-based satellite model resolution plus `fetch_satellite_model.py` so Orbit can consume local bundle or Hugging Face artifacts without a hardcoded GGUF path.
- [x] Surfaced manifest and repo metadata through `/api/inference/status` and `/api/analysis/status`.
- [x] Replaced the gallery's first offline thumbnail fallback with seeded local timelapse-frame extraction before dropping to the SVG placeholder.
- [x] Added gallery regression coverage for cached-frame and SVG fallback behavior.
- [x] Switched long-lived agent runtime code to `asyncio.get_running_loop()`.
- [x] Replaced several silent cache/credential/websocket failure paths with debug logging while preserving non-fatal fallbacks.
- [x] Tightened bbox/date validation across mission start, analysis timelapse, timelapse generation, VLM helper, and imagery-cell APIs so malformed inputs fail before scan/provider work starts.
- [x] Added shared `core/grid.py` bbox and cell-id validation coverage.
- [x] Made timelapse `steps` bound monthly provider fetches instead of being only an API compatibility field.
- [x] Retired the stale standalone `source/backend/autonomous_agent.py` prototype behind a clear non-running shim.
- [x] Added regression tests for invalid bboxes, reversed date windows, unsupported imagery cell IDs, bounded timelapse steps, mission-mode validation, and the retired agent shim.
- [x] Fixed validation exports so downloaded timelapse assets keep the correct container extension instead of being mislabeled as `.mp4`.
- [x] Added a first-pass Orbit dataset export script for recent alerts plus local gallery evidence at `source/backend/scripts/export_orbit_dataset.py`.
- [x] Added a first-pass baseline eval harness at `source/backend/scripts/evaluate_model.py` for replaying exported samples through `offline_lfm_v1`.
- [x] Expanded Orbit dataset export to materialize context thumbnails for image-backed alert rows and include recent ground-agent rejects as weak negative/control samples.
- [x] Added a seeded replay mission path that hydrates Mission/Logs/Inspect/Agent Dialogue from bundled local evidence for judge walkthroughs and deterministic review.
- [x] Added a central runtime reset helper plus `/api/runtime/reset` so app boot, replay loading, backend tests, and Playwright fixtures all reset the same mutable stores.
- [x] Repointed selected screenshot/tutorial demo flows at the seeded replay path and added shared Playwright runtime helpers to reduce repeated setup logic.
- [x] Tightened observation-store readiness so records are only marked `training_ready` after both satellite and ground observations exist.
- [x] Corrected runtime-mode summary truth so imagery-backed scoring flags match the stricter provider rules used elsewhere in config.
- [x] Stopped the debug HTML dump spec from writing artifacts into the frontend repo root.
- [x] Refreshed `README.md`, `docs/ARCHITECTURE.md`, and `summary_bank.json` so current state, backlog, and grouping match the validated repo.
- [x] Added `core/temporal_use_cases.py` so temporal missions and exports can auto-classify deforestation, wildfire, maritime, ice-cap growth, flood, crop, urban, mining, and generic temporal-review tasks.
- [x] Extended Orbit dataset export to emit enriched sample JSONL plus chat-style `training.jsonl` files with temporal examples and API-prep metadata.
- [x] Added an API observation-store export lane for cached provider data so raw API-derived observations can be auto-prepped into the modeling bundle.
- [x] Promoted SimSat Mapbox from client-only support into provider config, loader routing, status APIs, imagery labels, settings UI, and tests.
- [x] Added repo-root `.env.example` plus launcher `.env` loading for reproducible cold-start provider/model configuration.
- [x] Trimmed the README into a GitHub-facing cold-start, provider, custom-training-data, and validation guide.
- [x] Added a WebGL depth-map summary utility with CPU fallback for the future image-conditioned depth-verification lane.
- [x] Added backend import-contract coverage for core modules, API entrypoints, and supported scripts so broken imports/exports fail fast in pytest.
- [x] Hardened SimSat timeout parsing so malformed or non-positive `SIMSAT_TIMEOUT` values fall back safely instead of breaking status checks.
- [x] Made Playwright dev-server reuse explicitly opt-in with `PLAYWRIGHT_REUSE_SERVER=1` and reset runtime state in replay/metrics specs to avoid stale local state leakage.
- [x] Consolidated progress tracking around `README.md`, `docs/ARCHITECTURE.md`, `docs/TODO.md`, and `summary_bank.json`.
- [x] Added install-only and verify modes to the cross-platform launchers so setup, startup, clean reset, and full validation are scriptable from repo root.
- [x] Fixed the PowerShell launcher to stop its backend child process when the frontend dev server exits.
- [x] Updated GitHub/Copilot setup metadata to use the locked `uv` backend environment instead of ad hoc package installs.
- [x] Smoke-tested `.\run.ps1 -Run` by verifying backend health and Vite startup from a clean local port state.
- [x] Added Orbit-native maritime monitoring primitives: optional Element84 Sentinel-2 STAC metadata search, date deduplication, N/E/S/W investigation planning, API endpoint, and tests.
- [x] Added civilian lifeline before/after monitoring primitives: seeded assets, strict candidate validation, safe `discard` fallbacks, `downlink_now` policy, API endpoints, eval metrics, and tests.
- [x] Tightened lifeline before/after integrity so `downlink_now` requires distinct baseline/current frame evidence, and empty eval payloads fail validation instead of returning misleading metrics.
- [x] Added optional dataset-export ingestion for persisted maritime/lifeline monitor-report JSON files through `--monitor-reports-dir`, with sample JSONL and training JSONL coverage.
- [x] Added Mission-tab monitor preview cards for maritime and lifeline workflows plus Playwright visual proof screenshots and API contract coverage.
- [x] Tightened model-handoff and eval-harness wording so tracked runtime gaps live in this canonical backlog instead of scattered follow-up notes.
- [x] Added rejection-reason observability so QC/runtime rejects now persist `runtime_rejections_by_reason` and low-valid-coverage rates instead of only aggregate reject percentages.
- [x] Normalized scanner QC failures such as `Scene Quality Rejected: Insufficient Valid Pixels` into stable metrics reason codes.
- [x] Added backend coverage for metrics rejection reasons, scanner rejection normalization, VLM image-fetch fallback behavior, and health/metrics contract alignment.
- [x] Updated Mission Control to show client/API validation details instead of collapsing all launch failures into a generic backend-unreachable message.
- [x] Added Playwright coverage for reversed mission date validation and kept bbox assignment coverage on the current context-menu workflow.
- [x] Changed VLM image fetch failure behavior to return deterministic fallback answers instead of passing blank fabricated tiles into optional pipelines.
- [x] Aligned backend health/metrics contracts with frontend telemetry types, including demo-mode and observability fields.
- [x] Surfaced observability rejection breakdowns in the Logs tab so operators can see scene rejects, low-valid-coverage rate, and top rejection reasons without opening raw metrics JSON.
- [x] Added decision-gate output for QC rejection breakdowns and separated low-valid-coverage optical blockage from other high-rejection states.
- [x] Tightened timelapse viewer error handling so `format: none` API payloads render a retryable operator error instead of an empty video surface.
- [x] Added focused backend and Playwright coverage for decision-gate QC output, Logs-tab pipeline integrity, and timelapse API error rendering.
- [x] Consolidated tutorial/demo Playwright subtitle, highlight, and map-drawing helpers, and moved the dual-agent tutorial onto the visible seeded-replay path for deterministic recordings.
- [x] Added shared basemap-readiness waits to judge screenshot, monitor-preview, and VLM visual specs so captures do not freeze partially loaded map tiles.
- [x] Polished Mission-tab composition so VLM/timelapse auxiliary panels mount directly below a compact mission section instead of below empty sidebar space.
- [x] Added explicit VLM `Find` and `Ask` controls plus inline error rendering for grounding, VQA, and caption failures.
- [x] Replaced console-only map agent-evaluation failures with best-effort agent-bus error messages for operator visibility.
- [x] Hardened Playwright map context-menu setup with a canvas-relative retry helper that avoids live scan marker interception.
- [x] Added a keyboard/touch-friendly `Map Actions` button that opens the same spatial options at map center and covered it with Playwright.
- [x] Added optional Depth Anything V3 support: env/runtime toggle, `/api/depth/status`, `/api/depth/settings`, `/api/depth/estimate`, Settings UI status, documented `da3-large` default, auto device resolution, and dependency-free fallback tests.
- [x] Gated the debug HTML dump spec behind `PLAYWRIGHT_DUMP_HTML=1`, kept dumps under Playwright test output, and left browser-console echo opt-in with `PLAYWRIGHT_DUMP_HTML_LOGS=1`.
- [x] Regenerated judge-facing screenshot artifacts and checked the PNG outputs for expected dimensions and nonblank luminance ranges.
- [x] Re-reviewed actionable `TODO`/`FIXME`/stub-style markers; remaining hits are canonical docs references, input placeholders, test fixtures, or explicitly tracked safe fallback paths.
- [x] Reordered Depth Anything V3 estimate validation so malformed image payloads fail before optional model loading, with API/unit regression coverage.
- [x] Hardened LFM tool-call parsing for nested fenced JSON arguments and added parser regression coverage.
- [x] Replaced additional silent fallback paths with debug diagnostics for secrets-file reads, observability persistence, GIBS timelapse candidate fetches, and corrupt observation-store records.
- [x] Converted root-level Sentinel Hub WMS probe files into safe manual entrypoints with env-only credentials and import-contract coverage.
- [x] Replaced remaining script-level silent suppressions in model fetch, NASA seed, and GEE auth helpers with explicit suppress/debug/return paths.
- [x] Added the button-driven `Map Actions` path as the final fallback in the shared Playwright context-menu helper after a full-suite run exposed one marker/layer interception edge case.
- [x] Moved active Mission timelapse evidence above the VLM panel so generated temporal video proof is immediately visible in the right rail.
- [x] Made the timelapse visual proof deterministic by routing the E2E generation call to a seeded WebM and waiting for video readiness before screenshot capture.
- [x] Hardened Settings status loading with per-endpoint retries and made the settings screenshot wait for provider, SimSat, analysis, depth, and basemap readiness before asserting live status.
- [x] Reset agent-bus runtime state and verified the injected agent-evaluation query through `/api/agent/bus/dialogue` before scrolling it into the visual proof screenshot.
- [x] Reused the shared Playwright link-readiness helper in `app.spec.ts` to reduce duplicate E2E timing code.
- [x] Stopped Map Actions overlay clicks from bubbling into the map click handler, which could immediately close the spatial menu in the full E2E run.
- [x] Promoted retryable app navigation into shared Playwright runtime helpers and moved all E2E specs onto `gotoApp`.
- [x] Surfaced Agent Dialogue bus stats and operator-injection failures inline instead of silently swallowing non-OK or unreachable bus responses, with Playwright coverage for both failure paths.
- [x] Sharpened Ground Agent assistant failures so backend error payloads render inline, timed-out requests are labeled distinctly, and empty/loading sends are disabled.
- [x] Added Playwright coverage for Ground Agent backend-error rendering.
- [x] Tightened map-driven Agent Video Evaluation so bus injection and timelapse-analysis non-OK responses become agent-bus error notes instead of silent no-ops.
- [x] Changed Inspect timelapse fallback copy from an active generating state to a clearer pending/unavailable state when a gallery row has no video payload.
- [x] Made `.env.example` default to `DISABLE_EXTERNAL_APIS=true` so copied cold-start configs avoid live API calls and provider quota unless explicitly enabled.
- [x] Verified the repo-root `.\run.ps1 -Verify` path, including locked dependency sync, Playwright Chromium install, backend tests, frontend lint/build, and full E2E.
- [x] Smoke-tested copied `.env.example` with `.\run.ps1 -InstallOnly` and a bounded `.\run.ps1 -Run` startup check against backend health plus the Vite index.
- [x] Surfaced gallery and timelapse provenance through API payloads and operator UI labels so evidence is distinguishable as live fetch, seeded cache, replay, provided asset, or offline fallback.
- [x] Added standalone dataset asset retagging via `scripts/retag_training_assets.py`, with SHA-256 dedupe, Ollama/OpenAI-compatible provider hooks, Hugging Face ImageFolder output, sampled timelapse frames, and ordered temporal sequence JSONL.
- [x] Added optional Tkinter wrapper `scripts/retag_training_assets_ui.py` so operators can run retagging with directory pickers, provider/model controls, and a live log while preserving the CLI as source of truth.
- [x] Added the Tkinter retagging screenshot to the root README and data README.
- [x] Hardened map pins with backend coordinate validation, bounded frontend fetches, operator-visible sync errors, and Playwright coverage for API failure visibility.
- [x] Replaced MapLibre marker-label `innerHTML` rendering with DOM text nodes so agent/operator pin labels cannot inject markup.
- [x] Expanded import-contract coverage to include seed-data scripts, GEE auth, the edge starter, and the optional satellite debug dashboard.
- [x] Added satellite-debug dashboard render sanitization coverage and escaped server-side message IDs/timestamps before HTML insertion.
- [x] Prevented map-pin success and error toasts from stacking over each other after failed pin sync.
- [x] Consolidated the root README integrity notes into a shorter current-state baseline, leaving detailed progress history in this TODO file.

## Active Backlog

- [ ] Add a production image-conditioned satellite inference adapter that consumes `GGUF + mmproj` artifacts instead of score-only prompt context.
- [ ] Replace VLM VQA/caption compatibility fallbacks with explicitly supported on-device implementations for the current local runtime.
- [ ] Add a model-present smoke path that validates manifest-resolved GGUF loading separately from fallback-only default runs.
- [ ] Add replay snapshot export/import so completed missions can be packaged outside the bundled seeded manifest set.
- [ ] Add a second seeded replay pack so deterministic demo/test coverage spans more than one mission style.
- [ ] Add mocked SimSat Mapbox fixture coverage for provider selection, credential status, imagery labels, and operator-facing provenance.
- [ ] Add mocked Element84 STAC fixture coverage with visual asset URLs and a seeded maritime replay pack.
- [ ] Expand the dataset export from weak negatives into a full training contract with operator-reviewed controls and stronger localization labels.
- [ ] Persist API-generated maritime/lifeline monitor reports into a runtime report directory so `--monitor-reports-dir` can be populated directly from UI/API usage.
- [ ] Add UI controls for selecting and previewing temporal use cases before mission launch.
- [ ] Add responsive/mobile layout coverage for the fixed right mission rail so smaller operator displays can still inspect evidence without overlap.
- [ ] Add a lightweight frontend unit/component harness for hooks such as `useMapPins` so timeout/error behavior can be tested without starting the full Playwright stack.
- [ ] Expand the first-pass eval harness into a true base-vs-tuned benchmark lane with independent labels and promotion thresholds.
- [ ] Feed Depth Anything V3 depth summaries into alert evidence/eval scoring and add a model-present smoke test on a runner with DA3 artifacts installed.
- [ ] Replace the current square-grid compatibility layer with true H3 parsing/generation before production geospatial scale-out.

## Wrap-Up Order

The remaining work is now mostly the modeling lane, not general app integrity.

1. Expand the new dataset export path so confirmed/rejected alerts can be handed to external training workflows in a reproducible format.
2. Expand the new baseline eval harness into a base-vs-tuned comparison lane and persist run artifacts before changing live runtime behavior.
3. Add the real image-conditioned `GGUF + mmproj` or equivalent local adapter for tuned-model inference.
4. Add model-present smoke tests and a promotion gate so trained artifacts are validated before live use.
5. Surface tuned-model provenance and comparison output in the existing UI.

## Review Notes

- No broken frontend imports/exports were found after lint, build, and the full Playwright suite.
- No broken backend imports surfaced under the full backend test run, and import contracts now have dedicated pytest coverage.
- No actionable repo-local `TODO`/`FIXME`/stub markers were found outside intentional test fixtures, input placeholders, documented fallback paths, and this canonical backlog.
- Full validation on April 27, 2026 is green: `240` backend tests, `npm run lint`, `npm run build`, and `69` Playwright specs with `1` debug-only HTML dump skipped by default.
- Repo-root validation on April 27, 2026 is green: `.\run.ps1 -Verify` completes the locked install and full test path from repo root.
- Judge screenshot artifacts under `source/frontend/e2e/screenshots/` regenerated at `1440x900`; nonblank luminance checks passed, with the darker satellite-debug dashboard expected.
- Screenshot contact-sheet review passed for the current visual set: settings shows live provider/model status, timelapse shows a real video frame plus extracted-frame count, and agent-evaluation shows the operator query on the dialogue bus.
- Playwright now starts fresh local web servers by default; set `PLAYWRIGHT_REUSE_SERVER=1` only when intentionally reusing already-running servers.
- Context-menu and VLM visual specs now share canvas-relative helpers so live map markers do not make tests depend on a fragile viewport-center click.
- The map has both right-click and button-driven spatial action paths; the shared test helper now falls back to the button path, the button is disabled until MapLibre layers are ready, and Escape closes the menu.
- Playwright app navigation retries are now shared across all E2E specs through `source/frontend/e2e/runtime.ts`.
- Agent Dialogue now exposes bus stats/injection failures in the panel so operator commands do not fail silently.
- Ground Agent assistant failures now preserve API error payloads in the chat transcript, and its send control disables during empty/loading states.
- Map-driven Agent Video Evaluation now checks non-OK bus and timelapse-analysis responses and routes failures back through the agent bus.
- Map pin sync now has bounded frontend fetches, visible API failure copy, coordinate validation, and safe marker-label DOM rendering.
- Inspect timelapse fallback text no longer implies an active generation job when the gallery only has partial evidence.
- Copied cold-start `.env` files now stay offline-safe by default; direct Sentinel/NASA/GEE provider use should set `DISABLE_EXTERNAL_APIS=false` alongside credentials.
- Depth Anything V3 is optional and disabled by default; the Settings toggle changes the current backend process only and reports missing `depth_anything_3` dependencies without failing app startup.
- Repo-root verification is available through `.\run.ps1 -Verify` or `./run.sh --verify`.
- The repo-root launcher start path was smoke-tested after copying `.env.example`; no listeners were left on ports `8000`, `8080`, or `5173`.
- Remaining placeholder/fallback behavior is intentional and currently limited to safe offline paths:
  - `core/inference.py`: non-fatal response when the manifest-resolved GGUF model is not installed.
  - `core/vlm.py`: deterministic offline assist responses when optional vision pipelines are unavailable.
  - `core/gallery.py`: final SVG chip only after ESRI and seeded-cache thumbnail fallbacks both fail.
