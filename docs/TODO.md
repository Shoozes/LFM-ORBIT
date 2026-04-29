# TODO

Updated **April 29, 2026**.

This is the canonical backlog and integrity note. Keep detailed history in `summary_bank.json` and focused docs; keep this file oriented around current state, active gaps, and edge cases.

## Current App State

- LFM Orbit is a demo-ready, local-first mission-control prototype, not an unattended production deployment.
- Mission Control can run realtime provider/API scans, replay cached real API imagery, monitor previews, VLM helper calls, timelapse generation, and dataset export paths.
- Runtime evidence surfaces expose three separate fields: `runtime_truth_mode` (`realtime`, `replay`, `fallback`), `imagery_origin` (`sentinelhub`, `simsat`, `nasa_gibs`, `gee`, `cached_api`, etc.), and `scoring_basis` (`multispectral_bands`, `proxy_bands`, `visual_only`, `fallback_none`).
- Replay-cache entries are stored real API imagery with preserved date/provenance for deterministic review and cost control. They are not generated evidence.
- Fallback means degraded runtime behavior: provider error, quality gate, heuristic proxy, or VLM compatibility fallback. Fallback paths must not masquerade as realtime imagery or high-confidence model output.
- Fast Replay can load curated replay packs and valid cached API WebMs, then rescan saved metadata through the current runtime/model stack.
- NDVI has an explicit spectral-band contract: RGB-only, missing, or invalid band data returns unavailable/abstain instead of fabricated NDVI.
- Cloud and no-data coverage are hard quality gates: Sentinel SCL cloud/shadow/cirrus classes are tracked, cloudy cached frames are skipped, and cloud-blocked scoring windows return no-transmit quality-gate results.
- VLM responses now carry structured provenance with output source, model, fallback reason, runtime truth mode, imagery origin, and scoring basis.
- Local control endpoints are guarded for localhost use, and default CORS is a localhost allowlist unless overridden.
- Dataset export and retagging can carry cached real Sentinel-2 timelapses into local ImageFolder-style training data; the current bounded Qwen/Ollama cycle is published to `Shoozes/LFM-Orbit-SatData`.

## Recent Integrity Pass

- [x] Split runtime metadata into `runtime_truth_mode`, `imagery_origin`, and `scoring_basis` across provider status, health, telemetry, metrics, recent alerts, replay, timelapse, VLM provenance, and frontend normalization.
- [x] Standardized the primary active-provider truth label as `realtime` while preserving backward compatibility for old stored rows and source labels.
- [x] Kept replay/cached API evidence labeled as `replay` with `imagery_origin=cached_api` and `scoring_basis=visual_only`.
- [x] Changed cached timelapse provenance to `kind=replay_cache`, `label=Cached real API timelapse`, and `legacy_kind=seeded_cache`.
- [x] Ensured provider failures and quality-gate failures produce zero-score/zero-confidence fallback or no-transmit results instead of forced positive alerts.
- [x] Updated frontend labels to distinguish realtime provider fetches, replay caches, cached API imagery, and fallback/proxy paths.
- [x] Re-scanned repo-local TODO/FIXME/stub/incomplete markers; remaining hits are intentional UI placeholders, test fixtures, compatibility labels, optional fallback paths, or backlog items tracked here.
- [x] Consolidated progress tracking so `README.md` stays judge-facing, `docs/ARCHITECTURE.md` stays system-facing, `docs/DATASET_CYCLE_TUTORIAL.md` stays workflow-facing, and this file stays backlog-facing.

## Active Backlog

