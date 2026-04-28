# Dataset Cycle Tutorial

This is the show-ready data loop for LFM Orbit: seed real satellite evidence, package it as replayable training data, retag it with Qwen, and publish a viewer-safe Hugging Face dataset.

## Story

One cycle creates evidence like an operator would:

1. Pick an interesting mission area.
2. Fetch cloud-gated Sentinel-2 frames.
3. Save the replay as seeded WebM plus metadata.
4. Export Orbit records into a local dataset pack.
5. Retag deduplicated images and temporal sequences with `qwen3.6:27b`.
6. Upload the retagged configs to Hugging Face.
7. Verify the Hub loads each split.

## Current Cycle

| Mission | Evidence | Seed |
|---|---|---|
| Mauna Loa lava-flow review | Sentinel-2 L2A SWIR/NIR/Red sequence, 4 accepted frames, 0 cloud pixels in accepted windows | `source/backend/assets/seeded_data/sh_53c969f1.webm` |
| Lake Urmia water persistence review | Sentinel-2 L2A true-color sequence, 4 accepted frames, max cloud ratio `0.0018` | `source/backend/assets/seeded_data/sh_3ceea0a9.webm` |
| Black Rock City recurring settlement review | Sentinel-2 L2A true-color sequence, 5 accepted frames across empty/event seasons, max cloud ratio `0.1164` | `source/backend/assets/seeded_data/sh_73634fe8.webm` |
| Lahaina wildfire burn-scar recovery review | Sentinel-2 L2A SWIR/NIR/Red sequence, 4 accepted frames, near-zero cloud in accepted windows | `source/backend/assets/seeded_data/sh_a7815591.webm` |
| Kakhovka reservoir drawdown review | Sentinel-2 L2A true-color sequence, 4 accepted frames, max cloud ratio `0.0771` | `source/backend/assets/seeded_data/sh_b9993f84.webm` |
| Kilauea summit eruption review | Sentinel-2 L2A SWIR/NIR/Red sequence, 4 accepted frames, cloudy narrow windows widened until enough valid imagery existed | `source/backend/assets/seeded_data/sh_07ea2b1b.webm` |
| Lake Mead shoreline recovery review | Sentinel-2 L2A true-color sequence, 4 accepted frames | `source/backend/assets/seeded_data/sh_c8ec6b43.webm` |

The Mauna Loa and Kilauea runs are classified as `volcanic_surface_change`, not wildfire. Lake Urmia, Kakhovka, and Lake Mead stay in water/flood extent style temporal review lanes. The Mayon candidate was rejected for this cycle because the available windows were too cloudy to produce a valid timelapse.

## Run The Cycle

From `source/backend`:

```powershell
uv run --no-sync python scripts\seed_sentinel_cache.py `
  --lat 19.50 --lon -155.60 --grid 1 --cell-dim 0.035 `
  --location-name "Mauna Loa lava flow review" `
  --region-note "Volcanic lava-flow surface-change mission using SWIR/NIR/Red composites for visually distinct dataset evidence" `
  --use-case-id volcanic_surface_change `
  --target-category volcanic_surface_change `
  --target-task volcanic_lava_flow_temporal_review `
  --visual-mode burn_scar `
  --skip-vlm-metadata `
  --date-window pre_eruption=2022-08-01:2022-09-15 `
  --date-window active_eruption=2022-11-28:2022-12-15 `
  --date-window post_eruption=2023-01-01:2023-02-15 `
  --date-window recovery_2025=2025-01-01:2025-02-15
```

```powershell
uv run --no-sync python scripts\seed_sentinel_cache.py `
  --lat 37.65 --lon 45.35 --grid 1 --cell-dim 0.05 `
  --location-name "Lake Urmia water persistence review" `
  --region-note "Closed-basin lake extent and shoreline persistence mission for water-change dataset evidence" `
  --use-case-id flood_extent `
  --target-category water_extent `
  --target-task lake_extent_temporal_monitoring `
  --visual-mode true_color `
  --skip-vlm-metadata `
  --date-window low_water_2021=2021-08-01:2021-09-15 `
  --date-window rebound_2023=2023-04-01:2023-05-15 `
  --date-window summer_2024=2024-08-01:2024-09-15 `
  --date-window spring_2026=2026-03-01:2026-04-15
```

Then export and retag:

```powershell
uv run --no-sync python scripts\export_orbit_dataset.py `
  --output-dir ..\..\runtime-data\modeling\orbit-export `
  --include-seeded-cache `
  --monitor-reports-dir ..\..\runtime-data\monitor-reports

uv run --no-sync python scripts\retag_training_assets.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export `
  --provider ollama `
  --model qwen3.6:27b `
  --max-provider-assets 40 `
  --max-provider-sequences 6 `
  --reuse-existing-dir ..\..\runtime-data\modeling\orbit-export\retagged_training_reuse_prev `
  --no-reuse-existing-sequences `
  --timeout 180
```

Upload:

```powershell
uv run --no-sync python scripts\upload_orbit_dataset_hf.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export\retagged_training `
  --repo-id Shoozes/LFM-Orbit-SatData `
  --commit-message "Refresh LFM Orbit temporal replay dataset with frame-safe retagging"
```

## Proof From This Cycle

| Output | Value |
|---|---|
| Exported Orbit samples | `56` |
| Seeded-cache rows | `24` |
| Records with timelapse references | `25` |
| Deduplicated training assets | `179` |
| Temporal sequences | `26` |
| Qwen image calls | `40` |
| Qwen sequence calls | `6` |
| Reused existing image tags | `74` |
| Deterministic image fallbacks | `65` |
| Deterministic sequence fallbacks | `20` |
| Skipped assets | `9` SVG placeholders |
| Tagger failures | `0` |

The sample count is a current runtime-cycle export, not a claim of total possible mission history. The durable seeded cache increased and now includes seven newer temporal missions.

## Integrity Rules

- Clouds and no-data are quality gates before frames enter seeded WebMs.
- A valid timelapse needs multiple contextual satellite slices.
- Static image recolors are invalid temporal evidence.
- Unsupported SVG placeholders are skipped, not forced into vision tagging.
- Already-tagged image hashes are reused from the previous retag folder when `--reuse-existing-dir` is set.
- Extracted video frames are namespaced by video SHA-256 so different `timelapse.webm` files cannot overwrite each other.
- Future-risk manifests remain unverified until independent post-window evidence exists.

## Hugging Face

Dataset: [Shoozes/LFM-Orbit-SatData](https://huggingface.co/datasets/Shoozes/LFM-Orbit-SatData)

Current refresh:

- Data commit: `5a2798e7d16cd76df08eff3725dcf3ade9340b58`
- Card commit: `60e8ae913f61315740a640c532eb1aa9ae7cfe75`
- Remote config verification: `default=179`, `temporal_sft=26`, `asset_metadata=179`, `retagged_assets=179`, `temporal_metadata=26`, `review_queue=179`

The Hub card keeps schemas separate:

| Config | File |
|---|---|
| `default` | `training_assets.jsonl` |
| `temporal_sft` | `training_temporal_sequences.jsonl` |
| `asset_metadata` | `metadata.jsonl` |
| `retagged_assets` | `retagged_assets.jsonl` |
| `temporal_metadata` | `temporal_sequences.jsonl` |
| `review_queue` | `review_queue.jsonl` |
