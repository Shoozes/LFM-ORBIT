# QA Pitfalls

Current as of **May 7, 2026**.

This doc is the regression-prevention checklist for generated media, mission stories, agent behavior, and model claims. Treat it as a question-and-answer gate before promoting screenshots, videos, story plates, or demo copy into public docs.

## Mission Story Scope

### What is the primary story track?

Use a SimSat/Mapbox mission where the app can show the full loop: mission context, SAT-side pruning, retained evidence packets, Ground Agent review, compact proof JSON, and replayable audit artifacts.

The current strongest public showcase track is Critical Minerals Expansion Watch over the Salar de Atacama / Escondida / Atacama mining corridor. It exercises the app's real shape: scan a mission bbox, prune low-value cells, keep contextual evidence, box retained extraction-site regions, reason over a compact evidence packet, and show why raw imagery does not need to downlink first. The current first-impression tutorial uses Rondonia frontier canopy-loss triage because it clearly demonstrates chat-launched mission setup, grid scanning, space/ground agent handoff, temporal/static evidence, target-pack proof fields, Proof Mode, and tagged training export in one continuous walkthrough.

### Why not lead with every possible use case?

Many use cases are valid directions, but not every generated plate proves the same thing. Fireline-to-Lifeline, Maritime Activity, Glacier Retreat, Waterline, shelter, road, and coastal-debris scenes are useful fixture/training tracks, but public proof must only show what survives visual audit and current runtime capability.

### How should the two agents work together?

The Satellite Pruner should scan and reduce the search space. The Ground Validator should review retained evidence, load or reconstruct replay context, propose operator actions, and package proof artifacts. The story should make their handoff visible instead of making the model look like a detached image captioner.

### Where does SimSat/Mapbox fit?

SimSat/Mapbox is the primary hackathon runtime lane and map context source. It should support mission search, spatial context, and operator review. Direct Sentinel Hub, NASA, GEE, and Esri context are optional development/replay supports, not required showcase dependencies.

### What can the trained model actually claim today?

It can support text evidence-packet and bbox JSON reasoning from the LiquidAI Leap Tune-compatible handoff. Do not claim image-conditioned Orbit inference unless `image_conditioned_runtime_enabled=true` after an adapter passes a two-image smoke test where different images change the output.

### What proves retained-frame image review is real?

The proof path is `/api/inference/image` with `image_b64`, not a server file path and not a text-only GGUF prompt. It must decode the retained evidence frame, pass pixels into the configured LiquidAI/LFM2.5-VL-450M Transformers image-text-to-text adapter, return `image_conditioned=true` only after success, and return structured unavailable or abstain states for missing dependencies, invalid images, blank/no-data frames, or failed model loading.

The CI-safe unit/API tests should fake the adapter. The real runtime gate is `scripts/smoke_image_review.py --require-present` with the `vision` extra installed. A release pass should include that smoke whenever the model revision, Transformers/Torch/Torchvision stack, or image adapter code changes.

## Generated Media Gates

### How should the README stay short?

Keep one hero visual, the run command near the top, proof images inside the proof gallery, and progress history out of public copy. Public visuals must live under `docs/media/`, be linked from markdown, and pass `test_docs_artifacts.py`. Use `TODO.md` for current backlog and `summary_bank.json` for detailed history.

### When can generated screenshots or story plates enter `docs/media/`?

Only after they pass visual review and metadata checks. A generated file starts as a candidate. Public story plates must have `public_docs=true`, `visual_audit_status=approved`, visible `box_source=visual_story_fixture`, and labels scoped as areas, groups, zones, samples, regions, corridors, clusters, or candidates unless a true object-scale model path supports a singular-object label.

### What went wrong with `story-object-evidence-port.png`?

The generated plate had a `channel vessel` box over open water, plus an audit note visible in the image. That failed truth review. The fix was code-level: remove the unsupported singular vessel box, change public labels to region/group wording, add audit metadata, and add tests that reject public plates without approval and scoped labels.

### What changed after the port local-audit pass?

Exact object boxes are too brittle when the zoomed satellite context is soft or low resolution. The safer default is group/area evidence: `shipping container cluster`, `container yard cluster`, `docked-vessel group`, and `berth basin context`. The fallback VLM path must not invent exact `homes` or `boats` boxes, and model-backed exact-object classes must clear class-specific confidence gates before becoming proof evidence.

### What UI evidence tools are intentionally retired?

