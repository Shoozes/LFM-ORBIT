# Current Integrity Review

Updated **August 4, 2026**.

This is the canonical short review snapshot. The active backlog and completion conditions live in [TODO.md](TODO.md); historical route and progress detail stays in [archive/summary_bank_history.json](archive/summary_bank_history.json).

## Decision

The hosted application is ready for a Pages project-path build, but the public deployment is not yet proven. The local Pages bundle now builds under `/LFM-ORBIT/`, keeps first-party assets below that base, installs its browser-test runtime in CI, and has a lightweight post-deploy static-origin smoke. The public Pages artifact deliberately disables browser model fetching until the owner-approved licensing decision; a live-origin model proof remains a release-only gate for the model-enabled lane.

## Evidence matrix

| Surface | State | Evidence |
| --- | --- | --- |
| Hosted architecture | Green | Isolated hosted entry, saved packages, browser-local text reasoning, and no backend dependency. |
| Pages project path | Green locally | `build:pages` plus `test:hosted:pages` exercise `/LFM-ORBIT/`, JSON, CSS, JavaScript, WASM, favicon, and all promoted package stills. |
| Pages workflow | Green in-repo | `.github/workflows/pages.yml` installs Chromium, builds only `dist-pages` with `VITE_HOSTED_MODEL_ENABLED=false`, deploys with the `github-pages` environment, then runs a no-weight static-origin smoke. |
| Public origin | Unproven | No deployment or post-deployment real-model run has been performed from the live Pages URL. |
| Model licensing | Owner gate / public model disabled | The derivative handoff is currently labeled `mit`, while the upstream LiquidAI model card is labeled `lfm1.0`; redistribution and attribution terms still need owner/legal confirmation, so Pages remains saved-packages-only. |
| Full-app runtime | Green for default browser suite | The August 4 default Playwright suite reran with `108 passed, 6 skipped`; the root launcher/GGUF lane remains a separate historical proof and was not rerun in this pass. |

## Changes in this pass

- Added one configurable Vite base for local root, Pages project-path, and custom-domain-root builds.
- Added a shared safe asset resolver and changed hosted package paths to repo-relative values.
- Required every promoted hosted package to carry an accessible visual asset; promoted the matching fireline source frame.
- Added a Pages-subpath Playwright smoke and a least-privilege Pages deployment workflow.
- Added an explicit live-origin Playwright harness that runs only with `HOSTED_PAGES_URL` and records two model/chat timing passes.
- Replaced the Starlette/httpx TestClient warning path with the locked `httpx2` development dependency.
- Added the missing review snapshot and routed it from the docs index/context bank instead of expanding progress notes across product docs.
- Added explicit hosted manifest readiness/disabled states, a Pages-only saved-packages gate, Chromium installation in the workflow, and a post-deploy static-origin smoke that retains Playwright reports.
- Made distinct-acquisition confirmation idempotent by persisting a stable acquisition fingerprint per mission/cell and defaulted new one-shot missions to `single_acquisition`.
- Added a shared request gate with tests, then applied it to App mission polling and Agent Dialogue bus stats polling so superseded or unmounted responses cannot repaint state.
- Narrowed active summary-bank routes to focused source/contracts and omitted large binary/media payloads; the audit now reports no missing references, broad groups, or over-budget active groups.

## Release gates

- **Live-origin static proof:** run after every successful deployment through `test:hosted:pages:live:static`; prove the project path, asset MIME, manifest/image/WASM availability, and no backend/provider traffic without downloading weights.
- **Live-origin model proof:** run only after licensing approval and a successful deployment with the model gate enabled; prove the sealed manifest, pinned revision, initial 219 MB load, local response, no backend traffic, and measurable cached reuse.
- **Model license decision:** confirm the derivative GGUF, upstream base terms, quantization/redistribution rights, attribution, and displayed metadata before public promotion.
- **Archive references:** verify the preserved `hackathon` branch and immutable tag resolve to the intended pre-modernization submission, or record the owner-approved alternative.

## Verification used for this snapshot

- Bundled Node TypeScript check: passed.
- Pages production build: passed.
- Hosted build smoke follow-up: the built preview started, but the managed browser hung on its single static test after launch; the test-owned process was stopped after a bounded wait, so this run is unproven rather than green.
- Pages-subpath Playwright smoke: build contract passed; the managed browser runner became stuck after launch in this sandbox and was stopped without changing repo state. CI now installs Chromium and runs the same smoke on Ubuntu.
- Frontend unit tests: 10 passed (8 browser-model cases and 2 request-gate cases).
- Summary-bank audit: 66 groups, one default route, 107.9 KB expanded default context, no missing references, and no active group over its advisory budget.
- Backend/docs/import/CI verification: 557 tests passed in the repository Windows environment with one Starlette deprecation warning because that stale venv lacks the declared `httpx2` dev extra; no app test failures. The lockfile/CI contract still declares `httpx2` for a warning-free managed run.
- Follow-up environment audit: both ignored backend virtualenvs currently point to a missing uv-managed Python executable, and the bundled Python runtime has no pytest; a fresh backend pytest rerun is therefore blocked until the local environment is resynchronized.
- Default Playwright E2E: 108 passed and 6 intentional skips; release-only Pages specs are excluded from the default suite.
- Live-origin static/model verification: not confirmed in this local pass; the workflow is published and wired as a post-deploy job, while the model proof remains owner/license-gated.