- [ ] Add a production image-conditioned satellite inference adapter that consumes `GGUF + mmproj` artifacts, not only scored metadata.
- [ ] Replace VLM VQA/caption compatibility fallbacks with explicitly supported on-device implementations for the selected local runtime.
- [ ] Add a model-present smoke path that validates manifest-resolved GGUF loading separately from fallback-only default runs.
- [ ] Expand `scripts/evaluate_model.py` into a base-vs-tuned benchmark lane with independent labels, thresholds, and promotion artifacts.
- [ ] Feed Depth Anything V3 summaries into alert evidence/eval scoring and add a model-present smoke test where DA3 artifacts are installed.
- [ ] Expand dataset export from weak negatives into a full training contract with operator-reviewed controls and stronger localization labels.
- [ ] Add a versioned update cadence for future `Shoozes/LFM-Orbit-SatData` refreshes.
- [ ] Replace remaining SVG context placeholder outputs with raster thumbnails before dataset export so future Qwen cycles have zero unsupported assets.
- [ ] Persist API-generated maritime/lifeline monitor reports into `runtime-data/monitor-reports/` directly from UI/API usage.
- [ ] Add full replay snapshot export/import so completed realtime missions can be packaged outside bundled replay packs and cached API WebMs.
- [ ] Add a reusable Sentinel Hub replay seeding manifest command that refreshes exact replay assets without relying on manual grid/cell-dim selection.
- [ ] Add Sentinel Hub OGC/WMS instance-id seeding support only if a valid WMS-only instance appears; current Process API seeding uses validated OAuth credentials.
- [ ] Add optional Planet/Planet Insights imagery ingestion once a local API token is available; the current shared workspace URL is a browser account page, not an API credential.
- [ ] Add mocked SimSat Mapbox and Element84 STAC fixture coverage with visual asset URLs and operator-facing provenance checks.
- [ ] Replace the square-grid compatibility layer with true H3 parsing/generation before production geospatial scale-out.
- [ ] Add a custom temporal-use-case editor so operators can save preset libraries beyond bundled examples.
- [ ] Add responsive/mobile Playwright coverage for the map, fixed right rail, and Judge Mode panel.
- [ ] Add lightweight frontend unit/component tests for hooks such as `useMapPins`, telemetry normalization, and settings retry behavior.
- [ ] Deprecate user-facing data-source use of `demo_mode_enabled`; keep it as a run-context flag only where needed for legacy metrics/contracts.
- [ ] After `2026-04-29T18:00:00Z`, verify the SPC Southern High Plains fire-weather watch against FIRMS/NIFC and only promote it from `watch_only_unverified` if independent detections or incident reports exist inside the bbox.

## Edge Cases To Keep Covered

- Replayed cached API imagery must be labeled as `runtime_truth_mode=replay`, not as a run-context or fallback label.
- Realtime provider paths must include the provider/API family through `imagery_origin`; avoid vague standalone "live" labels in evidence surfaces.
- Fallback paths must carry fallback provenance and must not produce high-confidence positive alerts from provider errors, quality-gate failures, or heuristic-only VLM output.
- Empty or malformed provider credentials must report unavailable status without switching to external calls unexpectedly.
- Cloudy, stale, missing, RGB-only, or non-numeric spectral inputs must abstain rather than fabricate spectral indices.
- Quality-gated cloud/no-data failures must not emit `suspected_canopy_loss`, even when raw band deltas look large.
- Cached Sentinel replay/training frames must carry frame-quality metadata and reject cloudy frames before WebM creation.
- Timelapse evidence must contain multiple contextual satellite imagery slices; single still-image color shifts are invalid temporal evidence.
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

- Fast broken-import/export guard: `python -m pytest source/backend/tests/test_import_contracts.py`.
- Full backend guard: `python -m pytest source/backend/tests`.
- Frontend contract guard: `npm run lint` and `npm run build` from `source/frontend`.
- Judge acceptance path: `npm run demo:judge` from `source/frontend`.
- Full local validation remains `.\run.ps1 -Verify` from repo root.
- Latest integrity validation: backend `289 passed`; frontend `npm run lint` passed; frontend `npm run build` passed; `summary_bank.json` parsed; `uvx ruff check source/backend --select E9` passed; `git diff --check` reported only CRLF normalization warnings.
- Latest dataset-cycle validation: dataset export produced `56` current-cycle samples, `24` replay-cache rows, and `25` timelapse rows; bounded Qwen retag produced `179` assets and `26` temporal sequences with `74` reused image tags, `9` SVG placeholder skips, and zero tagger failures.
- Hugging Face remote config verification: `default=179`, `temporal_sft=26`, `asset_metadata=179`, `retagged_assets=179`, `temporal_metadata=26`, `review_queue=179`.
