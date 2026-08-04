# Dataset Cycle Tutorial

This is the optional data loop for LFM Orbit: package replayable training data, retag it with Qwen, and publish a viewer-safe Hugging Face dataset. It supports real-data development, while the default satellite-data API family remains SimSat/Mapbox through DPhi Space SimSat.

## Story

One cycle creates evidence like an operator would:

1. Pick an interesting mission area.
2. Optionally fetch cloud-gated Sentinel-2 frames for cached replay fixtures.
3. Save the replay as a cached real API WebM plus metadata.
4. Export Orbit records into a local dataset pack.
5. Preserve `visual_model_review` when the optional image-conditioned retained-frame review path is present.
6. Retag deduplicated images and temporal sequences with `qwen3.6:27b`.
7. Upload the retagged configs to Hugging Face.
8. Verify the Hub loads each split.

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

## Optional Sentinel Development Cycle

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
  --monitor-reports-dir ..\..\runtime-data\monitor-reports `
  --offline-context-thumbnails

uv run --no-sync python scripts\retag_training_assets.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export `
  --provider ollama `
  --model qwen3.6:27b `
  --reuse-existing-dir ..\..\runtime-data\modeling\orbit-export\retagged_training `
  --reuse-existing-only `
  --timeout 180
```

Use `--reuse-existing-only` for normal upload refreshes: existing Qwen/Ollama tags are preserved by hash, while new hashes get deterministic heuristic labels instead of blocking on local model latency. Remove that flag and set positive `--max-provider-assets` / `--max-provider-sequences` only when intentionally running a fresh visual-model retag pass.

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
| Exported Orbit samples | `200` |
| Cached API observation rows | `0` |
| Replay-cache rows | `11` |
| Visual story frame rows | `0` |
| Monitor-report rows | `0` |
| Mission metadata rows | `185` |
| Records with timelapse references | `26` |
| Deduplicated training assets | `179` |
| Temporal sequences | `26` |
| External image calls | `0` |
| External sequence calls | `0` |
| Reused existing image tags | `179` |
| Reused existing sequence tags | `26` |
| Skipped assets | `0` |
| Tagger failures | `0` |
| Orphan or missing uploaded image files | `0` |

The sample count is a current runtime-cycle export, not a claim of total possible mission history. The durable replay cache is joined with cached API observations, visual story frames, persisted monitor reports, and mission metadata so new CV/object evidence work can train without spending provider quota.

## Integrity Rules

- Clouds and no-data are quality gates before frames enter replay WebMs.
- A valid timelapse needs multiple contextual satellite slices.
- Static image recolors are invalid temporal evidence.
- New exports rasterize offline SVG placeholder chips to PNG before retagging.
- `--offline-context-thumbnails` keeps local refreshes from waiting on ESRI thumbnail requests, and generated sample folders are cleared before each export so loose scans do not see stale sample assets.
- Successful retained-frame visual reviews export as `orbit_visual_review_sft_v1` image/text rows; rows without visual review stay valid `orbit_temporal_sft_v1` evidence-packet rows.
- Monitor before/after frame references are exported only when their image files are resolvable, so retagging does not chase dead local paths.
- Unsupported non-raster assets should still be skipped rather than forced into vision tagging.
- Already-tagged image hashes are reused from the previous retag folder when `--reuse-existing-dir` is set.
- Extracted video frames are namespaced by video SHA-256 so different `timelapse.webm` files cannot overwrite each other.
- Future-risk manifests remain unverified until independent post-window evidence exists.

## Hugging Face

Dataset: [Shoozes/LFM-Orbit-SatData](https://huggingface.co/datasets/Shoozes/LFM-Orbit-SatData)

Current refresh:

- Data payload commit: `9ccff9ce7315e270ca1b280c82c39414ce591d01`
- Dataset Viewer verification commit: `2df07094f36037e71c7e14e28dfbd298343be359`
- Final card documentation commit: `550c98f7c9b84eefbe3c0c6eb77b33a70028402a`
- Remote config verification before the May 7 refresh: `default=179`, `temporal_sft=26`, `asset_metadata=179`, `retagged_assets=179`, `temporal_metadata=26`, `review_queue=179`, `mission_metadata=185`
- Current remote refresh: `default=265`, `temporal_sft=33`, `asset_metadata=265`, `retagged_assets=265`, `temporal_metadata=33`, `review_queue=265`, total rows `1126`; `mission_metadata=0` is omitted from the Hub card until non-empty so Dataset Viewer does not fail the empty split. Remote label check found `70` wildfire image rows and `11` wildfire temporal rows.

The Hub card keeps schemas separate:

| Config | File |
|---|---|
| `default` | `training_assets.jsonl` |
| `temporal_sft` | `training_temporal_sequences.jsonl` |
| `asset_metadata` | `metadata.jsonl` |
| `retagged_assets` | `retagged_assets.jsonl` |
| `temporal_metadata` | `temporal_sequences.jsonl` |
| `review_queue` | `review_queue.jsonl` |
| `mission_metadata` | `mission_metadata.jsonl` |

## Refresh Cadence

- Use a dated local refresh label such as `orbit-satdata-YYYY-MM-DD`.
- Reuse existing image hashes and upload only changed configs/assets unless a schema changes.
- Keep metadata-only missions in `mission_metadata`; do not force invalid WebMs into image configs.
- For training-data refreshes, exclude local mission archives with `--no-missions --no-archived-missions` unless the explicit goal is intent/tool tuning. Otherwise repeated operator mission rows can crowd out seeded replay evidence under the export limit.
- Keep changing counts, tagger source, skipped assets, failures, and Hub commit hashes in the generated dataset manifests and release evidence; this tutorial owns the stable refresh workflow.
- Keep direct Sentinel/NASA/GEE refreshes optional. The default path remains SimSat/Mapbox through DPhi Space SimSat plus seeded replay data.
