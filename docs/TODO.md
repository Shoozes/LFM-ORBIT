# TODO

Updated **April 28, 2026**.

This is the canonical backlog and integrity note. Keep completed history out of this file unless it changes current operating guidance.

## Current App State

- Mission Control can run live scans, deterministic seeded replay, monitor previews, VLM helper calls, timelapse generation, and dataset export paths.
- Mission Control now has Fast Replay for curated replay packs and every valid seeded-cache WebM, plus a rescan action that reruns prior replay metadata through the current runtime/model stack.
- Judge Mode now provides a deterministic Playwright demo lane with video, trace, screenshots, proof JSON, payload-reduction evidence, provenance, abstain behavior, and link-outage recovery.
- Runtime reset, replay loading, provider fallback, queue/gallery/bus persistence, and Playwright navigation helpers are shared instead of duplicated per test.
- Direct Sentinel Hub seeding supports `.tools/.secrets/sentinel.txt`, `.tools/.secrets/sh.txt`, or environment variables; the current labeled `API` / `CLIENTID` / `CLIENT` `sh.txt` shape validates against Sentinel Hub Process API OAuth.
- NDVI now has an explicit spectral-band contract: RGB-only or invalid band data returns unavailable/abstain instead of fake NDVI.
- Cloud and no-data coverage are hard quality gates: Sentinel SCL cloud/shadow/cirrus classes are tracked, cloudy seeded frames are skipped, and cloud-blocked scoring windows return no-transmit quality-gate results.
- Dataset export and retagging can carry real seeded Sentinel-2 timelapses into local ImageFolder-style training data; the current bounded Qwen/Ollama pass retags representative images and falls back deterministically for the rest; Hugging Face upload is published to `Shoozes/LFM-Orbit-SatData`.

## Completed Current Pass

- [x] Added judge-ready Playwright demo config, demo scripts, demo specs, visual overlay hooks, proof JSON export, and Judge Mode UI.
- [x] Added deterministic payload-reduction, provenance, abstain-safety, and orbital-eclipse demos.
- [x] Added backend link-state endpoints for outage/recovery demos and included reset-state cleanup.
- [x] Added spectral-band contract coverage for explicit NIR/Red NDVI requirements.
- [x] Added `.tools/.secrets/sh.txt` compatibility for Sentinel Hub credentials without logging secret values.
- [x] Added labeled Sentinel Hub trial-bundle parsing for `API`, `CLIENTID`, and `CLIENT` lines.
- [x] Added `--skip-vlm-metadata` to Sentinel Hub cache seeding so replay imagery can be refreshed without forcing local metadata inference for every cell.
- [x] Added Sentinel-2 L2A seeded mission timelapses for Pakistan Manchar Lake flood, Atacama mining, Greenland ice-edge abstain, and Suez maritime demos.
- [x] Hardened recorded demo videos against static or too-short captures by using seeded WebM evidence, minimum-duration checks, sampled-frame uniqueness checks, and a backend seeded-timelapse integrity test.
- [x] Kept replay proof-panel playback inside a clearer evidence window so the final Judge Mode screenshot does not land on cloud-obstructed frames while still rendering the seeded WebM.
- [x] Added a Playwright proof-frame artifact and luminance guard for every recorded demo so blank or washed-out final evidence panels fail the demo run.
- [x] Reworked recorded demos into tutorial-style UI flows with subtitles: Rondonia Judge replay, Pakistan flood payload proof, Atacama provenance proof, Greenland abstain safety, Suez maritime eclipse recovery, and a refreshed `docs/tutorial_video.webm`.
- [x] Rebuilt the tutorial video as a user-like replay workflow that loads Singapore maritime evidence, analyzes it, replaces it with Atacama mining evidence, and opens Judge Mode on the active replay instead of defaulting to Rondonia.
- [x] Added visible local satellite frames for Pakistan flood, Atacama, Greenland, and Suez demos so mission-preset demos do not fake timelapses.
- [x] Preloaded recorded demo missions/replay before browser telemetry connects and disabled the boot-time live agent pair for demo runs, so videos do not open on the legacy Amazonas sweep.
- [x] Added seeded-cache export, HF upload helper, and optional HF upload controls in the Tkinter retag UI.
- [x] Added a timestamped future wildfire risk-watch manifest from the NOAA SPC Day 2 fire-weather outlook so later evidence can prove or disprove a post-window catch without retroactive claims.
- [x] Consolidated progress docs so `README.md` stays judge-facing for the Liquid AI x DPhi Space Hackathon, while architecture, backlog, demo, and handoff details live in focused docs.
- [x] Re-reviewed repo-local TODO/FIXME/stub markers; remaining hits are intentional UI placeholders, test fixtures, or tracked backlog items.
- [x] Tightened Playwright map-action timing by replacing several fixed sleeps with shared basemap readiness checks.
- [x] Moved opt-in HTML dump console capture into Playwright artifacts instead of stdout noise.
- [x] Removed the empty SimSat client exception body left by the repo-wide stub scan.
- [x] Hardened cloud handling so SCL QC records cloud/no-data ratios, Sentinel seeded frames are skipped when quality fails, low-quality score windows zero effective change score, and scanner cloud/QC exceptions cannot force demo anomalies.
- [x] Added a narrow Windows asyncio disconnect-noise filter for benign Playwright WebSocket teardown resets without hiding unrelated backend exceptions.
- [x] Published the retagged satellite dataset to `Shoozes/LFM-Orbit-SatData` and added a Hugging Face dataset card so the Dataset Viewer loads single-image SFT, temporal SFT, metadata, retag, temporal metadata, and review queue files as separate schemas.
- [x] Added new mission replay packs for Manchar flood, Atacama mining, Singapore maritime activity, Georgia wildfire candidate, and Delhi urban expansion.
- [x] Seeded additional Sentinel-2 mission data for Kansas crop phenology, Delhi urban expansion, and Singapore maritime anchorage with cloud/no-data quality gates.
- [x] Verified `Shoozes/LFM-Orbit-SatData` with remote `datasets.load_dataset` streaming/regular loads.
- [x] Re-scanned repo-local TODO/FIXME/stub/incomplete markers; no active code TODOs were found outside intentional UI placeholders, test fixtures, documented compatibility fallbacks, and this backlog.
- [x] Replaced a silent Mission refresh catch with debug diagnostics so API refresh failures are traceable without adding operator UI noise.
- [x] Added Sentinel-2 seeded data-cycle missions for Mauna Loa lava-flow review and Lake Urmia water persistence with cloud/no-data quality metadata.
- [x] Added a `volcanic_surface_change` temporal use case so lava-flow evidence does not collapse into wildfire labeling.
- [x] Added Fast Replay catalog support for dynamic seeded-cache WebMs and a rescan endpoint/UI action for rerunning saved mission metadata after model/runtime updates.
- [x] Added Sentinel-2 temporal data for Black Rock City recurring settlement, Lahaina wildfire recovery, Kakhovka reservoir drawdown, Kilauea summit eruption review, and Lake Mead shoreline recovery; rejected the Mayon candidate instead of forcing cloudy evidence.
- [x] Added retag reuse so already-tagged image hashes are not resent to Qwen/Ollama, while new assets and intentionally regenerated sequences still get current-cycle tags.
- [x] Fixed extracted timelapse frame naming so different samples named `timelapse.webm` cannot overwrite each other during training export.
- [x] Re-exported and retagged the current dataset cycle with Ollama `qwen3.6:27b`: `56` current-cycle samples, `24` seeded-cache rows, `179` assets, `26` temporal sequences, `40` image calls, `6` sequence calls, `74` reused image tags, `9` skipped SVG placeholders, and zero tagger failures.
- [x] Refreshed `Shoozes/LFM-Orbit-SatData` at data commit `5a2798e7d16cd76df08eff3725dcf3ade9340b58` and card commit `60e8ae913f61315740a640c532eb1aa9ae7cfe75`; verified remote streaming loads for all six configs.
- [x] Added `docs/DATASET_CYCLE_TUTORIAL.md` so the seed/export/Qwen/Hugging Face workflow is documented as a repeatable story outside the front README.

