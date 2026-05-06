# Orbit Model Handoff

Updated May 3, 2026.

## Purpose

This document defines Orbit's external model-bundle contract for trained satellite artifacts.
It is a contract/reference doc; the active backlog lives in `TODO.md` to keep progress tracking centralized.

The immediate goal is operational:

- package the trained model outside Orbit
- optionally publish the bundle to Hugging Face
- fetch the published artifact into Orbit
- keep Orbit's runtime model resolution reproducible
- keep replay/demo review aligned with the same artifact shape the runtime uses

## Current Runtime Constraint

Orbit's current local satellite inference path is still GGUF chat-style reasoning over scored metadata in [inference.py](../../source/backend/core/inference.py).

That means:

- Orbit can resolve a trained artifact through a manifest instead of one hardcoded file path
- Orbit can report whether the NM-UNI training manifest contains image rows through `/api/analysis/status`; the current fetched bundle reports image-text training rows and image blocks
- Orbit does not yet run a fully image-conditioned multimodal `mmproj` inference path in production
- a published `mmproj` can still be carried in a future handoff manifest so the artifact chain is ready for the next adapter step
- the current NM-UNI Orbit bundle is a trained GGUF handoff without an `mmproj` file

## Orbit Runtime Contract

Orbit resolves the trained satellite model through [model_manifest.py](../../source/backend/core/model_manifest.py).

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

[fetch_satellite_model.py](../../source/backend/scripts/fetch_satellite_model.py)

Default trained Orbit bundle:

