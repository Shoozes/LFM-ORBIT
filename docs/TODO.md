# TODO

Updated **April 30, 2026**.

This is the canonical backlog and integrity note. Keep detailed history in `summary_bank.json` and focused docs; keep this file oriented around current state, active gaps, and edge cases.

## Current App State

- LFM Orbit is a demo-ready, local-first mission-control prototype, not an unattended production deployment.
- The hackathon runtime is built around DPhi Space SimSat (`simsat_sentinel`). Direct Sentinel Hub, NASA, and GEE-style providers are optional development/replay support and must not become required showcase dependencies.
- Mission Control can run realtime provider/API scans, replay cached real API imagery, monitor previews, optional visual evidence helper calls, timelapse generation, and dataset export paths.
- Runtime evidence surfaces expose three separate fields: `runtime_truth_mode` (`realtime`, `replay`, `fallback`), `imagery_origin` (`sentinelhub`, `simsat`, `nasa_gibs`, `gee`, `cached_api`, etc.), and `scoring_basis` (`multispectral_bands`, `proxy_bands`, `visual_only`, `fallback_none`).
- Replay-cache entries are stored real API imagery with preserved date/provenance for deterministic review and cost control. They are not generated evidence.
- The first `ice_snow_extent` lane scores cached Sentinel-2 L2A replay metadata with NDSI, SCL cloud rejection, snow/ice SCL support, water/ice ambiguity flags, and multi-frame persistence.
- Fallback means degraded runtime behavior: provider error, quality gate, heuristic proxy, or visual-helper compatibility fallback. Fallback paths must not masquerade as realtime imagery or high-confidence model output.
- Fast Replay can load curated replay packs and structurally valid cached API WebMs, then rescan saved metadata through the current runtime/model stack.
- Ground Agent chat now uses proposal cards for mutating local actions, so replay loads/rescans, mission packs, and SAT/GND link changes show provenance and expected state impact before the operator confirms; backend action errors stay visible instead of being marked confirmed, and post-action UI refresh failures are reported separately from successful action execution.
- Fast Replay excludes cached WebMs that fail structural timelapse-integrity checks, so static or color-shift-only videos are not presented as temporal proof.
- NDVI and NDSI have explicit spectral-band contracts: RGB-only, missing, or invalid band data returns unavailable/abstain instead of fabricated indices.
- Cloud and no-data coverage are hard quality gates: SCL metadata is used when available, cloudy cached frames are skipped, and cloud-blocked scoring windows return no-transmit quality-gate results.
- Optional visual evidence responses carry structured provenance with output source, model, fallback reason, runtime truth mode, imagery origin, and scoring basis.
- Visual evidence search supports operator target presets for homes, boats, possible flaring, and dark smoke while keeping fallback answers cautious and candidate-oriented.
- Visual evidence prompt/question inputs and Settings credential writes are trimmed and validated before runtime work or secret-file writes.
- The NM-UNI trained GGUF handoff bundle is published at `Shoozes/lfm2.5-450m-vl-orbit-satellite`; launchers pull it with `-FetchModel` / `--fetch-model` and preserve the source/training manifests locally.
- Orbit now surfaces the NM-UNI training/runtime distinction: image-backed training is proven from `training_result_manifest.json`, while runtime remains text evidence-packet reasoning until `mmproj` or native VLM image input is wired.
- Proof Mode JSON now includes `payload_accounting` so byte-reduction claims state which fields are counted and which proof artifacts are excluded.
- Local control endpoints are guarded for localhost use, and default CORS is a localhost allowlist unless overridden.
- Dataset export and retagging can carry cached replay timelapses into local ImageFolder-style training data; the current bounded Qwen/Ollama cycle is published to `Shoozes/LFM-Orbit-SatData`.

## Recent Integrity Pass

