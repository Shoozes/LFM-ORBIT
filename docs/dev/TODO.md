# TODO

Updated **May 6, 2026**.

This is the compact backlog and integrity checklist. Keep run-by-run history in `summary_bank.json`; keep product proof in `README.md`; keep implementation contracts in focused docs.

See [QA_PITFALLS.md](QA_PITFALLS.md) for the detailed guardrail checklist.

## Current State

- LFM Orbit is a demo-ready, local-first mission-control prototype, not an unattended production deployment.
- The hackathon satellite-data API family is SimSat/Mapbox through DPhi Space SimSat. Default realtime scanning uses `simsat_sentinel`; `simsat_mapbox` is the optional SimSat imagery/context lane when a Mapbox token is configured. Sentinel Hub, NASA, and GEE-style providers are optional development or replay support only.
- Evidence surfaces must keep `runtime_truth_mode`, `imagery_origin`, and `scoring_basis` visible.
- Replay-cache entries are stored real API imagery with preserved metadata. They are deterministic review assets, not generated evidence.
- New runtime cache WebM/meta outputs under `source/backend/assets/seeded_data/` are ignored by default; promote only reviewed fixtures with forced git add plus docs and summary-bank updates.
- Fast Replay excludes cached WebMs that fail timelapse-integrity checks.
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
- The retired target/monitor subtabs and visual-evidence tools panel must stay out of the submission UI unless deliberately reintroduced after review.
- Frontend reloads must not restart an active mission from the first scan cell or let stale demo query params override a live mission.
- Public README proof currently centers on Critical Minerals, target-pack proof, payload reduction, orbital eclipse queueing, provenance, abstain safety, Greenland timelapse context, Ground Agent flow, and semantic map context.
- The current trained NM-UNI bundle is fetched from `Shoozes/lfm2.5-450m-vl-orbit-satellite`; Orbit still treats it as evidence-packet reasoning until a direct image-conditioned adapter is wired and smoke-tested.
- Option 1 / `-Install` / `--install` refresh moving Hugging Face model refs such as `main` instead of assuming the installed manifest is current.
- The shared trained GGUF runtime serializes completion calls so simultaneous satellite/ground-agent generations cannot crash the native llama.cpp context.
- Docs are split by audience: `docs/user/` is for demo/review operators, `docs/dev/` is for architecture, data/model handoff, future lanes, QA, and backlog work.
- Tracked ad hoc backend scratch probes are pruned; use maintained scripts, tests, or documented manual provider probes instead.
- Manual Sentinel WMS connectivity/evalscript checks live in `source/backend/scripts/probe_sentinel_wms.py`; root-level `test_*.py` probes are intentionally blocked by import-contract tests.
- Manual Sentinel Hub cache refreshes are allowed for development/source-backed replay assets only. The May 5 Lochloosa West Fire seed attempt proved this path stays manual: `sh.txt` credentials resolved, the pre-fire Sentinel-2 L2A frame loaded, the May 4-5 event window was rejected for no-data/insufficient valid pixels, and no one-frame timelapse was written. The SR-26/Balu Forest fire seed succeeded as `sh_83e3aea2` with three real Sentinel-2 L2A burn-scar frames, frame PNGs, and curated replay `florida_sr26_wildfire_replay`; the postfire window remains rejected, so wording stays candidate-only.

## Active Backlog

- Rerun and review the Lochloosa West Fire Sentinel Hub seed after the next accepted post-event Sentinel pass before promoting Florida Fire/Drought Readiness Watch beyond candidate triage.
- Seed longer source-backed Atacama, Columbia Glacier, Great Salt Lake, and Lake Mead story assets before promoting those as README-level long-form proof.
- Expand object-evidence eval fixtures beyond the first replay-safe fireline/port cases and add stable CI thresholds.
- Add responsive/mobile coverage for the fixed right rail and Proof Mode panel.
- Add a small frontend unit/component layer for high-churn pure logic and hooks.
- Keep import/export guards current whenever scripts, entrypoints, or dataset row types change.
- Keep the docs user/dev split enforced when adding new markdown files.
- On the next demo-media refresh, pre-warm or trim Proof Mode transition frames so recorded videos do not linger on black loading states.
- Promote additional camera/location targets only with semantic profiles: aliases, bbox, center, camera, location type, terrain context, mission context, safe evidence guidance, and tags.
- Add optional external geocoding behind `/api/location/resolve` only if arbitrary place lookup becomes required. Keep the vetted local registry as the offline/default provider.
- Keep `marine_debris` and live HAB scoring as post-handoff Sentinel lanes; the combined plan lives in [FUTURE_SENTINEL_LANES.md](FUTURE_SENTINEL_LANES.md).

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
- claims that require unbuilt image-conditioned multimodal runtime paths

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

- Image-trained artifacts are not described as direct image-conditioned Orbit inference unless `/api/analysis/status` reports `image_conditioned_runtime_enabled=true`.
- `/api/inference/image` stays structured and provenance-rich when unavailable.
- A future image-conditioned adapter must prove different image inputs affect output before enabling runtime image claims.
- Shared local GGUF inference must remain process-serialized unless the runtime is replaced with a concurrency-safe server or per-agent model context.

## Verification Commands