The old Mission-tab target/monitor subtabs and visual-evidence tools panel are retired for submission. Target packs now live as backend/proof metadata attached to missions, alerts, replay snapshots, dataset rows, and Proof Mode. If future work reintroduces operator tuning, it needs new product review and tests because first-run Mission UI should stay focused on plan, replay, progress, and timelapse.

### What went wrong with reload-driven scan confusion?

Frontend reload could reconnect to an active mission and make the scan look like it restarted, while stale demo query params could make the UI appear to fall back to a deforestation replay. The guards are: backend scanner resumes from `mission.cells_scanned`, frontend repaint reconstructs prior scanned cells from mission progress plus alerts, stale demo URLs cannot override active live missions, and normal app startup must not auto-play the last replay.

No active mission means no scan. `/ws/telemetry` may open for UI readiness, but it must emit an empty grid/complete state and avoid scoring cells until an operator-confirmed live mission exists. This prevents clean startup from silently scanning the legacy default region.

### What went wrong with the first object-evidence runtime capture?

The demo passed semantically but zoomed the map enough that the exported screenshot no longer matched the approved story-plate context. The fix was to keep the mission bbox stable, remove the recording zoom step, and let the docs screenshot show the same port-region framing as the visual-story plate. The runtime capture is useful for UI/provenance flow; the story plate remains the cleaner public object-evidence proof.

### What if a box covers many subjects?

Name it as a group, zone, row, cluster, area, or candidate region. Do not label a broad box as one object. For example, use `docked-vessel group`, `container zone`, or `shelter-row cluster` instead of implying one confirmed subject.

### What if the screenshot looks compelling but the source is weak?

Keep it local. App-level CV captures, Playwright screenshots, and generated plates stay under `source/frontend/e2e/artifacts/`, `source/frontend/test-results/`, or `source/backend/assets/seeded_data/visual_story_frames/story_plates/` until promoted.

### How do we avoid stale docs media?

Public docs media must be linked from markdown and covered by `source/backend/tests/test_docs_artifacts.py`. Raw Playwright screenshots should not write to `docs/media/` unless the artifact is intentionally promoted.

If a promoted WebM is referenced from README or the demo guide, it must also be included in the explicit public-video temporal/nonblank guard. The May 3, 2026 media refresh found `object-evidence-demo.webm` linked from README but missing from that explicit video list, which made the docs feel stale even though the file existed. The fix is to list the video in both `docs/user/DEMO_GUIDE.md` and `test_public_demo_videos_are_temporal_and_nonblank`.

Recorded docs-video suites should own their ports one at a time. Do not run `npm run demo:record`, `npm run demo:tutorial`, screenshot capture, or targeted Playwright specs as separate parallel commands unless the configs are moved to separate API/debug/Vite ports; these suites expect the default `8000`, `8080`, and `5173` launch path. The Playwright configs already use one worker internally, so the risk is parallel shell commands, not normal suite execution.

### What if `summary_bank.json --auto-add` over-expands groups?

Treat that as a docs integrity regression. The bank should organize issue and feature groups, not attach most backend files to every group. Keep group file lists focused on the files that define, test, or document the issue. If a generated pass gets too broad, trim it back before handoff and rerun `test_docs_artifacts.py`.

### What if MapLibre logs a shader or WebGL warning during headless capture?

Treat it as a recoverable basemap-rendering issue unless the map goes blank or the browser guard fails. The app should surface `Basemap rendering degraded. Scoring is unaffected.` and continue keeping mission scoring/provenance separate from visual tile rendering. If the public screenshot is blank, fix readiness or rendering before promotion.

For screenshot/media export tests, wait for the map visualizer and nonzero MapLibre canvas size before capture. Basemap credit text can remain in a loading state after recoverable headless WebGL warnings even when imagery is visible, so tests should not block solely on the attribution label.

### Should external inspiration become proof?

No. External posts, including the Pau Labarta Bajo X post about smaller VLMs plus satellite imagery, are useful for mission framing. They do not validate our app. Convert inspiration into a mission hypothesis, then prove it through local app behavior, replay artifacts, and auditable metadata.

## Claim Boundaries

### Can we say the app detects refugee populations?

No. It can count or sample shelter-row areas when the imagery supports that scope. Avoid person-level population claims unless a separate, validated demographic model and ethical review path exists.

### Can we say the app detects plastic pollution?

Only as candidate slick, foam-line, or debris review areas unless material identity is confirmed by a supported sensor/model path. RGB or broad satellite context alone is not material identification, and open-ocean garbage-patch mass growth is not a safe optical-satellite claim.

