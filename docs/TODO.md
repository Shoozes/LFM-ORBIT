# TODO

Updated **May 5, 2026**.

This is the compact backlog and integrity checklist. Keep run-by-run history in `summary_bank.json`; keep product proof in `README.md`; keep implementation contracts in focused docs.

See `docs/QA_PITFALLS.md` for the detailed guardrail checklist.

## Current State

- LFM Orbit is a demo-ready, local-first mission-control prototype, not an unattended production deployment.
- The hackathon runtime is DPhi Space SimSat-first. Sentinel Hub, NASA, and GEE-style providers are optional development or replay support.
- Evidence surfaces must keep `runtime_truth_mode`, `imagery_origin`, and `scoring_basis` visible.
- Replay-cache entries are stored real API imagery with preserved metadata. They are deterministic review assets, not generated evidence.
- Fast Replay excludes cached WebMs that fail timelapse-integrity checks.
- Cloud, no-data, malformed spectral bands, and RGB-only inputs must abstain instead of fabricating indices.
- Ground Agent mutating actions use proposal cards before state changes.
- Mission target packs remain backend/proof metadata and appear through alerts, replays, dataset rows, and Proof Mode; the normal Mission tab stays focused on plan, replay, progress, and timelapse.
- Mission date windows are use-case aware: long-term change missions can keep annual/history windows, while operational Fire Watch presets default to the last 30 days through current date.
- Clean startup is idle by contract: the app opens on the Atacama mining context without auto-playing a replay, starting a mission, or letting the telemetry websocket scan the legacy default region.
- Florida Fire/Drought Readiness Watch is candidate-only unless smoke, active-fire, burn-scar, hotspot, or fireline-specific source evidence is present; generic proxy vegetation changes are filtered before downlink.
- The retired target/monitor subtabs and visual-evidence tools panel must stay out of the submission UI unless deliberately reintroduced after review.
- Frontend reloads must not restart an active mission from the first scan cell or let stale demo query params override a live mission.
- Public README proof currently centers on Critical Minerals, target-pack proof, payload reduction, orbital eclipse queueing, provenance, abstain safety, Greenland timelapse context, Ground Agent flow, and semantic map context.
- The current trained NM-UNI bundle is fetched from `Shoozes/lfm2.5-450m-vl-orbit-satellite`; Orbit still treats it as evidence-packet reasoning until a direct image-conditioned adapter is wired and smoke-tested.

## Active Backlog

- Seed and review post-event Florida imagery before promoting Florida Fire/Drought Readiness Watch beyond candidate triage.
- Seed longer source-backed Atacama, Columbia Glacier, Great Salt Lake, and Lake Mead story assets before promoting those as README-level long-form proof.
- Expand object-evidence eval fixtures beyond the first replay-safe fireline/port cases and add stable CI thresholds.
- Add responsive/mobile coverage for the fixed right rail and Proof Mode panel.
- Add a small frontend unit/component layer for high-churn pure logic and hooks.
- Keep import/export guards current whenever scripts, entrypoints, or dataset row types change.
- Add lightweight API contract coverage for responses that must never expose local machine paths or secret-adjacent directories.
- On the next demo-media refresh, pre-warm or trim Proof Mode transition frames so recorded videos do not linger on black loading states.
- Promote additional camera/location targets only with semantic profiles: aliases, bbox, center, camera, location type, terrain context, mission context, safe evidence guidance, and tags.
- Add optional external geocoding behind `/api/location/resolve` only if arbitrary place lookup becomes required. Keep the vetted local registry as the offline/default provider.
- Keep `marine_debris` and live HAB scoring as post-handoff Sentinel lanes; the combined plan lives in `docs/FUTURE_SENTINEL_LANES.md`.

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
- The telemetry websocket must stay idle with an empty grid when no active mission exists; no backend scoring should happen just because the browser opened.
- Firewatch scans must not promote proxy-only canopy/vegetation deltas into map pins, ground confirmations, or fire claims.
- Stopped missions, replay contexts, and camera-only navigation show paused/idle scan state.
- Live missions show explicit starting, scanning, and complete status while cells arrive.
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

## Verification Commands

- Full local verification: `.\run.ps1 -Verify` or `./run.sh --verify`
- Backend: `uv run --no-sync pytest -q` from `source/backend`
- Docs/media guard: `uv run --no-sync pytest tests/test_docs_artifacts.py -q` from `source/backend`
- Import/export guard: `uv run --no-sync pytest tests/test_import_contracts.py -q` from `source/backend`
- Frontend type/build guard: `npm run lint` and `npm run build` from `source/frontend`
- Full browser guard: `npm run test:e2e` from `source/frontend`
- Demo refresh: `npm run demo:record` and `npm run demo:tutorial` from `source/frontend`
- README timelapse refresh: `uv run --no-sync python scripts/build_docs_timelapse_highlight.py` from `source/backend`
- Visual story proof refresh: `uv run --no-sync python scripts/build_visual_story_proofs.py --offline` from `source/backend`

## Latest Validation Snapshot

- Root cold-start verify passed after `.\run.ps1 -Clean`.
- Latest backend suite passed `446`.
- Focused docs/import/startup-firewatch guards passed `62`.
- Focused Playwright startup/draw-area guard passed `2`.
- Frontend lint/build passed after the startup/firewatch stabilization pass.
- Clean-start browser smoke confirmed no active mission, no replay auto-play, Atacama context selected, and only the SAT/GND boot messages on the bus.
- Florida Fire/Drought smoke confirmed `2026-04-05` to `2026-05-05`, `378/378` cells scanned, and `0` confirmed flags because proxy-only vegetation signals were filtered.
- Focused scanner reload regression guard passed in `tests/test_scanner_resume.py`.
- Mission target-pack UI guard passed in `source/frontend/e2e/vlm.spec.ts`.
- Full Playwright passed `98` with `1` intentional HTML-dump skip after 3D and Mission evidence UI pruning.
- Docs/import/scanner focused guard passed `21`; docs artifact guard alone passed `16` after the May 5 consolidation pass.
- Frontend lint/build passed after the May 5 consolidation pass.
- Focused Playwright Mission target-pack guard passed `3` on alternate ports because local `8000` was already occupied.
- Media contact-sheet review passed for promoted README images and docs videos; next refresh should trim black Proof Mode loading transition frames.
- Latest pushed CI and CodeQL runs on `main` passed after the tutorial pacing update.
- Current tutorial WebM duration is about `171.00s`; it now starts clean, launches the Rondonia mission through Ground Agent chat, shows the grid scan, then loads replay-backed proof.
