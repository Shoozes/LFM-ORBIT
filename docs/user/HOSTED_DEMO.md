# Hosted browser demo

The hosted route is a separate portfolio presentation. It leaves the full Orbit application at `/`, and gives visitors a short, browser-only path at `/hosted`. The full-app link is a local-lab affordance; it is not a claim that a static host can run FastAPI.

## Start locally

```powershell
.\run.ps1 -Hosted
```

```bash
./run.sh --hosted
```

Open `http://127.0.0.1:5173/hosted`. This path installs only the frontend; it does not start FastAPI, SimSat, a provider, or the backend model runtime.

## What the visitor sees

- A terrain shader presentation adapted from the HAIO WebGL landing-page direction.
- One public GGUF fetch action using Wllama in the browser through WebAssembly for model-enabled local builds; the hero action starts that browser-local load only after the static manifest has shown the exact model identity, size, license, and text-only capability. The Pages build is intentionally saved-packages-only until redistribution terms are approved.
- Three clearly labeled saved evidence packages loaded from a validated static manifest; they are not live satellite data.
- Each package uses schema v2 and carries a local replay id, source manifest path, bbox, observation window, scoring basis, runtime truth, imagery origin, and candidate/review/abstain decision.
- A local Orbit Classroom chat grounded in the selected package.
- Short teaching cards covering browser constraints, evidence boundaries, and edge-AI tradeoffs.
- Reviewed Atacama, Greenland, and Southeast US fireline evidence stills; every promoted package now has a matching visual asset and accessible alt text.

The browser model is pinned by `source/frontend/hosted/model-manifest.json` to Hugging Face revision `0fc90b8caaa6b8e07d1dc0a9125969c2730e4353`, with a 219,310,432-byte inventory and SHA-256 `9e488f38f64dc4b897c768bec4b37ba01a671309910fd08c470220fa244e14f6`. The manifest is emitted into a build only when the model policy is enabled; a model-enabled route reads it before any GGUF request, then verifies the remote pointer and byte count before Wllama loads the public artifact. The committed Pages workflow sets `VITE_HOSTED_MODEL_ENABLED=false`, so its artifact contains no model manifest, Wllama runtime, or model request while redistribution terms are reviewed.

The hosted entry point never starts or calls an Orbit model server. A model-enabled browser route fetches the pinned artifact from Hugging Face, loads Wllama’s local WebAssembly runtime, and keeps the saved-package experience available if secure-context, WebAssembly, storage, device-memory limits, or network policy prevent model loading. Without cross-origin isolation, the loader chooses Wllama single-thread mode for the safer GitHub Pages/iOS Safari path. The page probes those browser signals before enabling fetch; a saved-only build is an intentional portfolio mode, not a backend outage.

The current browser path sends text package metadata to Wllama. It is text reasoning over saved Orbit evidence, not image-conditioned VLM inference; the `VL` name reflects the upstream artifact lineage, not a browser image-input guarantee. Download cancellation returns to idle, while generation cancellation returns to the reusable local-ready state. The evidence card keeps the replay/scoring provenance visible so a generated explanation cannot be mistaken for a live provider result.

The hosted manifest currently labels the Shoozes handoff repository `mit`. The upstream [LiquidAI/LFM2.5-VL-450M model card](https://huggingface.co/LiquidAI/LFM2.5-VL-450M) labels the base model `lfm1.0`; treat the complete redistribution/attribution decision for the handoff bundle as pending legal review rather than assuming the repository label settles inherited terms. This is why the public Pages model lane is disabled until the owner can reconcile the exact pinned revision and notices.

## Deploy

Build the hosted presentation with `npm run build:hosted` from `source/frontend`, then serve `source/frontend/dist-hosted` at a domain root. For the standard repository Pages site, use `npm run build:pages`; it emits `dist-pages` with the project base supplied by `VITE_PUBLIC_BASE` (the committed workflow supplies `/<repository>/`). The hosted build renders at `/`; `/hosted` remains the local full-app build alias. The hosted route must not be configured as a backend/API proxy.

The committed `.github/workflows/pages.yml` runs the hosted unit checks, installs Chromium and its Linux dependencies before browser checks, builds a saved-packages-only Pages artifact, and deploys only `dist-pages` through the `github-pages` environment. A post-deploy static-origin smoke then checks the public project path, MIME types, package manifest, images, favicon, and explicit absence of model runtime assets without downloading model weights. A live-origin model proof and owner-approved model licensing decision are still required before calling the public model lane release-ready.

## Public HTTPS and iOS

Use the GitHub Pages project URL over HTTPS, for example `https://<owner>.github.io/<repository>/`, and enable GitHub's **Enforce HTTPS** setting before promoting any model-enabled build. GitHub Pages supports HTTPS for Pages sites and correctly configured custom domains; the model manifest and artifact URLs are also HTTPS, so the browser does not cross a mixed-content boundary. See [GitHub's HTTPS guidance](https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https).

HTTPS is necessary but does not prove that an iPhone or iPad has enough memory and storage for a 219 MB model. The capability gate, single-thread fallback, and saved-evidence path are deliberate. A physical iOS Safari run must still prove first load, generation, cancellation, and reload/cache behavior before the model lane is advertised as iOS-ready.

To run the no-weight public-origin smoke after deployment:

```powershell
$env:HOSTED_PAGES_URL = "https://<owner>.github.io/<repository>/"
npm run test:hosted:pages:live:static
```

After deployment, run the release-only live proof from `source/frontend` with the exact trailing-slash Pages URL:

```powershell
$env:HOSTED_PAGES_URL = "https://<owner>.github.io/<repository>/"
npm run test:hosted:pages:live
```

The live proof runs the browser model/chat path twice and attaches timing evidence including model transfer bytes and browser cache/service-worker provenance. It fails closed when `HOSTED_PAGES_URL` is missing and is intentionally not part of normal CI because each pass can download the 219 MB model artifact. The static proof is the required lightweight post-deploy CI check; the model proof stays release-only.

The browser demo is device-dependent: model memory, download time, WebAssembly support, and browser storage vary. If local inference cannot start, the page should show the error and keep the saved evidence and teaching content usable.

## Verify

```bash
cd source/frontend
npm run test:unit
npm run lint
npm run test:hosted
npm run verify:hosted
npm run build:pages
npm run test:hosted:pages
```

The focused unit command covers build policy, secure-context capability, cancellation, response parsing, and actionable error branches without a model download. The opt-in `npm run test:hosted:model` command performs the slower real 219 MB browser fetch and proves Wllama load plus local generation without starting FastAPI. `npm run test:hosted:model:build` repeats that fetch-and-generate proof against the production `dist-hosted` preview and also runs the static MIME check through `npm run verify:hosted`. These commands are intentionally excluded from both the normal hosted smoke and the full-app E2E suite because they depend on network, device memory, browser cache state, and (for iOS) a physical device.

The full app remains available at `/` and through the existing launcher path.