## Active Backlog

- [ ] Add a production image-conditioned satellite inference adapter that consumes `GGUF + mmproj` artifacts, not only scored metadata.
- [ ] Replace VLM VQA/caption compatibility fallbacks with explicitly supported on-device implementations for the selected local runtime.
- [ ] Add a model-present smoke path that validates manifest-resolved GGUF loading separately from fallback-only default runs.
- [ ] Expand `scripts/evaluate_model.py` into a base-vs-tuned benchmark lane with independent labels, thresholds, and promotion artifacts.
- [ ] Expand dataset export from weak negatives into a full training contract with operator-reviewed controls and stronger localization labels.
- [ ] Add a versioned update cadence for future `Shoozes/LFM-Orbit-SatData` refreshes.
- [ ] Replace remaining SVG context placeholder outputs with raster thumbnails before dataset export so future Qwen cycles have zero unsupported assets.
- [ ] Add optional Planet/Planet Insights imagery ingestion once a local API token is available; the current shared workspace URL is a browser account page, not an API credential.
- [ ] Persist API-generated maritime/lifeline monitor reports into `runtime-data/monitor-reports/` directly from UI/API usage.
- [ ] Add full replay snapshot export/import so completed live missions can be packaged outside the bundled replay packs and seeded-cache WebMs.
- [ ] Add Sentinel Hub OGC/WMS instance-id seeding support only if a valid WMS-only instance appears; current Process API seeding uses validated OAuth credentials.
- [ ] Add mocked SimSat Mapbox and Element84 STAC fixture coverage with visual asset URLs and operator-facing provenance checks.
- [ ] Add a custom temporal-use-case editor so operators can save preset libraries beyond bundled examples.
- [ ] Add responsive/mobile Playwright coverage for the map, fixed right rail, and Judge Mode panel.
- [ ] Add lightweight frontend unit/component tests for hooks such as `useMapPins`, telemetry normalization, and settings retry behavior.
- [ ] Feed Depth Anything V3 summaries into alert evidence/eval scoring and add a model-present smoke test where DA3 artifacts are installed.
- [ ] Replace the square-grid compatibility layer with true H3 parsing/generation before production geospatial scale-out.
- [ ] Add a reusable Sentinel Hub replay seeding manifest command that refreshes exact replay assets without relying on manual grid/cell-dim selection.
- [ ] After `2026-04-29T18:00:00Z`, verify the SPC Southern High Plains future fire watch against FIRMS/NIFC and only promote it from `watch_only_unverified` if independent detections or incident reports exist inside the bbox.