### Can we say the app detects toxic algae or red tide?

No. The safe current wording is probable surface bloom, high chlorophyll signal, cyanobacteria-like signal, or possible HAB candidate. Sentinel-2 and basemap imagery cannot confirm toxin level, species, microcystin, or Karenia brevis on their own. Require NOAA, FDEP, or field confirmation before using toxic, species-specific, or confirmed red-tide language.

### Can we say the app finds illegal fishing?

No. Use neutral maritime wording such as vessel queue, dark-vessel triage, port activity, or supply-chain context. Legal conclusions are outside this app's current proof scope.

### Can fixture boxes be described as live model detections?

No. If `box_source=visual_story_fixture`, say fixture, candidate, replay, or visual-story evidence. Use model-backed detection wording only when the boxes come from a real detection path with provenance.

## Dataset And Hub Handoff

### What went wrong in the latest retag refresh?

The retag pass reused existing Qwen tags correctly, but the generated upload folder still contained stale `images/` files from a previous source footprint. That produced `197` metadata rows and `200` image files, leaving orphan assets that could be uploaded without a current JSONL row.

The fix is code-level: after reusable prior JSONL tags are loaded, clear generated `images/` and `frames/` outputs, then regenerate the package. Before upload, validate `metadata.jsonl` against `images/` and require `orphan_count=0` and `missing_count=0`.

### What went wrong in the offline-safe refresh?

The exporter tried to resolve ESRI context thumbnails for arbitrary rows and exceeded the local run timeout. The fix is code-level: use `--offline-context-thumbnails` for packaging refreshes that should stay local, and clear generated `samples/` before each export so retag loose scans cannot see stale sample assets.

### What if Ollama/Qwen retagging stalls?

Stop the stuck retag process and continue with `--reuse-existing-dir` plus `--reuse-existing-only` for normal refreshes. That preserves already-tagged image hashes, prevents new rows from blocking on Ollama/OpenAI, and routes any new hashes through deterministic heuristic fallback. Record the requested provider/model and effective fallback in the manifest and docs; do not pretend a heuristic fallback was a fresh visual-model pass.

### Can a Hub manifest include local absolute paths?

No. A published dataset manifest must not expose machine-specific paths such as `C:/Users/...`. The retag manifest should use portable labels such as `orbit-export`, `.`, or repo-relative paths. Regression coverage should assert that temporary workspace paths do not appear in the manifest.

### How should mission metadata be packaged?

Mission metadata belongs in `mission_metadata.jsonl`, not in single-image SFT rows. It preserves operator task text, bbox intent, target packs, object targets, replay ids, and training-contract metadata without pretending metadata-only missions have visual proof assets.

### What if Hugging Face CLI auth looks stale?

Do not print or paste tokens. Use `scripts/upload_orbit_dataset_hf.py` so the token resolves from `HF_TOKEN`, `HUGGINGFACE_HUB_TOKEN`, or a local developer token file into the subprocess environment only. A stale global `hf auth whoami` login should not block the helper when the local secret is valid.

### How do we verify a Hub refresh?

Upload only after local JSONL parsing and image inventory pass. Then read back the exact Hub revision and verify row counts for every config, the card counts, and manifest portability. Update `DATASET_CYCLE_TUTORIAL.md`, `source/backend/data/README.md`, `MODEL_HANDOFF.md`, `TODO.md`, and `summary_bank.json` with the final Hub commit, not an intermediate upload commit.

### What went wrong during the May 7 Hugging Face refresh?

The refresh worked, but exposed several packaging traps:

- The default dataset export limit can let repeated mission-archive metadata crowd out older seeded replay rows after timestamp sorting. For training-focused Hub refreshes, use `--no-missions --no-archived-missions` unless the explicit goal is intent/tool tuning.
- The docs still described the upload as ImageFolder-first. The actual Hub contract is explicit JSONL configs with `images/` assets: `default`, `temporal_sft`, `asset_metadata`, `retagged_assets`, `temporal_metadata`, and `review_queue`.
- Retagged `video_source` references initially carried absolute Windows paths inherited from extracted timelapse frame refs. The fix is code-level: the retagger now writes export-relative paths such as `samples/<sample_id>/timelapse.webm`, and tests assert that temporary workspace paths do not leak.
- An empty `mission_metadata.jsonl` was listed in the Hub card. Dataset Viewer treats an advertised empty JSONL config as a split-parse failure. Omit empty configs from the card until they contain rows.
- Dataset Viewer indexing is asynchronous. A commit can be present while `/splits` or `/size` reports pending, busy, or index-loading states. Poll until pending and failed are empty before recording final counts.