- Hugging Face repo: [Shoozes/lfm2.5-450m-vl-orbit-satellite](https://huggingface.co/Shoozes/lfm2.5-450m-vl-orbit-satellite)
- Primary GGUF: `LFM2.5-VL-450M-Q4_0.gguf`
- Handoff manifest: `orbit_model_handoff.json`
- Training manifest: `training_result_manifest.json`
- Base model: `LFM2.5-VL-450M`
- Training method: `vlm_sft`
- Task: `wildfire_detection`
- Training rows: `5670`
- Multimodal rows: `5670`
- Image blocks: `6758`
- Eval rows: `630`

The training target is reviewed Orbit evidence tuples with image chip, bbox, task, model answer, confidence, provenance, and abstain labels. Promotion metrics should cover downlink decision precision/recall, abstain precision, and grounded bbox agreement.

The normal launcher path is:

```powershell
cd <repo-root>
.\run.ps1 -Install
```

```bash
./run.sh --install
```

The production launcher path downloads the trained handoff, installs the `model` extra (`llama-cpp-python`), and runs `scripts/smoke_satellite_model.py --require-present --max-tokens 8`. If the GGUF runtime cannot load, option 1 fails before the app starts; fallback analysis is development-only, not the hackathon path.

Direct script usage:

```powershell
cd <repo-root>\source\backend
python scripts\fetch_satellite_model.py
```

Using a local handoff manifest:

```powershell
cd <repo-root>\source\backend
python scripts\fetch_satellite_model.py `
  --source-manifest path/to/model-bundle/orbit_model_handoff.json
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

The published GGUF contains a newer Hugging Face chat template that older local `llama_cpp` builds do not parse because of the Jinja `{% generation %}` tag. Orbit therefore defaults `CANOPY_SENTINEL_LLAMACPP_CHAT_FORMAT=chatml` and `CANOPY_SENTINEL_LLAMACPP_PATCH_CHAT_TEMPLATE=true` so the local runtime can load the GGUF and use Orbit's own evidence-packet prompt format.

Direct image inference remains explicitly gated:

- `ORBIT_IMAGE_CONDITIONED_INFERENCE=false`
- `ORBIT_IMAGE_INFERENCE_BACKEND=none`
- `ORBIT_REQUIRE_MMPROJ_FOR_IMAGE_INFERENCE=true`

Supported backend labels are `none`, `llama_cpp_mmproj`, and `transformers_vlm`. The current Orbit code reports these as status flags only; it does not claim `image_conditioned_runtime_enabled=true` until an adapter passes real image pixels into the runtime.

## Runtime Capability Contract

Orbit reports the handoff truth through `/api/inference/status` and `/api/analysis/status`.

Current expected fields for the published NM-UNI handoff are:

```json
{
  "training_modality": "image_text",
  "image_training_verified": true,
  "training_train_rows": 7245,
  "training_multimodal_rows": 7245,
  "training_image_blocks": 8335,
  "training_eval_rows": 805,
  "mmproj_present": false,
  "runtime_inference_mode": "text_evidence_packet",
  "image_conditioned_runtime_enabled": false
}
```

The correct operator wording is:

```text
Training modality: image-text SFT in the fetched handoff
Runtime mode: text evidence-packet reasoning
Direct image inference: unavailable until mmproj/native VLM runtime is present
```

Do not say the GGUF sees images unless a runtime adapter and smoke test prove image-sensitive output from actual image inputs.

## Recommended Bundle Shape

Any external training or publishing workflow should stage a folder that contains:

- primary model artifact, usually `*.gguf`
- optional `*mmproj*.gguf`
- `training_result_manifest.json`
- `orbit_model_handoff.json`
- optional `README.md`

The handoff manifest is the bridge between external training output and Orbit runtime.

## NM-UNI Role

The current training/publish partner is the local NM-UNI training workspace.
NM-UNI is responsible for importing Orbit exports, preparing Liquid training runs, quantizing trained outputs to GGUF, staging `orbit_model_handoff.json`, and optionally publishing a Hugging Face model repo.
Orbit is responsible for consuming that bundle and validating it against SimSat/replay evidence.

Current published bundle:

- repo: `Shoozes/lfm2.5-450m-vl-orbit-satellite`
- generated at: `2026-05-06T00:00:00Z`
- training method: `vlm_sft`
- task: `orbit-satellite-triage`
- train rows: `7245`
- multimodal rows: `7245`
- image blocks: `8335`
- eval rows: `805`
- promotion gate: not required in `training_result_manifest.json`

Treat this as the trained runtime artifact for evidence-packet and bbox JSON reasoning. Its training manifest now includes image-text rows, but Orbit still must not describe runtime inference as image-conditioned until a runtime adapter passes pixels into the model and a smoke test proves image-sensitive output.

Do not move NM-UNI's training UI or provider management into Orbit. Keep Orbit's hackathon path centered on DPhi SimSat (`simsat_sentinel`), bundled replay fixtures, and manifest-driven model consumption.

## Orbit Dataset Bridge

Orbit exports a stronger training bundle through `source/backend/scripts/export_orbit_dataset.py`.

The export now includes:

- gallery-backed confirmed positives
- alert-only positives with a materialized `context_thumb` from fetched API imagery when pin coordinates are available
- recent ground-agent `reject` outcomes as weak negative/control rows
- cached API observation-store rows when the CLI is run without `--no-api-observations`
- direct replay-cache rows when the CLI is run with `--include-seeded-cache`
- persisted maritime/lifeline monitor-report JSON rows when passed through `--monitor-reports-dir`
- SimSat/Mapbox through DPhi Space SimSat as the hackathon satellite-data API family: default SimSat Sentinel scanning, optional SimSat Mapbox imagery/context, direct Sentinel Hub, NASA, GEE, replay-cache, and offline provenance fields where available
- temporal use-case metadata and examples for deforestation, wildfire, civilian lifeline disruption, maritime monitoring, ice/snow extent, legacy ice-cap visual review, floods, agriculture, urban expansion, mining, and generic temporal review
- chat-style `training.jsonl`, `train_training.jsonl`, and `eval_training.jsonl` files for supervised data-refinement workflows
- second-pass asset retagging through `scripts/retag_training_assets.py`, including deduplicated still images, sampled timelapse frames, ordered temporal sequence rows, Hugging Face ImageFolder-compatible `images/ + metadata.jsonl`, and provider adapters for heuristic/manual queue, Ollama vision models, or OpenAI-compatible vision models
- optional Hugging Face dataset upload through `scripts/upload_orbit_dataset_hf.py`, using `HF_TOKEN`, `HUGGINGFACE_HUB_TOKEN`, or a local developer token file
- explicit metadata fields such as `target_action`, `target_category`, `target_task`, and `label_tier`
- `orbit_training_contract_v1` metadata for review status, localization fields, evidence requirements, and NM-UNI import behavior
- PNG-rasterized context thumbnails even when the runtime thumbnail fallback started as SVG

Current ground rejects are useful as weak negatives because they come from the real validation loop, but they are still not the same as operator-reviewed gold controls.

The temporal-prep lane is intentionally strict about timelapse integrity: training rows should treat a video as temporal evidence only when it contains at least two contextual imagery slices. Static single-image color shifts are flagged as invalid evidence.

Timelapse videos are processed in two layers:

- sampled frames become unique image assets for normal image-caption/classification/SFT workflows
- the ordered frame list also becomes `temporal_sequences.jsonl` and `training_temporal_sequences.jsonl`, so temporal context is preserved for sequence-aware training and evaluation

The retagging step deduplicates by SHA-256. If multiple samples point at the same image or extracted frame, Orbit writes one training asset and records every source sample under `references`.

Orbit's observation cache is now stricter about handoff readiness:

- a record is only marked `training_ready` after both satellite and ground observations exist for the same region
- single-role cached notes are still useful context, but they should not be treated as paired supervision during downstream import

Orbit also now supports curated replay manifests and dynamic Fast Replay entries from valid cached API WebMs. That is useful for model handoff work in two ways:

- a trained-model review can be demonstrated against a fixed, inspectable mission instead of realtime scan timing
- the same prior replay metadata can be rescanned after a model/runtime update to compare behavior
- future model eval packs can mirror the replay manifest structure so mission evidence and modeling artifacts stay aligned

For deterministic local review, Orbit exposes a runtime reset path before replay load:

1. `POST /api/runtime/reset`
2. `POST /api/replay/load/{replay_id}`

Completed runtime surfaces can also be packaged with:

1. `GET /api/replay/snapshot/export`
2. `POST /api/replay/snapshot/import`

This snapshot path is for packaging completed realtime or replay missions. Bundled replay packs remain the preferred showcase walkthrough path.

Current replay cache includes Rondonia replay coverage plus cached API missions for Pakistan Manchar Lake flooding, Atacama mining, Greenland ice/snow extent metadata scoring, Suez maritime queueing, Singapore maritime anchorage, Kansas crop phenology, Delhi urban expansion, Highway 82 Georgia wildfire candidate, Mauna Loa, Lake Urmia, Black Rock City, Lahaina, Kakhovka, Kilauea, and Lake Mead. These are development and proof fixtures that avoid repeated API usage; they do not make Sentinel Hub part of the default hackathon runtime. The legacy Greenland ice-edge abstain WebM is excluded from Fast Replay because it fails the structural timelapse-integrity gate. These are intentionally small repo fixtures, not a full training corpus.

Recorded proof demos now export both the full proof screen and the isolated `evidence-frame.png` surface. That keeps model/dataset review aligned with the exact visible evidence frame used in Proof Mode, not just the longer Playwright recording.

Orbit also stores timestamped watch manifests under `source/backend/assets/watchlists/`. These are source-backed risk watches, not labels. The SPC Day 2 Southern High Plains watch is now promoted only to `incident_report_verified_candidate` after NM Fire Info reported the Sparks Fire in Quay County inside the watch bbox; satellite burn-scar confirmation still requires a separate post-event imagery pass.

Current raw replay/cache export after including the Florida firewatch seed:

- `33` Orbit samples
- `0` cached API observation rows
- `25` replay-cache rows
- `7` visual story frame rows
- `0` monitor-report rows
- `0` mission metadata rows
- `26` rows with timelapse references
- `wildfire` / `fireline` tags plus Sentinel-2 `B12/B08/B04` band stats on `seeded_83e3aea2__83e3aea2`
- `0` local Windows paths in the published raw export JSONL/manifest

Hugging Face upload is wired and completed locally. The dataset is published at `Shoozes/LFM-Orbit-SatData`, with latest raw export commit `b6ef429d958a21dc7690d3f4b7cc4f3bd2088d25`: `records=33`, `seeded_cache_records=25`, `mission_metadata_records=0`, and the Florida firewatch sample tagged as `wildfire` / `fireline` with Sentinel-2 `B12/B08/B04` frame stats. The earlier retagged training export remains reusable for model work when raw replay/cache rows need SFT conversion.

The trained model handoff bundle is published at `Shoozes/lfm2.5-450m-vl-orbit-satellite`. Latest checked revision: `2a8c57cbb7f4dda26d5faff2ec3e31a5cbd2f4b8`. Local fetch with `--force` refreshed `runtime-data/models/lfm2.5-vlm-450m/`; `scripts/smoke_satellite_model.py --require-present --max-tokens 8` passed with `loaded=true` in the launcher-managed Windows backend environment. The manifest reports task `wildfire_detection`, base model `LiquidAI/LFM2.5-VL-450M`, GGUF runtime, `training_modality=image_text`, `image_training_verified=true`, `5670` train rows, `5670` multimodal rows, `6758` image blocks, and `630` eval rows. Runtime remains `text_evidence_packet` because no `mmproj` or direct image-conditioned adapter is wired.

## Integration Sequence

1. Export Orbit samples with `source/backend/scripts/export_orbit_dataset.py --include-seeded-cache --offline-context-thumbnails`.
2. Retag and deduplicate with `source/backend/scripts/retag_training_assets.py --reuse-existing-dir <previous-retagged-folder> --reuse-existing-only` for normal upload refreshes.
3. Import, train, and package the model in an external training workspace.
4. Generate `orbit_model_handoff.json`.
5. Upload the staged folder to Hugging Face.
6. Run Orbit's fetch script against the handoff manifest or the default `Shoozes/lfm2.5-450m-vl-orbit-satellite` repo.
7. Verify Orbit status at `/api/inference/status` or `/api/analysis/status`, including `image_training_verified`, `training_image_blocks`, `mmproj_present`, and `image_conditioned_runtime_enabled`.
8. When a real GGUF is installed, run `python scripts\smoke_satellite_model.py --require-present` from `source/backend`.
9. Use `scripts/evaluate_model.py --baseline-summary ...` to write `comparison.json` and `promotion.json` before promoting a tuned bundle.

## Tracked Runtime Gaps

This handoff closes artifact resolution and publication flow. The runtime gaps below are tracked in `TODO.md`:

- a production multimodal image-input adapter inside Orbit
- automatic `mmproj` use in the current `llama_cpp` path when a compatible projector exists
- native `transformers_vlm` runtime support if the HF checkpoint/LoRA path is the safer image-conditioned adapter
- an image-conditioned smoke test that proves output changes when image pixels change
- replacement visual-summary runtimes for the final selected local model family
