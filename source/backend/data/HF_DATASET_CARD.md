---
license: mit
pretty_name: LFM Orbit SatData
size_categories:
- n<1K
tags:
- satellite-imagery
- earth-observation
- sentinel-2
- lfm-orbit
- liquid-ai
- dphi-space-hackathon
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
- config_name: mission_metadata
  data_files:
  - split: train
    path: mission_metadata.jsonl
---

# LFM Orbit SatData

Retagged Earth-observation training data produced by LFM Orbit for the Liquid AI x DPhi Space Hackathon.

The default viewer config is `training_assets.jsonl`, which contains single-image SFT rows with `image`, `messages`, and metadata. Temporal sequence rows live in the `temporal_sft` config so the Hugging Face Dataset Viewer does not try to cast sequence rows into the single-image schema.

## Configs

| Config | File | Purpose |
|---|---|---|
| `default` | `training_assets.jsonl` | Single-image SFT training rows |
| `temporal_sft` | `training_temporal_sequences.jsonl` | Ordered multi-frame SFT rows |
| `asset_metadata` | `metadata.jsonl` | ImageFolder-compatible asset metadata |
| `retagged_assets` | `retagged_assets.jsonl` | Full retag records and source references |
| `temporal_metadata` | `temporal_sequences.jsonl` | Full temporal-sequence provenance |
| `review_queue` | `review_queue.jsonl` | Human-review prompts and references |
| `mission_metadata` | `mission_metadata.jsonl` | Metadata-only scored mission rows, including missions without valid video proof |

## Current Export

- 56 exported Orbit samples in the current runtime cycle
- 24 replay-cache rows
- 25 records with timelapse references
- 179 deduplicated image/frame assets
- 26 temporal sequences
- 1 metadata-only scored mission row for Greenland ice/snow extent
- 40 bounded Qwen/Ollama image calls
- 6 bounded Qwen/Ollama temporal-sequence calls
- 74 reused existing image tags
- 65 deterministic image fallbacks
- 20 deterministic sequence fallbacks
- 9 skipped SVG placeholder assets
- 0 tagger failures

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

Images are stored under `images/`. Sampled frame artifacts are stored under `frames/`. Empty failure logs remain downloadable for audit but are not part of the Dataset Viewer configs.

## Loading

```python
from datasets import load_dataset

assets = load_dataset("Shoozes/LFM-Orbit-SatData", split="train")
temporal = load_dataset("Shoozes/LFM-Orbit-SatData", "temporal_sft", split="train")
metadata = load_dataset("Shoozes/LFM-Orbit-SatData", "asset_metadata", split="train")
missions = load_dataset("Shoozes/LFM-Orbit-SatData", "mission_metadata", split="train")
```

For streaming:

```python
stream = load_dataset("Shoozes/LFM-Orbit-SatData", split="train", streaming=True)
first_rows = list(stream.take(3))
```