The upload helper now runs pre-upload validation unless `--skip-validation` is explicitly passed. It parses root JSONL files, checks referenced `images/` assets, rejects local path leaks, catches orphan/missing images, and blocks README configs that point at empty JSONL files.

## Cold-Start QA

### What went wrong during the May 7 wildfire replay proof pass?

The useful failures were all reproducibility and claim-boundary issues:

- The existing backend on `8000` was stale and returned `404` for the new `/api/wildfire/smoke-score` endpoint. Avoid assuming a running port is current after code edits. For manual app checks, either restart the repo-owned backend or launch an isolated backend on another port and point Vite at it with `VITE_API_BASE_URL`.
- A PowerShell `Start-Process` command accidentally appended the log path as a Vite route argument, so Vite served `404` at `/`. Avoid shell-redirection strings in nested `Start-Process` calls. Use `-RedirectStandardOutput` / `-RedirectStandardError`, or a simple `cmd /c` command whose arguments are known-good.
- The first Pineland Road replay crop produced only two accepted frames, then failed the structural timelapse guard because the edge-map delta was below `0.02`. A replay WebM is not valid proof just because the frame colors change. The fix was to add an ignition/pre-active window and widen the crop from the narrow `sh_ad1a3f08` view to `sh_af5954b2`, which produced three contextual frames and passed the integrity threshold.
- SCL treated the active white plume as cloud. Do not solve this by weakening cloud rejection globally. The fix was wildfire-specific: retain active/ignition burn-scar frames as `review_only` only when `dataMask` is valid, mark `acceptance_override=wildfire_smoke_cloud_review`, include B02/B03/B04/B08/B11/B12/SCL/CLD/CLP/dataMask summaries, and let the confidence assist defer ambiguous smoke/cloud claims.
- New `source/backend/assets/seeded_data/sh_*` WebM/meta/frame outputs are ignored by `.gitignore`. Curated replay JSON can accidentally reference local-only cache assets. Before committing a promoted replay, run `git status --short --ignored` on the exact `sh_*` asset family and force-add the reviewed WebM, meta JSON, and frame directory if the replay depends on them.
- Playwright CLI output created `.playwright-cli/` and ad hoc `output/` artifacts during manual inspection. Keep those transient unless the user explicitly asks for an artifact. Remove them before final status or committing.
- The app proof path can pass semantically while Proof Mode still reports image-conditioned review unavailable. That is acceptable for this lane: the proof is cached Sentinel replay plus compact multispectral metadata, not a claim that the GGUF or image-review adapter inspected the frame.

Manual validation that resolved the above:

```powershell
cd source/backend
uv run --no-sync pytest tests/test_wildfire_smoke.py tests/test_spectral_band_contract.py tests/test_seed_sentinel_cache.py tests/test_replay.py tests/test_api.py tests/test_seeded_timelapse_integrity.py tests/test_vlm.py -q
```

Expected result for the May 7 pass after the reproducibility fixtures were added: `157 passed`.

The operator-path check loaded `pineland_road_wildfire_replay` through Ground Agent chat, confirmed the proposal, verified `wildfire_assessment.target_action=defer`, saw `smoke_or_cloud_review` on the active frame, and opened Proof Mode with replay pins and compact proof JSON visible.

### What went wrong during the May 7 wildfire reproducibility packaging pass?

The app result was repeatable on the local machine before it was repeatable from a fresh repo checkout. These were the packaging pitfalls:

- Curated replay JSON referenced promoted `sh_*` cache assets, but the default `.gitignore` still hid new Sentinel Hub WebMs, metadata, and frame directories. The fix was to add explicit unignore rules for promoted wildfire cache families and stage each WebM, `_meta.json`, and frame PNG directory that a curated replay references.
- The first reproducibility test required `frame_images` metadata for every seeded replay in the repo. Older non-wildfire replay assets have valid WebMs but were not produced with exported frame PNG metadata, so the test failed on unrelated fixtures such as `sh_07da3a0b`. The fix was to keep the older broad timelapse-integrity guard for all replay WebMs, then apply the stricter frame-image contract only to source-backed wildfire replays.
- Backend/API proof carried `wildfire_assessment`, but the frontend initially parsed only the older alert fields. That made the same cached result less visible to operators. The fix was to add telemetry types/parsing plus compact Wildfire Confidence Assist cards in the Validation panel and Proof Mode JSON/sidebar.
- Manual staging can accidentally sweep unrelated changes into the proof set. The pass found an unrelated `README.md` media-link edit and left it unstaged. Before handoff, run `git status --short` and stage by explicit path groups rather than broad `git add .` when the worktree contains unrelated edits.
- `git diff --check` reported only line-ending normalization warnings for touched files, not whitespace errors. Treat those warnings as a reminder to keep the final diff reviewed; do not churn files purely to silence CRLF/LF notices during a scoped proof pass.

