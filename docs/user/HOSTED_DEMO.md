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
- One public GGUF fetch action using Wllama in the browser through WebAssembly; the hero action starts that browser-local load directly after the static manifest has shown the exact model identity, size, license, and text-only capability.
- Three clearly labeled saved evidence packages loaded from a validated static manifest; they are not live satellite data.
- Each package uses schema v2 and carries a local replay id, source manifest path, bbox, observation window, scoring basis, runtime truth, imagery origin, and candidate/review/abstain decision.
- A local Orbit Classroom chat grounded in the selected package.
- Short teaching cards covering browser constraints, evidence boundaries, and edge-AI tradeoffs.
- Reviewed Atacama and Greenland evidence stills; the fireline packet remains a text-first review story until a matching public still is promoted.

The browser model is pinned by `source/frontend/public/model-manifest.json` to Hugging Face revision `0fc90b8caaa6b8e07d1dc0a9125969c2730e4353`, with a 219,310,432-byte inventory and SHA-256 `9e488f38f64dc4b897c768bec4b37ba01a671309910fd08c470220fa244e14f6`. The route reads this local manifest on entry without fetching the GGUF. After the visitor chooses fetch, it verifies the remote pointer and byte count before Wllama loads the public artifact; later visits may use browser cache.

The hosted entry point never starts or calls an Orbit model server. The browser fetches the pinned artifact from Hugging Face, loads Wllama’s local WebAssembly runtime, and keeps the saved-package experience available if WebAssembly, storage, device-memory limits, or network policy prevent model loading. The page probes those browser signals before enabling fetch; a disabled fetch button means “saved packages only,” not a backend outage.

The current browser path sends text package metadata to Wllama. It is text reasoning over saved Orbit evidence, not image-conditioned VLM inference; the `VL` name reflects the upstream artifact lineage, not a browser image-input guarantee. Download cancellation returns to idle, while generation cancellation returns to the reusable local-ready state. The evidence card keeps the replay/scoring provenance visible so a generated explanation cannot be mistaken for a live provider result.

The hosted manifest currently labels the Shoozes handoff repository `mit`. The upstream [LiquidAI/LFM2.5-VL-450M model card](https://huggingface.co/LiquidAI/LFM2.5-VL-450M) labels the base model `lfm1.0`; treat the complete redistribution/attribution decision for the handoff bundle as pending legal review rather than assuming the repository label settles inherited terms.

## Deploy

Build the hosted presentation with `npm run build:hosted` from `source/frontend`, then serve `source/frontend/dist-hosted` as a static site with SPA fallback. The hosted build renders at `/`; `/hosted` remains the local full-app build alias. The hosted route must not be configured as a backend/API proxy.

The browser demo is device-dependent: model memory, download time, WebAssembly support, and browser storage vary. If local inference cannot start, the page should show the error and keep the saved evidence and teaching content usable.

## Verify

```bash
cd source/frontend
npm run test:unit
npm run lint
npm run test:hosted
npm run verify:hosted
```

The focused unit command covers capability, cancellation, response parsing, and actionable error branches without a model download. The opt-in `npm run test:hosted:model` command performs the slower real 219 MB browser fetch and proves Wllama load plus local generation without starting FastAPI. `npm run test:hosted:model:build` repeats that fetch-and-generate proof against the production `dist-hosted` preview and also runs the static MIME check through `npm run verify:hosted`. These commands are intentionally excluded from both the normal hosted smoke and the full-app E2E suite because they depend on network, device memory, and browser cache state.

The full app remains available at `/` and through the existing launcher path.
