# TODO

Updated **April 29, 2026**.

This is the canonical backlog and integrity note. Keep detailed history in `summary_bank.json` and focused docs; keep this file oriented around current state, active gaps, and edge cases.

## Current App State

- LFM Orbit is a demo-ready, local-first mission-control prototype, not an unattended production deployment.
- The hackathon runtime is built around DPhi Space SimSat (`simsat_sentinel`). Direct Sentinel Hub, NASA, and GEE-style providers are optional development/replay support and must not become judge-path dependencies.
- Mission Control can run realtime provider/API scans, replay cached real API imagery, monitor previews, VLM helper calls, timelapse generation, and dataset export paths.
- Runtime evidence surfaces expose three separate fields: `runtime_truth_mode` (`realtime`, `replay`, `fallback`), `imagery_origin` (`sentinelhub`, `simsat`, `nasa_gibs`, `gee`, `cached_api`, etc.), and `scoring_basis` (`multispectral_bands`, `proxy_bands`, `visual_only`, `fallback_none`).
- Replay-cache entries are stored real API imagery with preserved date/provenance for deterministic review and cost control. They are not generated evidence.
- The first `ice_snow_extent` lane scores cached Sentinel-2 L2A replay metadata with NDSI, SCL cloud rejection, snow/ice SCL support, water/ice ambiguity flags, and multi-frame persistence.
- Fallback means degraded runtime behavior: provider error, quality gate, heuristic proxy, or VLM compatibility fallback. Fallback paths must not masquerade as realtime imagery or high-confidence model output.
- Fast Replay can load curated replay packs and structurally valid cached API WebMs, then rescan saved metadata through the current runtime/model stack.
- Fast Replay excludes cached WebMs that fail structural timelapse-integrity checks, so static or color-shift-only videos are not presented as temporal proof.
- NDVI and NDSI have explicit spectral-band contracts: RGB-only, missing, or invalid band data returns unavailable/abstain instead of fabricated indices.
- Cloud and no-data coverage are hard quality gates: SCL metadata is used when available, cloudy cached frames are skipped, and cloud-blocked scoring windows return no-transmit quality-gate results.
- VLM responses now carry structured provenance with output source, model, fallback reason, runtime truth mode, imagery origin, and scoring basis.
- Judge Mode proof JSON now includes `payload_accounting` so byte-reduction claims state which fields are counted and which proof artifacts are excluded.
- Local control endpoints are guarded for localhost use, and default CORS is a localhost allowlist unless overridden.
- Dataset export and retagging can carry cached replay timelapses into local ImageFolder-style training data; the current bounded Qwen/Ollama cycle is published to `Shoozes/LFM-Orbit-SatData`.

## Recent Integrity Pass