The reproducibility check for this packaging pass was:

```powershell
cd source/backend
uv run --no-sync pytest tests/test_wildfire_smoke.py tests/test_spectral_band_contract.py tests/test_seed_sentinel_cache.py tests/test_replay.py tests/test_api.py tests/test_seeded_timelapse_integrity.py tests/test_vlm.py -q

cd ../frontend
npm run lint

cd ../..
git diff --check
```

Expected result: backend `157 passed`, frontend typecheck clean, and no whitespace errors from `git diff --check`.

### How do we avoid re-downloading the same wildfire data?

Promoted real-provider wildfire assets are now tracked in `docs/dev/SEEDED_DATA_REGISTRY.md`. Before using Sentinel Hub credentials, check the registry and the existing `_meta.json` for the cache key, bbox, date windows, visual mode, band contract, and rejected-window notes. If the area and frame windows are already present, reuse the cache in tests, training exports, and replay polishing.

The May 7 Spain pass added `spain_larouco_wildfire_replay` from `sh_09384ab0` rather than replacing the Florida/Georgia proof. It is a different proof lane: postfire burn-scar review with positive dNBR support and low postfire cloud support. Keep it candidate/review because no hotspot context is attached.

### What went wrong during the Spain user-flow app check?

The replay itself worked, but the temporary app launch exposed repeatable dev-server pitfalls:

- `Start-Process` on Windows rejects using the same file for both `-RedirectStandardOutput` and `-RedirectStandardError`. Use distinct `.out.log` and `.err.log` files.
- Quoted env assignments inside a nested PowerShell `-Command` string are brittle when the repo path contains spaces. Prefer `Start-Process -WorkingDirectory ... -ArgumentList @(...)` and set any inherited env vars in the parent shell immediately before launch.
- `npm` must be launched as `npm.cmd` from `Start-Process` on Windows; `npm` alone can fail with `%1 is not a valid Win32 application`.
- Backend CORS defaults allow the standard Vite origins `5173` and `4173`. A temporary frontend on `5175` rendered the app but blocked every API call. Use `5173` for user-flow checks, or start the backend with `ORBIT_CORS_ALLOW_ORIGINS` including the temporary origin.
- After replay load, the app selects the Inspect tab automatically. To open Proof Mode as a user, switch back to the Agent tab (`tab-agents`) and then use the Ground Agent Proof Mode shortcut.

The passing user-flow check loaded `spain_larouco_wildfire_replay` from the Ground Agent suggestion, confirmed `Run Replay`, verified the Inspect-panel Wildfire Confidence Assist card, opened Proof Mode, and verified `wildfire_assessment` plus the Proof Mode Wildfire Assist card.

### How do we keep Sentinel Hub from becoming the hackathon default?

Sentinel Hub is for development, real-data research, replay seeding, and cache refreshes only. The hackathon default provider story is SimSat/Mapbox through DPhi Space SimSat. A clean hackathon run should not require `SENTINEL_CLIENT_ID`, `SENTINEL_CLIENT_SECRET`, `sh.txt`, or any Sentinel Hub quota.

The safe split is:

- Default live/realtime scan path: `simsat_sentinel` with optional `simsat_mapbox` context when a Mapbox token is configured.
- Deterministic proof/demo path: bundled cached replay assets under `source/backend/assets/seeded_data/` and curated replay JSON under `source/backend/assets/replays/`.
- Development refresh path: manual Sentinel Hub seeding scripts, logged in `docs/dev/SEEDED_DATA_REGISTRY.md`, with promoted cache files committed only after review.

Avoid wording such as "live Sentinel Hub proof" in hackathon docs or UI copy. Use "cached real API replay", "development-seeded Sentinel Hub cache", or "source-backed replay asset" when describing these wildfire fixtures. If operators need to test without cached replay data, add a Settings switch or environment-backed flag to hide/disable cached replays; for now this stays in backlog to keep the release surface narrow.

### What does "clean run" mean here?

