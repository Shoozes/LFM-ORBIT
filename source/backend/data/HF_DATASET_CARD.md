---
pretty_name: LFM Orbit SatData
size_categories:
- 1K<n<10K
tags:
- satellite-imagery
- earth-observation
- sentinel-2
- lfm-orbit
- liquid-ai
- edge-ai
configs:
- config_name: default
  data_files:
  - split: train
    path: training_assets.jsonl
- config_name: temporal_sft
  data_files:
  - split: train
    path: training_temporal_sequences.jsonl
- config_name: asset_metadata
  data_files:
  - split: train
    path: metadata.jsonl
- config_name: retagged_assets
  data_files:
  - split: train
    path: retagged_assets.jsonl
- config_name: temporal_metadata
  data_files:
  - split: train
    path: temporal_sequences.jsonl
- config_name: review_queue
  data_files:
  - split: train
    path: review_queue.jsonl
---

# LFM Orbit SatData

Retagged Earth-observation training data produced by the LFM Orbit / GenUni edge-AI training pipeline.

The default viewer config is `training_assets.jsonl`, which contains single-image SFT rows with `image`, `messages`, and metadata. Temporal sequence rows live in the `temporal_sft` config so the Hugging Face Dataset Viewer does not try to cast sequence rows into the single-image schema.

## Configs

| Config | File | Purpose |
|---|---|---|
| `default` | `training_assets.jsonl` | Single-image SFT training rows |
| `temporal_sft` | `training_temporal_sequences.jsonl` | Ordered multi-frame SFT rows |
| `asset_metadata` | `metadata.jsonl` | Image asset metadata with labels, quality, confidence, and reason codes |
| `retagged_assets` | `retagged_assets.jsonl` | Full retag records and source references |
| `temporal_metadata` | `temporal_sequences.jsonl` | Full temporal-sequence provenance |
| `review_queue` | `review_queue.jsonl` | Human-review prompts and references |
| `mission_metadata` | `mission_metadata.jsonl` | Optional metadata-only scored mission rows. Omitted from current Hub configs when empty so Dataset Viewer does not fail split parsing. |

## Current Export

- Latest local refresh: `2026-05-07`
- Data payload commit: `9ccff9ce7315e270ca1b280c82c39414ce591d01`
- Dataset Viewer verification commit: `2df07094f36037e71c7e14e28dfbd298343be359`
- 46 exported Orbit samples in the current raw export cycle
- 0 cached API observation rows
- 33 replay-cache rows
- 7 visual object-evidence story frames
- 5 persisted monitor-report rows
- 0 metadata-only mission rows in the latest raw export
- 34 records with timelapse references
- 265 image-level SFT rows and 33 temporal-sequence SFT rows after retagging
- 145 image tags and 14 sequence tags were reused by SHA-256; new hashes used deterministic heuristic labels
- 0 skipped assets, 0 image tagger failures, and 0 sequence tagger failures
- Dataset Viewer verification: `1126` total rows, no pending configs, no failed configs
- Remote wildfire verification: `70` `asset_metadata` rows and `11` `temporal_metadata` rows tagged `wildfire`
- Wildfire rows include Florida SR-26/Balu Forest, Georgia Highway 82, Pineland Road, Spain Larouco, Lahaina, and related fireline/burn-scar review candidates tagged as `wildfire` / `fireline` where applicable.

The retagged SFT configs are the training-facing view. The raw export is kept locally for audit and regeneration.

Latest replay-cache additions:

- Mauna Loa lava-flow surface-change review, `volcanic_surface_change`, Sentinel-2 L2A SWIR/NIR/Red.
- Lake Urmia water persistence review, `flood_extent`, Sentinel-2 L2A true color.
- Black Rock City recurring temporary-settlement review, `urban_expansion`, Sentinel-2 L2A true color.
- Lahaina wildfire burn-scar recovery review, `wildfire`, Sentinel-2 L2A SWIR/NIR/Red.
- Kakhovka reservoir drawdown review, `flood_extent`, Sentinel-2 L2A true color.
- Kilauea summit eruption review, `volcanic_surface_change`, Sentinel-2 L2A SWIR/NIR/Red.
- Lake Mead shoreline recovery review, `flood_extent`, Sentinel-2 L2A true color.
- Greenland ice/snow extent review, `ice_snow_extent`, Sentinel-2 L2A NDSI/SCL metadata-only replay. The legacy static Greenland WebM is intentionally not used as timelapse proof.

Frame extraction now namespaces sampled frames by video SHA-256 so different `timelapse.webm` files cannot overwrite each other in the generated training folder.

Exported `samples/` are cleared before each export. Generated `images/` and `frames/` outputs are cleared before each retag run after reusable prior tags are loaded, so removed source assets cannot leave stale files in the upload folder. This refresh used offline context thumbnails so large local packaging runs do not wait on ESRI thumbnail requests.

Images are stored under `images/`. Sampled frame artifacts are stored under `frames/`. Empty failure logs remain downloadable for audit but are not part of the Dataset Viewer configs. Export references use repo/export-relative paths, not local workstation paths.

## Loading

```python
from datasets import load_dataset

assets = load_dataset("Shoozes/LFM-Orbit-SatData", "default", split="train")
temporal = load_dataset("Shoozes/LFM-Orbit-SatData", "temporal_sft", split="train")
metadata = load_dataset("Shoozes/LFM-Orbit-SatData", "asset_metadata", split="train")
```

For streaming:

```python
stream = load_dataset("Shoozes/LFM-Orbit-SatData", split="train", streaming=True)
first_rows = list(stream.take(3))
```