- [x] Split runtime metadata into `runtime_truth_mode`, `imagery_origin`, and `scoring_basis` across provider status, health, telemetry, metrics, recent alerts, replay, timelapse, VLM provenance, and frontend normalization.
- [x] Standardized the primary active-provider truth label as `realtime` while preserving backward compatibility for old stored rows and source labels.
- [x] Kept replay/cached API evidence labeled as `replay` with `imagery_origin=cached_api`; visual replay defaults to `scoring_basis=visual_only`, while band-derived replay manifests can explicitly use `scoring_basis=multispectral_bands`.
- [x] Changed cached timelapse provenance to `kind=replay_cache`, `label=Cached real API timelapse`, and `legacy_kind=seeded_cache`.
- [x] Applied a structural timelapse-integrity gate to dynamic Fast Replay catalog entries, excluding the legacy static Greenland WebM while keeping metadata-only cryosphere scoring available.
- [x] Added the first ice/snow evidence lane with NDSI, SCL cloud rejection, water/ice ambiguity flags, multi-frame persistence, API tests, replay/export provenance, and an Ice/Snow Mission Control preset.
- [x] Ensured provider failures and quality-gate failures produce zero-score/zero-confidence fallback or no-transmit results instead of forced positive alerts.
- [x] Updated frontend labels to distinguish realtime provider fetches, replay caches, cached API imagery, and fallback/proxy paths.
- [x] Added explicit Judge Mode payload-accounting metadata and proof assertions so `alert_payload_bytes` is scoped to compact downlink JSON, not the larger proof artifact envelope.
- [x] Cleaned stale public-facing replay wording in Inspect, Alerts, Mission replay notices, tutorial subtitles, dataset-card notes, and replay/timelapse runtime dialogue.
- [x] Re-scanned repo-local TODO/FIXME/stub/incomplete markers; remaining hits are intentional UI placeholders, test fixtures, compatibility labels, optional fallback paths, or backlog items tracked here.
- [x] Consolidated progress tracking so `README.md` stays judge-facing, `docs/ARCHITECTURE.md` stays system-facing, `docs/DATASET_CYCLE_TUTORIAL.md` stays workflow-facing, and this file stays backlog-facing.
- [x] Confirmed NM-UNI's role from `C:\DevStuff\NM-UNI-main`: it is the external Orbit dataset-import, Liquid training, GGUF quantization, `orbit_model_handoff.json`, and optional Hugging Face model-publish lane. Orbit should consume that handoff; it should not absorb NM-UNI's training UI/runtime.
- [x] Added `runtime-data/monitor-reports/` persistence for API-generated maritime and lifeline monitor reports, plus API/listing tests.
- [x] Added replay snapshot export/import for completed runtime surfaces so realtime or replay missions can be packaged outside bundled replay manifests and cached API WebMs.
- [x] Added `orbit_training_contract_v1` to exported samples, including operator-review, localization, evidence, and NM-UNI import metadata.
- [x] Rasterized SVG fallback context thumbnails to PNG during dataset export so future Qwen/Ollama cycles receive image assets instead of unsupported SVG placeholders.
- [x] Expanded `scripts/evaluate_model.py` into `orbit_eval_v2` with independent label-source handling, base-vs-candidate comparison, thresholds, and `promotion.json` artifacts.
- [x] Added `scripts/smoke_satellite_model.py` for manifest-resolved GGUF smoke checks when an NM-UNI handoff bundle is actually installed.
- [x] Added backend smoke coverage that keeps `simsat_sentinel` first in the provider fallback chain.
- [x] Deprecated user-facing use of `demo_mode_enabled`: current matches are backend metrics/contracts/types compatibility fields, not data-source labels shown as evidence.

## Active Backlog

- No unblocked hackathon-path backlog remains in this file. The current judge path is DPhi SimSat-first, replay-safe, dataset-exportable, and locally verifiable.

## Blocked External Artifact Lane

- [ ] After NM-UNI exports a real Orbit bundle, fetch it with `scripts/fetch_satellite_model.py`, then run `python scripts\smoke_satellite_model.py --require-present` from `source/backend`.
- [ ] Add a production image-conditioned satellite inference adapter that consumes the fetched `GGUF + mmproj` artifacts. This should extend the manifest contract instead of adding hardcoded model paths.
- [ ] Replace VLM VQA/caption compatibility fallbacks with explicitly supported on-device implementations once the selected local runtime and model family are fixed.

## Time-Gated Watch

- [ ] After `2026-04-29T18:00:00Z`, verify the SPC Southern High Plains fire-weather watch against FIRMS/NIFC and only promote it from `watch_only_unverified` if independent detections or incident reports exist inside the bbox.

## Parked Post-Hackathon Ideas

- Sentinel Hub replay seeding manifests, live Sentinel Process API ice/snow summaries, OGC/WMS instance-id support, and refreshed Greenland contextual WebM proof.
- Planet/Planet Insights ingestion, broader Element84 STAC fixture work, and other non-SimSat direct-provider expansion.
- True H3 grid generation, a custom temporal-use-case editor, and Depth Anything V3 promotion into live alert scoring.
- Responsive/mobile Playwright coverage for the fixed right rail and Judge Mode panel.
- Lightweight frontend unit/component tests for hooks such as `useMapPins`, telemetry normalization, and settings retry behavior.

## Edge Cases To Keep Covered