## Edge Cases To Keep Covered

- Empty or malformed provider credentials must report unavailable status without switching to live calls unexpectedly.
- Cloudy, stale, missing, RGB-only, or non-numeric spectral inputs must abstain rather than fabricate spectral indices.
- Quality-gated cloud/no-data failures must not emit `suspected_canopy_loss`, even when raw band deltas look large.
- Seeded Sentinel demo/training frames must carry frame-quality metadata and reject cloudy frames before WebM creation.
- Timelapse evidence must contain multiple contextual imagery slices; single still-image color shifts are invalid temporal evidence.
- Link-offline mode must queue compact JSON alerts locally and flush only after link recovery.
- Demo and test runs should reset runtime state and avoid stale local server reuse unless explicitly requested.
- Recorded demos must preload their intended mission or replay before opening the browser; a generic default scan at video start is a regression.
- Map-action tests should use app readiness signals and shared helpers before touching the canvas; fixed sleeps are only acceptable for intentional visual/video pacing.
- Opt-in debug tests should write extra diagnostics to artifacts rather than polluting normal test output.
- Benign browser disconnect noise should stay out of demo logs; real websocket and backend exceptions should still be logged.
- Future-watch manifests must stay timestamped, source-backed, and unverified until post-window evidence exists; do not turn risk outlooks into claimed detections.
- Operator-visible errors should remain visible for mission validation, VLM actions, Ground Agent chat, agent-bus injection, timelapse generation, map-pin sync, and settings status.
- Periodic mission refresh failures should leave debug diagnostics so stale mission state can be investigated during local demo runs.

## Verification Notes

- Backend import-contract coverage is the fast broken-import/export guard.
- Frontend `npm run lint` is the fast TypeScript import/export guard.
- `npm run demo:judge` is the acceptance path for the judge proof demo.
- Full local validation remains `.\run.ps1 -Verify` from repo root.
- Current pass validation: `283` backend tests passed; frontend lint/build passed; normal `npm run test:e2e` passed `73` specs with `1` debug-only skip; `npm run demo:record` passed `5` demo specs.
- Current dataset-cycle validation: dataset export produced `56` current-cycle samples, `24` seeded-cache rows, and `25` timelapse rows; bounded Qwen retag produced `179` assets and `26` temporal sequences with `74` reused image tags, `9` SVG placeholder skips, and zero tagger failures.
- Hugging Face remote config verification: `default=179`, `temporal_sft=26`, `asset_metadata=179`, `retagged_assets=179`, `temporal_metadata=26`, `review_queue=179`.
- Focused integrity cleanup validation: SimSat/import-contract pytest passed `16` tests; frontend `npm run lint` passed; `e2e/bbox.spec.ts` passed `3` tests; app Phase 9 map/timelapse Playwright passed `4` tests; `summary_bank.json` parsed; `git diff --check` reported only CRLF normalization warnings.
- Focused cloud-gate/error-noise validation: API, scene QC, scorer, scanner, Sentinel seeding, and dataset-export tests passed `66` tests.
- Latest docs WebMs were sampled into contact sheets and visually checked for distinct Manchar, Atacama, Greenland, Suez, Rondonia, Singapore maritime, and refreshed tutorial scenes. The current `docs/tutorial_video.webm` is `27.60s` with `28` unique 1 FPS sampled frame hashes; the refreshed `docs/judge-mode-demo.webm` is `22.80s` with `23` unique 1 FPS sampled frame hashes.
- Sentinel Hub OAuth with current `.tools/.secrets/sh.txt` returned HTTP `200`; HF auth with current `.tools/.secrets/hf.txt` succeeds as `Shoozes`; the refreshed retagged dataset landed at data commit `5a2798e7d16cd76df08eff3725dcf3ade9340b58` and card commit `60e8ae913f61315740a640c532eb1aa9ae7cfe75`.
- Latest replay/retag/API validation: backend replay and retag tests passed `12` tests; backend import/API guard passed `43` tests; full backend pytest passed `283` tests; frontend `npm run lint` and `npm run build` passed; the focused seeded replay Playwright flow passed and covers Fast Replay plus rescan visibility.
- Latest targeted integrity pass: backend import/replay/export/seeded timelapse tests passed `14` tests; frontend `npm run lint` passed; `npm run demo:judge` passed and regenerated proof JSON with `evidence_frame`; `summary_bank.json` parsed; `git diff --check` reported only CRLF normalization warnings.