- [x] Split runtime metadata into `runtime_truth_mode`, `imagery_origin`, and `scoring_basis` across provider status, health, telemetry, metrics, recent alerts, replay, timelapse, visual-helper provenance, and frontend normalization.
- [x] Standardized the primary active-provider truth label as `realtime` while preserving backward compatibility for old stored rows and source labels.
- [x] Kept replay/cached API evidence labeled as `replay` with `imagery_origin=cached_api`; visual replay defaults to `scoring_basis=visual_only`, while band-derived replay manifests can explicitly use `scoring_basis=multispectral_bands`.
- [x] Changed cached timelapse provenance to `kind=replay_cache`, `label=Cached real API timelapse`, and `legacy_kind=seeded_cache`.
- [x] Applied a structural timelapse-integrity gate to dynamic Fast Replay catalog entries, excluding the legacy static Greenland WebM while keeping metadata-only cryosphere scoring available.
- [x] Added the first ice/snow evidence lane with NDSI, SCL cloud rejection, water/ice ambiguity flags, multi-frame persistence, API tests, replay/export provenance, and an Ice/Snow Mission Control preset.
- [x] Ensured provider failures and quality-gate failures produce zero-score/zero-confidence fallback or no-transmit results instead of forced positive alerts.
- [x] Updated frontend labels to distinguish realtime provider fetches, replay caches, cached API imagery, and fallback/proxy paths.
- [x] Added explicit Proof Mode payload-accounting metadata and proof assertions so `alert_payload_bytes` is scoped to compact downlink JSON, not the larger proof artifact envelope.
- [x] Cleaned stale public-facing replay wording in Inspect, Alerts, Mission replay notices, tutorial subtitles, dataset-card notes, and replay/timelapse runtime dialogue.
- [x] Re-scanned repo-local TODO/FIXME/stub/incomplete markers; remaining code-path hits were cleared or are intentional test fixtures/backlog items tracked here.
- [x] Consolidated progress tracking so `README.md` stays product-facing, `docs/ARCHITECTURE.md` stays system-facing, `docs/DATASET_CYCLE_TUTORIAL.md` stays workflow-facing, and this file stays backlog-facing.
- [x] Confirmed NM-UNI's role from `C:\DevStuff\NM-UNI-main`: it is the external Orbit dataset-import, Liquid training, GGUF quantization, `orbit_model_handoff.json`, and optional Hugging Face model-publish lane. Orbit should consume that handoff; it should not absorb NM-UNI's training UI/runtime.
- [x] Added `runtime-data/monitor-reports/` persistence for API-generated maritime and lifeline monitor reports, plus API/listing tests.
- [x] Added replay snapshot export/import for completed runtime surfaces so realtime or replay missions can be packaged outside bundled replay manifests and cached API WebMs.
- [x] Added `orbit_training_contract_v1` to exported samples, including operator-review, localization, evidence, and NM-UNI import metadata.
- [x] Rasterized SVG fallback context thumbnails to PNG during dataset export so future Qwen/Ollama cycles receive image assets instead of unsupported SVG placeholders.
- [x] Expanded `scripts/evaluate_model.py` into `orbit_eval_v2` with independent label-source handling, base-vs-candidate comparison, thresholds, and `promotion.json` artifacts.
- [x] Added `scripts/smoke_satellite_model.py` for manifest-resolved GGUF smoke checks when an NM-UNI handoff bundle is actually installed.
- [x] Added backend smoke coverage that keeps `simsat_sentinel` first in the provider fallback chain.
- [x] Deprecated user-facing use of `demo_mode_enabled`: current matches are backend metrics/contracts/types compatibility fields, not data-source labels shown as evidence.
- [x] Reframed README hierarchy around onboard bandwidth triage, proof cards, SimSat-first runtime positioning, explicit limitations, and reproducible demo commands.
- [x] Added Ground Agent action chat for local tool calls: list/load/rescan replay, start mission pack, infer mission pack from current context, and toggle SAT/GND link state.
- [x] Added backend-derived orbital-eclipse queue proof using unread `agent_bus` messages, with `link_state_before`, `queued_alerts_before_restore`, `link_state_after`, `flushed_alerts`, and `queue_source` exported in proof JSON.
- [x] Replaced public direct VLM wording with Liquid evidence-packet reasoning unless a manifest-resolved multimodal bundle is installed.
- [x] Neutralized maritime wording away from illegal-fishing claims toward dark-vessel and vessel-queue triage.
- [x] Removed remaining public VLM label residue in the app shell and tests, tightened visual evidence API error surfacing, and replaced loose frontend `any` casts around map cell IDs, alert rows, and metrics examples.
- [x] Refreshed `summary_bank.json` context groups for SimSat-first showcase proof, backend-derived DTN queue proof, Ground Agent local action chat, and frontend integrity polish.
- [x] Wired the published NM-UNI trained Orbit GGUF repo (`Shoozes/lfm2.5-450m-vl-orbit-satellite`) into the default model fetch path, launchers, docs, and tests.
- [x] Added repo-level `.gitattributes` line-ending and binary-artifact guardrails so Bash and PowerShell entrypoints stay reproducible across Linux and Windows checkouts.
- [x] Added visual evidence target presets and deterministic fallback boxes for operator searches such as homes, boats, possible flaring, and dark smoke, with Playwright coverage for the preset path.
- [x] Split launcher-managed backend virtualenvs by platform (`.venv-windows`, `.venv-linux`, `.venv-macos`) so Windows, WSL, Linux, and CI installs do not fight over one `.venv`.
- [x] Moved `llama-cpp-python` behind the optional `model` extra; `-FetchModel` / `--fetch-model` installs it when supported and falls back to a bootable core backend when local compiler support is missing.
- [x] Condensed `README.md` into a screenshot-led product surface with proof gallery, validation snapshot, runtime limits, and links out to deeper docs instead of repeating progress history.
- [x] Completed the due SPC Southern High Plains watch check: NM Fire Info independently reported the Sparks Fire in Quay County inside the watch bbox. The manifest is promoted only to `incident_report_verified_candidate`; satellite burn-scar confirmation remains a separate evidence step.
- [x] Hardened visual evidence and settings input validation: blank grounding prompts, blank VQA questions, and blank Sentinel credential fields now fail fast instead of producing vague fallback output or overwriting local secrets.
- [x] Added operator-visible MapLibre basemap degradation handling so headless/WebGL/style errors do not become unhandled UI noise and remain separate from scoring.
- [x] Replaced fixed waits in primary app and monitor Playwright specs with shared readiness, paint, video, and API polling helpers; deliberate tutorial/demo pacing remains isolated in recording helpers.
- [x] Removed the no-op `pass` from the optional GGUF chat-template shim so stub scans now only report intentional test fixtures.
- [x] Added manifest-derived model capability fields for NM-UNI handoff proof: `training_modality`, `image_training_verified`, multimodal row counts, image block counts, HF checkpoint presence, LoRA adapter presence, `mmproj_present`, runtime mode, and direct image-runtime reason.
- [x] Added status-safe image-runtime feature flags plus `/api/inference/image`, which returns structured unavailable provenance until a real image-conditioned adapter is wired.
- [x] Updated Settings to show training modality, image proof counts, `mmproj` presence, runtime mode, backend selection, and direct image-runtime availability without claiming the GGUF sees images.
- [x] Added Ground Agent action proposal cards plus `/api/agent/action/confirm` so chat-driven operations are reviewed before mutating app state; captured `docs/readme-ground-agent-chat-action.png` for the README proof gallery.
- [x] Hardened Ground Agent proposal confirmation: link-state actions require a real boolean target state, backend action-status errors surface in the proposal card, successful actions are not downgraded when a post-action UI refresh fails, and focused backend/Playwright regressions cover the declined-confirmation path.
- [x] Reframed the repo as a product/portfolio showcase while preserving Liquid AI x DPhi Space Hackathon context: public docs, package scripts, visible UI labels, demo guide, replay id, and proof artifacts now use Showcase/Proof Mode wording.