- Replayed cached API imagery must be labeled as `runtime_truth_mode=replay`, not as a run-context or fallback label.
- Realtime provider paths must include the provider/API family through `imagery_origin`; avoid vague standalone "live" labels in evidence surfaces.
- Fallback paths must carry fallback provenance and must not produce high-confidence positive alerts from provider errors, quality-gate failures, or heuristic-only VLM output.
- Empty or malformed provider credentials must report unavailable status without switching to external calls unexpectedly.
- Cloudy, stale, missing, RGB-only, or non-numeric spectral inputs must abstain rather than fabricate spectral indices.
- Quality-gated cloud/no-data failures must not emit `suspected_canopy_loss`, even when raw band deltas look large.
- Cached replay/training frames must carry frame-quality metadata and reject cloudy frames before WebM creation.
- Timelapse evidence must contain multiple contextual satellite imagery slices; single still-image color shifts are invalid temporal evidence.
- Dynamic Fast Replay must not list cached videos that fail structural frame-change checks, even when matching metadata exists.
- Ice/snow conclusions must require spectral bands and temporal persistence; RGB-only snow/cloud lookalikes should abstain or stay metadata-only.
- Link-offline mode must queue compact JSON alerts locally and flush only after link recovery.
- Payload-reduction proof must keep `payload_accounting` explicit so screenshots, videos, traces, and UI-only audit fields are not confused with downlink alert bytes.
- Demo and test runs should reset runtime state and avoid stale local server reuse unless explicitly requested.
- Recorded demos must preload their intended mission or replay before opening the browser; a generic default scan at video start is a regression.
- Map-action tests should use app readiness signals and shared helpers before touching the canvas; fixed sleeps are only acceptable for intentional visual/video pacing.
- Opt-in debug tests should write extra diagnostics to artifacts rather than polluting normal test output.
- Benign browser disconnect noise should stay out of demo logs; real websocket and backend exceptions should still be logged.
- Future-watch manifests must stay timestamped, source-backed, and unverified until post-window evidence exists; do not turn risk outlooks into claimed detections.
- Operator-visible errors should remain visible for mission validation, VLM actions, Ground Agent chat, agent-bus injection, timelapse generation, map-pin sync, and settings status.
- Periodic mission refresh failures should leave debug diagnostics so stale mission state can be investigated during local demo runs.

## Verification Notes

- Fast broken-import/export guard: `python -m pytest source/backend/tests/test_import_contracts.py`.
- Full backend guard: `python -m pytest source/backend/tests`.
- Frontend contract guard: `npm run lint` and `npm run build` from `source/frontend`.
- Judge acceptance path: `npm run demo:judge` from `source/frontend`.
- Full local validation remains `.\run.ps1 -Verify` from repo root.
- Latest integrity validation: cold-start `.\run.ps1 -Verify` passed with backend `305 passed`, frontend lint/build passing, and normal Playwright E2E `73 passed`, `1 skipped`; focused replay/export/timelapse checks passed `14`; Ice/Snow preset Playwright check passed `1`; focused Playwright replay/timelapse specs passed `5`; QA verification passed `8`; `npm run demo:judge` passed; `npm run demo:tutorial` passed and refreshed `docs/tutorial_video.webm`; `summary_bank.json` parsed; `uvx ruff check source/backend --select E9` passed; `git diff --check` reported only CRLF normalization warnings.
- Latest dataset-cycle validation: dataset export produced `56` current-cycle samples, `24` replay-cache rows, and `25` timelapse rows; bounded Qwen retag produced `179` assets and `26` temporal sequences with `74` reused image tags, `9` historical SVG placeholder skips, and zero tagger failures. New exports rasterize SVG fallbacks to PNG before retagging.
- Hugging Face remote config verification: `default=179`, `temporal_sft=26`, `asset_metadata=179`, `retagged_assets=179`, `temporal_metadata=26`, `review_queue=179`, `mission_metadata=1`; latest data/card commit `1ebd19065e8a8124372425c4c0df9c0332275c9c`.
- Latest focused backend validation after backlog closure: `python -m pytest source/backend/tests/test_api.py source/backend/tests/test_replay.py -q` -> `55 passed`; `python -m pytest source/backend/tests/test_export_orbit_dataset.py source/backend/tests/test_evaluate_model.py source/backend/tests/test_model_manifest.py source/backend/tests/test_import_contracts.py -q` -> `17 passed`.
