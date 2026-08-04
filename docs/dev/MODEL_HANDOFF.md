# Orbit Model Handoff

Owner: the interface between the external training/publishing cycle and the LFM-ORBIT runtime. This is a stable contract, not a training progress log; unfinished release gates live in [TODO.md](TODO.md).

## Current artifact

The published handoff is `Shoozes/lfm2.5-450m-vl-orbit-satellite` at revision `0fc90b8caaa6b8e07d1dc0a9125969c2730e4353`. The primary artifact is `LFM2.5-VL-450M-Q4_0.gguf`, `219310432` bytes, SHA-256 `9e488f38f64dc4b897c768bec4b37ba01a671309910fd08c470220fa244e14f6`. The authoritative identity is [orbit_model_handoff.json](../model/orbit_model_handoff.json); the browser manifest is [model-manifest.json](../../source/frontend/hosted/model-manifest.json).

The bundle is a LiquidAI/LFM2.5-VL-450M-derived `vlm_sft` handoff with image-text training metadata, but the normal Orbit GGUF path reasons over text evidence packets. It must not be described as image-conditioned inference. Retained-frame image review is a separate optional adapter and is only enabled when `/api/analysis/status` reports `image_conditioned_runtime_enabled=true`.

## Runtime contract

The full app resolves the model through [model_manifest.py](../../source/backend/core/model_manifest.py) and stores local artifacts under:

```text
runtime-data/models/lfm2.5-vlm-450m/
```

Required identity fields are `repo_id`, `revision`, `model_filename`, `mmproj_filename`, `base_model`, `quantization`, `task`, and the training manifest reference. The current handoff has no `mmproj` file. A compatible projector path is not shipped.

Fetch and verify the full local runtime from the repository root:

```powershell
.\run.ps1 -Install
```

```bash
./run.sh --install
```

The launcher validates the downloaded size and manifest, installs the model extra, and runs `smoke_satellite_model.py --require-present`. Fallback analysis is a development path and must not be presented as a loaded GGUF.

## Hosted browser boundary

The hosted app is a separate frontend-only contract. Vite emits [model-manifest.json](../../source/frontend/hosted/model-manifest.json) only when `VITE_HOSTED_MODEL_ENABLED=true`; the Pages workflow sets it to `false`. A model-enabled build fetches the pinned browser artifact over HTTPS and performs short local text reasoning over saved packages. It does not use FastAPI, provider credentials, live imagery, or browser-side image input.

When cross-origin isolation is unavailable, `useBrowserModel.ts` selects Wllama single-thread loading. This is a compatibility fallback, not proof of iOS support; a real HTTPS device run remains required before public mobile wording.

## Capability status

The status APIs should distinguish these values:

```json
{
  "training_modality": "image_text",
  "image_training_verified": true,
  "mmproj_present": false,
  "runtime_inference_mode": "text_evidence_packet",
  "image_conditioned_runtime_enabled": false
}
```

Correct operator wording:

```text
Training modality: image-text SFT in the fetched handoff
Runtime mode: text evidence-packet reasoning
Image-conditioned review: only when analysis status reports it enabled
```

## Dataset bridge

The exporter [export_orbit_dataset.py](../../source/backend/scripts/export_orbit_dataset.py) carries replay/cache provenance, optional `visual_model_review`, evidence packets, temporal sequence metadata, and valid weak-negative controls into JSONL. Rows with visual review can be image/text training rows; rows without it remain valid evidence-packet rows. Retagging deduplicates assets by SHA-256 and preserves source references.

The loop is intentionally outside the app UI:

1. Export and retag Orbit evidence.
2. Train/package an external handoff and manifest.
3. Publish the pinned artifact.
4. Fetch and validate it in Orbit.
5. Replay evidence and run promotion checks before replacing a local handoff.

Replay Cache comparisons are additive. A cached rescan preserves the original proof and records `cached_rescan_current_model` for the new scoring basis.

## Optional image review

The optional backend `vision` extra supports the bounded `transformers_vlm` adapter when explicitly configured. The `llama_cpp_mmproj` label remains unavailable until a compatible projector path is wired and proven. Do not promote either capability through hosted UI or documentation without the status contract and image-sensitive smoke evidence.