## Active Backlog

- No unblocked hackathon-path backlog remains in this file. The current showcase path is DPhi SimSat-first, replay-safe, dataset-exportable, and locally verifiable.

## Scope Lock

- Allowed before handoff: stability fixes, broken import/export fixes, reproducibility fixes, small UI polish, and sharper SAT/GND/CV/LFM response wording that keeps evidence boundaries honest.
- Not allowed before handoff: new provider integrations, new mission categories, new dashboards, new external services, or claims that require unbuilt image-conditioned multimodal runtime paths.

## Blocked External Artifact Lane

- [ ] Add a production image-conditioned satellite inference adapter that consumes fetched `GGUF + mmproj` artifacts when compatible, using the existing capability contract instead of hardcoded model paths.
- [ ] Add a native `transformers_vlm` image-runtime adapter for HF checkpoint/LoRA handoffs if that remains the safer route for LFM2.5-VL image conditioning.
- [ ] Add an image-conditioned smoke test that proves two different image inputs affect output before setting `image_conditioned_runtime_enabled=true`.
- [ ] Replace visual VQA/caption compatibility fallbacks with explicitly supported on-device implementations once the selected local runtime and model family are fixed.
- [ ] Attach a held-out base-vs-tuned evaluation report before claiming measured model lift; the current `training_result_manifest.json` has `eval_rows=0`.

