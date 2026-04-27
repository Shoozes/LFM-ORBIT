# Orbit Model Handoff

Updated April 27, 2026.

## Purpose

This document defines Orbit's external model-bundle contract for trained satellite artifacts.
It is a contract/reference doc; the active backlog lives in `docs/TODO.md` to keep progress tracking centralized.

The immediate goal is operational:

- package the trained model outside Orbit
- optionally publish the bundle to Hugging Face
- fetch the published artifact into Orbit
- keep Orbit's runtime model resolution reproducible
- keep replay/demo review aligned with the same artifact shape the runtime uses

## Current Runtime Constraint

Orbit's current local satellite inference path is still GGUF chat-style reasoning over scored metadata in [inference.py](</C:/Users/jc816/OneDrive/Desktop/Gen-App/LFM Orbit/source/backend/core/inference.py>).

That means:

- Orbit can resolve a trained artifact through a manifest instead of one hardcoded file path
- Orbit does not yet run a fully image-conditioned multimodal `mmproj` inference path in production
- a published `mmproj` can still be carried in the handoff manifest now so the artifact chain is ready for the next adapter step

## Orbit Runtime Contract

Orbit resolves the optional satellite model through [model_manifest.py](</C:/Users/jc816/OneDrive/Desktop/Gen-App/LFM Orbit/source/backend/core/model_manifest.py>).

Default runtime location:

```text
runtime-data/models/lfm2.5-vlm-450m/
```

Runtime manifest path:

```text
runtime-data/models/lfm2.5-vlm-450m/model_manifest.json
```

Important fields:

- `repo_id`
- `revision`
- `model_subdir`
- `model_filename`
- `mmproj_filename`
- `base_model`
- `quantization`
- `task`
- `training_result_manifest`

## Fetching Into Orbit

Orbit includes a fetch utility:

[fetch_satellite_model.py](</C:/Users/jc816/OneDrive/Desktop/Gen-App/LFM Orbit/source/backend/scripts/fetch_satellite_model.py>)

Examples:

```powershell
cd C:\Users\jc816\OneDrive\Desktop\Gen-App\LFM Orbit\source\backend
python scripts\fetch_satellite_model.py `
  --repo-id your-org/lfm-orbit-satellite `
  --model-filename LFM2.5-VL-450M-Q4_0.gguf
```

Using a local handoff manifest:

```powershell
cd C:\Users\jc816\OneDrive\Desktop\Gen-App\LFM Orbit\source\backend
python scripts\fetch_satellite_model.py `
  --source-manifest C:\path\to\model-bundle\orbit_model_handoff.json
```

If the Hugging Face repo is private or gated, set `HF_TOKEN` before running the fetch.

## Environment Overrides

Orbit supports these optional overrides:

- `CANOPY_SENTINEL_MODEL_MANIFEST`
- `CANOPY_SENTINEL_MODEL_SUBDIR`
- `CANOPY_SENTINEL_MODEL_FILENAME`
- `CANOPY_SENTINEL_MODEL_MMPROJ_FILENAME`
- `CANOPY_SENTINEL_MODEL_REPO_ID`
- `CANOPY_SENTINEL_MODEL_REVISION`

These are useful for local testing and temporary artifact swaps.

## Recommended Bundle Shape

Any external training or publishing workflow should stage a folder that contains:

- primary model artifact, usually `*.gguf`
- optional `*mmproj*.gguf`
- `training_result_manifest.json`
- `orbit_model_handoff.json`
- optional `README.md`

The handoff manifest is the bridge between external training output and Orbit runtime.

## Orbit Dataset Bridge

Orbit exports a stronger training bundle through `source/backend/scripts/export_orbit_dataset.py`.

The export now includes:

- gallery-backed confirmed positives
- alert-only positives with a materialized `context_thumb` from fetched API imagery when pin coordinates are available
- recent ground-agent `reject` outcomes as weak negative/control rows
- cached API observation-store rows when the CLI is run without `--no-api-observations`
- persisted maritime/lifeline monitor-report JSON rows when passed through `--monitor-reports-dir`
- SimSat Sentinel, optional SimSat Mapbox, Sentinel Hub, NASA, GEE, seeded-cache, and offline provenance fields where available
- temporal use-case metadata and examples for deforestation, wildfire, civilian lifeline disruption, maritime monitoring, ice-cap growth, floods, agriculture, urban expansion, mining, and generic temporal review
- chat-style `training.jsonl`, `train_training.jsonl`, and `eval_training.jsonl` files for supervised data-refinement workflows
- second-pass asset retagging through `scripts/retag_training_assets.py`, including deduplicated still images, sampled timelapse frames, ordered temporal sequence rows, Hugging Face ImageFolder-compatible `images/ + metadata.jsonl`, and provider adapters for heuristic/manual queue, Ollama vision models, or OpenAI-compatible vision models
- explicit metadata fields such as `target_action`, `target_category`, `target_task`, and `label_tier`

Current ground rejects are useful as weak negatives because they come from the real validation loop, but they are still not the same as operator-reviewed gold controls.

The temporal-prep lane is intentionally strict about timelapse integrity: training rows should treat a video as temporal evidence only when it contains at least two contextual imagery slices. Static single-image color shifts are flagged as invalid evidence.

Timelapse videos are processed in two layers:

- sampled frames become unique image assets for normal image-caption/classification/SFT workflows
- the ordered frame list also becomes `temporal_sequences.jsonl` and `training_temporal_sequences.jsonl`, so temporal context is preserved for sequence-aware training and evaluation

The retagging step deduplicates by SHA-256. If multiple samples point at the same image or extracted frame, Orbit writes one training asset and records every source sample under `references`.

Orbit's observation cache is now stricter about handoff readiness:

- a record is only marked `training_ready` after both satellite and ground observations exist for the same region
- single-role cached notes are still useful context, but they should not be treated as paired supervision during downstream import

Orbit also now supports seeded replay manifests for completed missions. That is useful for model handoff work in two ways:

- a trained-model review can be demonstrated against a fixed, inspectable mission instead of live scan timing
- future model eval packs can mirror the replay manifest structure so mission evidence and modeling artifacts stay aligned

For deterministic local review, Orbit exposes a runtime reset path before replay load:

1. `POST /api/runtime/reset`
2. `POST /api/replay/load/{replay_id}`

## Integration Sequence

1. Export Orbit samples with `source/backend/scripts/export_orbit_dataset.py`.
2. Import, train, and package the model in an external training workspace.
3. Generate `orbit_model_handoff.json`.
4. Optionally upload the staged folder to Hugging Face.
5. Run Orbit's fetch script against the handoff manifest or the repo directly.
6. Verify Orbit status at `/api/inference/status` or `/api/analysis/status`.

## Tracked Runtime Gaps

This handoff closes artifact resolution and publication flow. The runtime gaps below are tracked in `docs/TODO.md`:

- a production multimodal image-input adapter inside Orbit
- automatic `mmproj` use in the current `llama_cpp` path
- benchmark gating inside Orbit itself
