# QA Pitfalls

Current as of **May 5, 2026**.

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

It can support text evidence-packet and bbox JSON reasoning from the NM-UNI handoff. Do not claim direct image-conditioned Orbit inference unless `image_conditioned_runtime_enabled=true` after an adapter passes a two-image smoke test where different images change the output.

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

Recorded docs-video suites should own their ports one at a time. Do not run `npm run demo:record` and `npm run demo:tutorial` in parallel unless the configs are moved to separate API/debug/Vite ports; both suites expect the default `8000`, `8080`, and `5173` launch path.

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

Do not print or paste tokens. Use `scripts/upload_orbit_dataset_hf.py` so the token resolves from `HF_TOKEN`, `HUGGINGFACE_HUB_TOKEN`, or `.tools/.secrets/hf.txt` into the subprocess environment only. A stale global `hf auth whoami` login should not block the helper when the local secret is valid.

### How do we verify a Hub refresh?

Upload only after local JSONL parsing and image inventory pass. Then read back the exact Hub revision and verify row counts for every config, the card counts, and manifest portability. Update `DATASET_CYCLE_TUTORIAL.md`, `source/backend/data/README.md`, `MODEL_HANDOFF.md`, `TODO.md`, and `summary_bank.json` with the final Hub commit, not an intermediate upload commit.

## Cold-Start QA

### What does "clean run" mean here?

Do not wipe source changes with `git reset`. A clean run means no stale app process and no stale transient artifacts. Clear `source/frontend/test-results`, `source/frontend/playwright-report`, and build outputs; then let Playwright start fresh backend/frontend servers with `RESET_RUNTIME_STATE_ON_BOOT=true`.

### How should we handle ad hoc QA audit findings?

Reproduce them through the app's normal launch path or Playwright before adding permanent TODOs. The May 4, 2026 audit reported telemetry WebSocket failure, missing `.env`, mission launch failure, camera failure, and silent VLM actions. Follow-up showed the WebSocket route passed after clearing a stale `8080` debug bind, `.env` absence is not a blocker when fallback/direct modes are active, and VLM/camera paths worked but needed clearer visible feedback. Fix confirmed UX gaps; document false positives instead of expanding scope.

For Florida Fire/Drought Watch, reject proxy-only vegetation or canopy-loss changes before they create pins or ground confirmations. Firewatch can use fuel-stress context, but retained fire candidates need smoke, active-fire, burn-scar, hotspot, or fireline-specific source evidence.

### What should pass before handoff?

Run:

```powershell
python scripts\build_visual_story_proofs.py
python -m pytest tests/test_docs_artifacts.py tests/test_import_contracts.py
```

from `source/backend`, then:

```powershell
npx playwright test e2e/visual-stories.spec.ts
npx playwright test e2e/vlm.spec.ts
npm run demo:record
npm run demo:tutorial
npm run lint
```

from `source/frontend`.

### What is the final human check?

Open the public images and watch sampled videos. Verify the visible story says what the app actually proves: what, why, where, when, evidence source, runtime truth mode, and scoring basis. If the media lies, fix the generator or app behavior first, then regenerate.