## Verified Watch Follow-Up

- [ ] Seed and review post-event satellite evidence for the Sparks Fire before claiming satellite-confirmed smoke, active-fire, or burn-scar detection.

## Parked Post-Hackathon Ideas

- Sentinel Hub replay seeding manifests, live Sentinel Process API ice/snow summaries, OGC/WMS instance-id support, and refreshed Greenland contextual WebM proof.
- Planet/Planet Insights ingestion, broader Element84 STAC fixture work, and other non-SimSat direct-provider expansion.
- True H3 grid generation, a custom temporal-use-case editor, and Depth Anything V3 promotion into live alert scoring.
- Responsive/mobile Playwright coverage for the fixed right rail and Proof Mode panel.
- Lightweight frontend unit/component tests for hooks such as `useMapPins`, telemetry normalization, and settings retry behavior.

## Edge Cases To Keep Covered

- Replayed cached API imagery must be labeled as `runtime_truth_mode=replay`, not as a run-context or fallback label.
- Realtime provider paths must include the provider/API family through `imagery_origin`; avoid vague standalone "live" labels in evidence surfaces.
- Fallback paths must carry fallback provenance and must not produce high-confidence positive alerts from provider errors, quality-gate failures, or heuristic-only visual-helper output.
- Empty or malformed provider credentials must report unavailable status without switching to external calls unexpectedly.
- Settings credential writes must trim input and reject blanks without replacing a local secret file.
- Blank visual-evidence prompts or questions must fail validation before optional fallback/model work starts.
- Basemap render/tile/WebGL failures must stay operator-visible and must not alter mission scoring or evidence provenance.
- Image-trained handoff artifacts must not be described as direct image-conditioned Orbit inference unless the runtime passes image pixels into an adapter and status reports `image_conditioned_runtime_enabled=true`.
- `/api/inference/image` should stay structured and provenance-rich when unavailable so frontend callers can fail softly instead of implying image runtime success.
- Cloudy, stale, missing, RGB-only, or non-numeric spectral inputs must abstain rather than fabricate spectral indices.
- Quality-gated cloud/no-data failures must not emit `suspected_canopy_loss`, even when raw band deltas look large.
- Cached replay/training frames must carry frame-quality metadata and reject cloudy frames before WebM creation.
- Timelapse evidence must contain multiple contextual satellite imagery slices; single still-image color shifts are invalid temporal evidence.
- Dynamic Fast Replay must not list cached videos that fail structural frame-change checks, even when matching metadata exists.
- Ice/snow conclusions must require spectral bands and temporal persistence; RGB-only snow/cloud lookalikes should abstain or stay metadata-only.
- Link-offline mode must queue compact JSON alerts locally and flush only after link recovery.
- Ground Agent confirmations must use whitelisted action kinds and typed details; an HTTP 200 response with `action.status=error` must remain operator-visible and must not be displayed as confirmed.
- Payload-reduction proof must keep `payload_accounting` explicit so screenshots, videos, traces, and UI-only audit fields are not confused with downlink alert bytes.
- Demo and test runs should reset runtime state and avoid stale local server reuse unless explicitly requested.
- Recorded demos must preload their intended mission or replay before opening the browser; a generic default scan at video start is a regression.
- Map-action tests should use app readiness signals and shared helpers before touching the canvas; fixed sleeps are only acceptable for intentional visual/video pacing.
- Opt-in debug tests should write extra diagnostics to artifacts rather than polluting normal test output.
- Benign browser disconnect noise should stay out of demo logs; real websocket and backend exceptions should still be logged.
- Watch manifests must stay timestamped and source-backed; incident-report candidates are not satellite-confirmed detections until post-event imagery is seeded and reviewed.
- Operator-visible errors should remain visible for mission validation, visual evidence actions, Ground Agent chat, agent-bus injection, timelapse generation, map-pin sync, and settings status.
- Ground Agent proposals must stay whitelist-dispatched; frontend proposal details are review data, not arbitrary function names.
- Periodic mission refresh failures should leave debug diagnostics so stale mission state can be investigated during local demo runs.

