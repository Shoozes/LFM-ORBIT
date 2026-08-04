# Current Integrity Review

Updated **August 4, 2026**.

This is the canonical short review snapshot. The active backlog and completion conditions live in [TODO.md](TODO.md); historical route and progress detail stays in [archive/summary_bank_history.json](archive/summary_bank_history.json).

## Decision

The hosted application is ready for a Pages project-path build, but the public deployment is not yet proven. The local Pages bundle now builds under `/LFM-ORBIT/`, keeps first-party assets below that base, and has a deployment workflow. A live-origin model proof and owner-approved model licensing decision remain release gates.

## Evidence matrix

| Surface | State | Evidence |
| --- | --- | --- |
| Hosted architecture | Green | Isolated hosted entry, saved packages, browser-local text reasoning, and no backend dependency. |
| Pages project path | Green locally | `build:pages` plus `test:hosted:pages` exercise `/LFM-ORBIT/`, JSON, CSS, JavaScript, WASM, favicon, and all promoted package stills. |
| Pages workflow | Green in-repo | `.github/workflows/pages.yml` builds only `dist-pages`, uploads the Pages artifact, and deploys with the `github-pages` environment. |
| Public origin | Unproven | No deployment or post-deployment real-model run has been performed from the live Pages URL. |
| Model licensing | Owner gate | The derivative handoff is currently labeled `mit`, while the upstream LiquidAI model card is labeled `lfm1.0`; redistribution and attribution terms still need owner/legal confirmation. |
| Full-app runtime | Green for default browser suite | The August 4 default Playwright suite reran with `108 passed, 6 skipped`; the root launcher/GGUF lane remains a separate historical proof and was not rerun in this pass. |

## Changes in this pass

- Added one configurable Vite base for local root, Pages project-path, and custom-domain-root builds.
- Added a shared safe asset resolver and changed hosted package paths to repo-relative values.
- Required every promoted hosted package to carry an accessible visual asset; promoted the matching fireline source frame.
- Added a Pages-subpath Playwright smoke and a least-privilege Pages deployment workflow.
- Added an explicit live-origin Playwright harness that runs only with `HOSTED_PAGES_URL` and records two model/chat timing passes.
- Replaced the Starlette/httpx TestClient warning path with the locked `httpx2` development dependency.
- Added the missing review snapshot and routed it from the docs index/context bank instead of expanding progress notes across product docs.

## Release gates

- **Live-origin model proof:** run only after a successful deployment; prove the sealed manifest, pinned revision, initial 219 MB load, local response, no backend traffic, and cached reload.
- **Model license decision:** confirm the derivative GGUF, upstream base terms, quantization/redistribution rights, attribution, and displayed metadata before public promotion.
- **Archive references:** verify the preserved `hackathon` branch and immutable tag resolve to the intended pre-modernization submission, or record the owner-approved alternative.

## Verification used for this snapshot

- Bundled Node TypeScript check: passed.
- Pages production build: passed.
- Pages-subpath Playwright smoke: passed through the approved external browser runtime; managed Chromium launch remains `spawn EPERM`.
- Browser model unit tests: 8 passed.
- Backend/docs/import/CI verification: 554 tests passed through the approved locked repository environment with zero warnings and no app test failures.
- Default Playwright E2E: 108 passed and 6 intentional skips; release-only Pages specs are excluded from the default suite.
- Live-origin model verification: not run; the Pages workflow is present locally but has not been deployed from these changes.