Do not wipe source changes with `git reset`. A clean run means no stale app process and no stale transient artifacts. Clear `source/frontend/test-results`, `source/frontend/playwright-report`, and build outputs; then let Playwright start fresh backend/frontend servers with `RESET_RUNTIME_STATE_ON_BOOT=true`.

### What broke during the Windows/WSL cold-start integrity pass?

The clean Windows clone passed after the staged patch, but the WSL clone exposed environment and config assumptions:

- `playwright.config.ts` used `uv run --no-sync` for backend web servers. A fresh Linux checkout did not have the platform-specific `.venv-linux` populated, so `uvicorn` was missing. The fix was to use `uv run --locked`, which creates/syncs the env from `uv.lock` without mutating the lockfile.
- WSL only had Windows `node.exe`/`npm` on PATH. That made npm try to run from UNC paths and write under `C:\Windows`. The fix was a native Linux Node install under `~/.local/bin`, with `node`, `npm`, and `npx` verified from WSL before running frontend tests.
- WSL had `uv` available in an interactive path, but not for non-login webServer shells. Install or expose native `uv` under `~/.local/bin` so Playwright child processes can start backend services.
- Fresh Linux Playwright installs need both browser binaries and OS libraries. `npx playwright install chromium` downloads Chromium; `npx playwright install-deps chromium` installs packages such as `libnspr4`, `libnss3`, `libatk`, `libgbm`, `libxkbcommon`, and `libasound2`. In WSL this can be run as root via `wsl.exe -u root`.
- Run Playwright from `source/frontend`, not from the repo root with `npx --prefix`. The repo root invocation bypasses the frontend config/webServer setup and fails with `ECONNREFUSED` before the app starts.

The final WSL cold-smoke used a clean staged-content clone, native Linux `node/npm/npx/uv`, Playwright Chromium/deps, and passed the responsive plus replay-confirm tests.

### How should we handle ad hoc QA audit findings?

Reproduce them through the app's normal launch path or Playwright before adding permanent TODOs. The May 4, 2026 audit reported telemetry WebSocket failure, missing `.env`, mission launch failure, camera failure, and silent VLM actions. Follow-up showed the WebSocket route passed after clearing a stale `8080` debug bind, `.env` absence is not a blocker when fallback/direct modes are active, and VLM/camera paths worked but needed clearer visible feedback. Fix confirmed UX gaps; document false positives instead of expanding scope.

For Florida Fire/Drought Watch, reject proxy-only vegetation or canopy-loss changes before they create pins or ground confirmations. Firewatch can use fuel-stress context, but retained fire candidates need smoke, active-fire, burn-scar, hotspot, or fireline-specific source evidence.

### What should pass before handoff?

Run:

```powershell
.\run.ps1 -Verify
```

For the hackathon run path, also smoke option 1 without leaving servers running:

1. Start `.\run.ps1 -Install` from a separate process.
2. Wait for `http://127.0.0.1:8000/api/health` and `http://127.0.0.1:5173`.
3. Confirm the run log shows model fetch/smoke, backend ready, and Vite ready.
4. Stop the launcher process tree and confirm ports `8000`, `8080`, and `5173` have no active listeners.

For targeted backend integrity after docs/model changes:

```bash
cd source/backend
uv run --no-sync pytest tests/test_docs_artifacts.py tests/test_import_contracts.py tests/test_multimodal_inference.py tests/test_inference_image_api.py tests/test_replay.py -q
```

For targeted frontend/media integrity:

```bash
cd source/frontend
npm run lint
npx playwright test e2e/proof-mode-image-review.spec.ts
npm run demo:record
npm run demo:tutorial
```

### What broke during the latest quick integrity spot-check?

The docs/media guard caught a public video artifact that had been generated as `docs/media/videos/traning-journey.webm` but was not referenced by any markdown. Public media under `docs/media/` is intentionally treated as promoted proof, so orphaned files fail `test_docs_artifacts.py` even when the app itself is healthy. The fix was to preserve the artifact under the corrected `training-journey.webm` name and register it in `docs/media/README.md`.

Avoid putting draft videos directly under `docs/media/`. Keep temporary recordings in Playwright output folders until they are visually audited, named correctly, referenced from docs, and meant to ship.

When the optional image runtime is installed:

```bash
cd source/backend
uv run --extra dev --extra model --extra vision python scripts/smoke_image_review.py --require-present
```

from `source/frontend`.

### What is the final human check?

Open the public images and watch sampled videos. Verify the visible story says what the app actually proves: what, why, where, when, evidence source, runtime truth mode, and scoring basis. If the media lies, fix the generator or app behavior first, then regenerate.