## Verification Notes

- Fast broken-import/export guard: `python -m pytest source/backend/tests/test_import_contracts.py`.
- Full backend guard: `python -m pytest source/backend/tests`.
- Frontend contract guard: `npm run lint` and `npm run build` from `source/frontend`.
- Showcase recording path: `npm run demo:showcase` from `source/frontend`.
- Full local validation remains `.\run.ps1 -Verify` from repo root.
- Current product-surface integrity check: README/docs/package scripts/source wording scan found no stale overclaim or legacy demo framing; markdown local links resolve; JSON files parse; `summary_bank.json` references existing files; import-contract guard passed.
- Current closeout validation on April 30, 2026: backend guard now passes `335` tests after visual-evidence/settings validation, model capability-contract, and Ground Agent proposal regressions were added; `.\run.ps1 -Verify` passed with frontend lint/build passing and Playwright E2E `75 passed`, `1 skipped`. The run also refreshed `docs/tutorial_video.webm`.
- Current focused integrity validation from this pass: model-manifest + multimodal-inference + API checks passed `65`, frontend lint passed, affected Playwright app+monitor specs passed `47`, and the focused basemap/context guard passed `2`.
- Current model-pull validation: default `fetch_satellite_model.py --dry-run` resolves `Shoozes/lfm2.5-450m-vl-orbit-satellite@main`; actual fetch wrote the ignored local GGUF plus `model_manifest.json`, `source_handoff.json`, `training_result_manifest.json`, and README; Windows `.\run.ps1 -InstallOnly -FetchModel` installs the optional `model` extra and passes; WSL/Linux `bash run.sh --install-only --fetch-model` skips the optional `llama-cpp` build when no compiler exists and still completes the core install/model manifest check; `scripts\smoke_satellite_model.py --require-present --max-tokens 8` passed with `loaded=true`.
- Focused proof validation from this pass: backend API/agent-bus/import-contract checks passed `72`; visual evidence + QA Playwright checks passed `9`; orbital-eclipse recorded proof passed `1` and refreshed `docs/orbital-eclipse-demo.webm`, `docs/readme-orbital-eclipse.png`, and `source/frontend/e2e/artifacts/orbital-eclipse/proof.json`.
- Repo integrity checks from this pass: `summary_bank.json` parsed and all referenced files exist; stale public overclaim scans found no direct-frame Liquid claims, illegal-activity overclaims, stale visual-helper labels, or demo package-command drift; `git diff --check` is clean after line-ending normalization.
- Dataset/Hugging Face validation: dataset export produced `56` current-cycle samples, `24` replay-cache rows, and `25` timelapse rows; bounded Qwen retag produced `179` assets and `26` temporal sequences with `74` reused image tags, `9` historical SVG placeholder skips, and zero tagger failures. Hugging Face configs remain `default=179`, `temporal_sft=26`, `asset_metadata=179`, `retagged_assets=179`, `temporal_metadata=26`, `review_queue=179`, `mission_metadata=1`; latest data/card commit `1ebd19065e8a8124372425c4c0df9c0332275c9c`.
