# Hosted browser demo

Owner: the hosted frontend and its deployment handoff. This route is a backend-free presentation of validated saved evidence packages; the full local app is described in [DEMO_GUIDE.md](DEMO_GUIDE.md).

## What it is

The hosted route renders at `/hosted` locally and at the configured project path on GitHub Pages. It loads `source/frontend/public/demo-packages/index.json`, validates repo-relative package assets, and presents replay provenance without provider credentials or FastAPI.

Current deployment: [https://shoozes.github.io/LFM-ORBIT/](https://shoozes.github.io/LFM-ORBIT/). The Pages deployment and deployed static-origin smoke passed for the current `main` commit; HTTPS is enforced by the repository Pages configuration.

The default Pages build is deliberately model-free. It emits no browser model manifest, Wllama runtime, or model weights while redistribution and attribution terms are unresolved. Browser text reasoning is an explicit opt-in local capability, not image-conditioned VLM inference.

## Start locally

```powershell
.\run.ps1 -Hosted
```

Then open `http://127.0.0.1:5173/hosted`. For a production-style preview:

```bash
cd source/frontend
npm ci
npm run build:hosted
npm run test:hosted:build
```

## Build and deploy

The repository workflow in `.github/workflows/pages.yml` builds `dist-pages` with:

```text
VITE_HOSTED_MODEL_ENABLED=false
VITE_PUBLIC_BASE=/<repository-name>/
```

It runs unit checks and a project-path preview smoke, uploads the artifact, deploys through the `github-pages` environment, and runs a static-origin smoke. Pages must be configured to publish from **GitHub Actions** before `configure-pages` can succeed.

Do not enable the public model flag until the [model handoff](../dev/MODEL_HANDOFF.md) and [third-party notices](../legal/THIRD_PARTY_NOTICES.md) are approved.

## Current capabilities and limits

- Saved package cards show source replay, cached imagery origin, review summary, scoring basis, and candidate/review/abstain retention.
- The hosted page does not call backend APIs, live providers, or WebSockets.
- A model-enabled HTTPS build uses the pinned 219 MB artifact and Wllama; it selects single-thread loading when cross-origin isolation is unavailable for safer mobile compatibility.
- iOS Safari support is a release claim only after a real device proof. Secure-context, storage, WebAssembly, cancellation, reload, and cached reuse must be tested on the deployed HTTPS origin.

## Verify

```bash
cd source/frontend
npm run test:unit
npm run build:pages
npm run test:hosted:pages
```

For the deployed static proof, set `HOSTED_PAGES_URL` to the exact trailing-slash HTTPS URL and run:

```bash
npm run test:hosted:pages:live:static
```

The model-enabled build and model-fetch proof are release-only commands. See [TODO.md](../dev/TODO.md) for the remaining external gates.
