# Orbit Data Folder

This folder is for local data inputs that help Orbit gather, package, retag, and hand off training data. It is not the main runtime cache. Runtime-generated assets normally live under `runtime-data/`, while this folder holds repo-local data packs such as boundaries, local fixtures, or optional operator-managed imports.

## What This Is

Orbit's data cycle is:

1. The app gathers evidence during live missions, seeded replay, monitor previews, imagery fetches, VLM helper calls, and timelapse generation.
2. The backend stores alert metadata, gallery evidence, thumbnails, videos, observations, agent decisions, and monitor reports.
3. `scripts/export_orbit_dataset.py` packages those records into an Orbit dataset export with JSONL manifests and local assets.
4. `scripts/retag_training_assets.py` walks the export, deduplicates images and frames by SHA-256, extracts timelapse frames, preserves temporal sequence context, and retags assets with a chosen provider.
5. The retagged folder can be reviewed locally, loaded as a Hugging Face ImageFolder dataset, uploaded to Hugging Face, or used by external fine-tuning jobs.
6. Trained artifacts can come back through the model handoff/fetch path documented in `docs/MODEL_HANDOFF.md`.

The goal is a closed loop: collect evidence in Orbit, package it cleanly, retag it with a stronger vision model when useful, train or evaluate externally, then bring model artifacts back into Orbit.

## Folder Roles

- `source/backend/data/`
  Repo-local data inputs and fixtures. Keep this small and intentional.
- `source/backend/data/boundaries/`
  Boundary/concession/protected-area inputs used by overlay import tooling.
- `runtime-data/`
  Mutable local runtime state, generated exports, model bundles, and scratch outputs.
- `runtime-data/modeling/orbit-export/`
  Recommended output location for dataset exports.
- `runtime-data/modeling/orbit-export/retagged_training/`
  Recommended output location for retagged image/frame/sequence training data.

## Export Dataset

From the backend folder:

```powershell
cd source/backend
uv run --no-sync python scripts\export_orbit_dataset.py `
  --output-dir ..\..\runtime-data\modeling\orbit-export `
  --monitor-reports-dir ..\..\runtime-data\monitor-reports
```

The export writes:

- `samples.jsonl`
- `train.jsonl`
- `eval.jsonl`
- `training.jsonl`
- `train_training.jsonl`
- `eval_training.jsonl`
- `manifest.json`
- `samples/<sample_id>/sample.json`
- local assets such as `context_thumb.png` and `timelapse.webm`

Export rows include target task/category/action, temporal use-case metadata, alert scores, agent evidence, local imagery/video references, provenance, and weak-negative reject rows when available.

## Retag Assets

Run the second pass after export:

```powershell
cd source/backend
uv run --no-sync python scripts\retag_training_assets.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export `
  --provider heuristic
```

Provider options:

- `heuristic`
  Local metadata-based retagging. No network or model dependency. Good for dry runs and packaging checks.
- `queue`
  Writes `review_queue.jsonl` for manual or external retagging while still packaging deduplicated assets.
- `ollama`
  Sends images to a local Ollama vision model such as Qwen VL.
- `openai`
  Sends images to an OpenAI-compatible vision endpoint. Requires `OPENAI_API_KEY`.

Example with Ollama:

```powershell
uv run --no-sync python scripts\retag_training_assets.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export `
  --provider ollama `
  --model qwen2.5vl:32b
```

Example with OpenAI-compatible vision:

```powershell
$env:OPENAI_API_KEY = "..."
uv run --no-sync python scripts\retag_training_assets.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export `
  --provider openai `
  --model gpt-4.1-mini
```

## Retag Output

The retagger writes:

- `retagged_training/images/`
  Deduplicated image assets and extracted video frames.
- `retagged_training/metadata.jsonl`
  Hugging Face ImageFolder-compatible metadata.
- `retagged_training/retagged_assets.jsonl`
  Full Orbit asset records with provider/model output and source references.
- `retagged_training/training_assets.jsonl`
  Image-level SFT rows.
- `retagged_training/temporal_sequences.jsonl`
  Ordered timelapse sequence records.
- `retagged_training/training_temporal_sequences.jsonl`
  Sequence-level SFT rows.
- `retagged_training/review_queue.jsonl`
  Prompts and references for manual/external review.
- `retagged_training/skipped_assets.jsonl`
  Assets skipped due to unsupported type, unresolved paths, or invalid videos.
- `retagged_training/manifest.json`
  Counts, paths, provider, model, and processing notes.

## Duplicate Policy

Training assets are deduplicated by SHA-256. If the same image or extracted frame appears in multiple samples, Orbit writes one asset row and stores every source under `references`.

This avoids duplicate training examples while preserving auditability.

## Timelapse Policy

Timelapse videos are not trained as opaque video blobs by default.

The retagger:

1. Decodes each video.
2. Rejects videos with fewer than two frames.
3. Samples a configurable number of frames.
4. Deduplicates extracted frames by SHA-256.
5. Writes still-frame training rows.
6. Writes ordered temporal sequence rows so before/after context is preserved.

This matters because a true timelapse must contain multiple contextual satellite imagery slices. A static image that only changes color is invalid temporal evidence and should be reviewed or rejected.

Useful options:

```powershell
uv run --no-sync python scripts\retag_training_assets.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export `
  --video-frame-count 6 `
  --min-video-frames 2
```

## Hugging Face Handoff

The retagged folder is shaped so it can be loaded as an ImageFolder-style dataset:

```python
from datasets import load_dataset

ds = load_dataset(
    "imagefolder",
    data_dir="runtime-data/modeling/orbit-export/retagged_training",
)
```

For sequence-aware training, use `training_temporal_sequences.jsonl` alongside the referenced frame paths in `images/`.

## Optional Tkinter UI

The CLI is the source of truth. `scripts/retag_training_assets_ui.py` is a small Tkinter wrapper around the same retag command; it does not implement separate data logic.

Run it from the backend folder:

```powershell
cd source/backend
uv run --no-sync python scripts\retag_training_assets_ui.py
```

![Orbit training asset retagger Tkinter UI](../../../docs/retag-training-assets-ui.png)

The UI exposes:

- Dataset directory picker.
- Output directory picker.
- Provider selector: `heuristic`, `queue`, `ollama`, `openai`.
- Model text field.
- Frame count and minimum video frames.
- Run button that calls `scripts/retag_training_assets.py` in a subprocess.
- Scrollable output log.
- Manifest summary after a successful run.

Recommended behavior:

- Default `dataset_dir` to `runtime-data/modeling/orbit-export`.
- Default provider to `heuristic`.
- Keep provider secrets in environment variables, not UI fields, especially `OPENAI_API_KEY`.
- Disable the run button while the subprocess is active.
- Never write retag output into `source/backend/data/`; keep generated results under `runtime-data/`.

Tkinter is useful for operator convenience, but the repeatable workflow remains the CLI commands above. If Python was installed without Tkinter, use the CLI directly.

## What Goes Where

Use `source/backend/data/` for:

- Boundary files before import.
- Small local fixtures.
- Human-maintained notes about local datasets.

Use `runtime-data/` for:

- Generated dataset exports.
- Retagged training outputs.
- Runtime SQLite files.
- Downloaded model artifacts.
- Large imagery/video caches.

Avoid committing large generated datasets unless the repo intentionally tracks a small seeded fixture pack.