- Full local verification: `.\run.ps1 -Verify` or `./run.sh --verify`
- Backend: `uv run --no-sync pytest -q` from `source/backend`
- Docs/media guard: `uv run --no-sync pytest tests/test_docs_artifacts.py -q` from `source/backend`
- Import/export guard: `uv run --no-sync pytest tests/test_import_contracts.py -q` from `source/backend`
- Frontend type/build guard: `npm run lint` and `npm run build` from `source/frontend`
- Full browser guard: `npm run test:e2e` from `source/frontend`
- Demo refresh: `npm run demo:record` and `npm run demo:tutorial` from `source/frontend`
- README timelapse refresh: `uv run --no-sync python scripts/build_docs_timelapse_highlight.py` from `source/backend`
- Offline story-plate refresh, dev only: `uv run --no-sync python scripts/build_visual_story_proofs.py --offline` from `source/backend`

## Latest Validation Snapshot

- `.\run.ps1 -Clean` followed by option-1 equivalent `.\run.ps1 -Install` completed from a cold runtime reset: dependencies installed, trained GGUF smoke passed, backend health returned, and the frontend served on `127.0.0.1:5173`.
- `.\run.ps1 -Verify` passed end to end on May 5, 2026: backend `463 passed`, trained GGUF smoke passed, frontend lint/build passed, and Playwright passed `98` with `6` intentional skips for HTML dump and retired visual-overlay UI specs.
- Clean-start browser guards still confirm no active mission, no replay auto-play, Atacama context selected, and only SAT/GND boot messages before an operator action.
- The refreshed README screenshots and tutorial WebM were regenerated by the browser media tests and visually sampled for current app context.
- May 5 media refresh: `npx playwright test e2e/capture_screenshots.spec.ts` passed `8`, `npm run demo:record` passed `5`, `npm run demo:tutorial` passed `1`, and `uv run --no-sync pytest tests/test_docs_artifacts.py -q` passed `17`. Promoted docs media was visually sampled with a local Playwright contact sheet.
- May 5 startup/selection check: clean option-1 launcher startup reached backend health and frontend ready with no cold-start mission; Playwright dependencies resolved cleanly from `node_modules`; map-side bbox drawing now has a dedicated draw hitbox and `npx playwright test e2e/bbox.spec.ts` passed `6`, including a real drag-to-grid assertion.
- May 5 replay metadata cleanup: curated replay JSON now carries explicit `use_case_id`; replay catalog/proposals expose `target_pack_id` when present; root-level manual Sentinel `test_*.py` probes were consolidated into `scripts/probe_sentinel_wms.py`; import-contract tests passed `5`.
- May 5 API hardening: `/api/analysis/status` and `/api/inference/status` now sanitize path-like model/runtime fields to filenames before returning public JSON; targeted API/docs/import regression guard passed `24`.
- May 5 chat-to-proof handoff: critical-minerals mission chat now resolves through the mission-pack `proof_replay_id` contract unless the operator asks for a live/current scan; load-replay completion clears stale proof media, selects the replay primary cell, and opens Inspect. Targeted backend chat tests passed `5`, frontend typecheck passed, and focused Playwright proof-replay regressions passed `3`.
- May 6 retrained model refresh: fetched `Shoozes/lfm2.5-450m-vl-orbit-satellite@main` revision `2a8c57cbb7f4dda26d5faff2ec3e31a5cbd2f4b8`; the local manifest reports task `wildfire_detection`, `5670` train rows, `5670` multimodal rows, `6758` image blocks, and `630` eval rows. GGUF smoke passed and `.\run.ps1 -Verify` passed with backend `463`, frontend lint/build, and Playwright `98`/`6` skipped.
- May 6 tutorial refresh: `npx playwright test e2e/tutorial_video.spec.ts` passed and regenerated a `237s` paced walkthrough that frames the app in plain language, launches a mission from Ground Agent chat, explains grid scanning and acquisition frames, shows retained semantic evidence, and ends on Proof Mode plus a final anomaly-found result card.
- May 6 tutorial interaction polish: the tutorial helper now records visible click pulses and operator-style typed Ground Agent prompts; `npx playwright test e2e/tutorial_video.spec.ts` passed and regenerated a `260s` walkthrough with clearer Send/Launch/Run/Inspect/Analyze/Proof action cues.
- May 6 retrained model refresh #2: cold reset passed, the latest `Shoozes/lfm2.5-450m-vl-orbit-satellite@main` was forced from remote revision `40a2ebdfeab056a7e0da8c41677d592e8bd2199d`, local training metadata reports task `wildfire_detection`, `7245` train/multimodal rows, `8335` image blocks, and `805` eval rows, and GGUF SHA256 is `7A0A6535BB144487AEBFFD947C56BEDCDC15A1F7F72B9E0D83A63308FB37B4E3`. A concurrent llama.cpp crash found during tutorial Playwright was fixed by serializing shared GGUF completions; `.\run.ps1 -Verify` passed with backend `464 passed`, GGUF smoke, frontend lint/build, and Playwright passing.
- May 6 public media refresh #2: `npx playwright test e2e/tutorial_video.spec.ts` passed, `npm run demo:record` passed `5`, and docs/import guards passed `22`; regenerated public WebMs remain under `docs/media/videos/`.
