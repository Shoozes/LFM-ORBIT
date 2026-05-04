# Sentinel Close Looks

Sentinel Hub is the optional close-look lane for LFM-ORBIT. It is useful when an operator wants a clearer cached replay around a selected bbox/date window after the SimSat-first product flow has identified a region worth inspecting.

## What It Can And Cannot Do

- Sentinel-2 L2A gives useful 10m-class context for water, ice/snow, burn-scar, vegetation, port, and infrastructure-scale monitoring.
- It is not sub-meter inspection. Do not use it to imply individual-person, vehicle-plate, or building-detail confirmation. For roof-scale visual proof plates, use separate context imagery and label that imagery origin explicitly.
- Fresh Sentinel Hub calls are optional development/replay support. The default showcase remains DPhi SimSat-first and credential-free.
- Seeded Sentinel Hub outputs must stay labeled as cached/replay evidence once stored under `source/backend/assets/seeded_data/`.
- Timelapse evidence must show multiple contextual satellite frames. A single still image with color shifts is invalid temporal proof.

## Close-Look Workflow

1. Pick a small bbox around the mission area.
2. Choose explicit date windows or a bounded month range.
3. Seed Sentinel-2 L2A frames through the existing cache seeder.
4. Let SCL quality gates reject cloudy/no-data frames.
5. Review the contact sheet or replay before using it in README/demo material.
6. Keep the replay metadata with `runtime_truth_mode=replay`, `imagery_origin=cached_api`, and the source label from the seed metadata.

Example Greenland ice/snow close look:

```powershell
cd source/backend
uv run --no-sync python scripts/seed_sentinel_cache.py `
  --lat 69.18 `
  --lon -51.05 `
  --grid 1 `
  --cell-dim 0.08 `
  --start 2024-01 `
  --end 2025-12 `
  --location-name "Greenland Ilulissat ice edge" `
  --region-note "Ice/water/coastline contextual change review" `
  --use-case-id ice_cap_growth `
  --target-category cryosphere `
  --target-task ice_edge_change_quality_gate `
  --skip-vlm-metadata
```

Decade-scale same-season Greenland close look:

```powershell
cd source/backend
uv run --no-sync python scripts/seed_sentinel_cache.py `
  --lat 69.18 `
  --lon -51.05 `
  --grid 1 `
  --cell-dim 0.08 `
  --location-name "Greenland Ilulissat ice edge decade review" `
  --region-note "Same-season May ice/snow extent context from Sentinel Hub" `
  --use-case-id ice_snow_extent `
  --target-category cryosphere `
  --target-task ice_snow_extent_decade_review `
  --date-window may_2016=2016-05-01:2016-06-15 `
  --date-window may_2017=2017-05-01:2017-06-15 `
  --date-window may_2018=2018-05-01:2018-06-15 `
  --date-window may_2019=2019-05-01:2019-06-15 `
  --date-window may_2020=2020-05-01:2020-06-15 `
  --date-window may_2021=2021-05-01:2021-06-15 `
  --date-window may_2022=2022-05-01:2022-06-15 `
  --date-window may_2023=2023-05-01:2023-06-15 `
  --date-window may_2024=2024-05-01:2024-06-15 `
  --date-window may_2025=2025-05-01:2025-06-15 `
  --date-window may_2026=2026-05-01:2026-05-02 `
  --skip-vlm-metadata
```

This is possible as a development cache seed, but it should remain a same-season extent review, not an ice-volume claim. Early/global availability can vary by collection and geography; if a 2016 or current-year window is unavailable or clouded, the seeder records the rejected window instead of fabricating a frame.

For event-specific proof, prefer explicit windows:

```powershell
uv run --no-sync python scripts/seed_sentinel_cache.py `
  --lat 36.13 `
  --lon -114.40 `
  --grid 1 `
  --cell-dim 0.08 `
  --location-name "Lake Mead shoreline recovery review" `
  --region-note "Reservoir shoreline and water-persistence temporal review" `
  --use-case-id flood_extent `
  --target-category water_extent `
  --target-task reservoir_extent_temporal_monitoring `
  --date-window drought_low_2022=2022-07-01:2022-08-15 `
  --date-window monsoon_rebound_2023=2023-07-01:2023-08-15 `
  --date-window summer_2025=2025-07-01:2025-08-15 `
  --date-window spring_2026=2026-03-15:2026-04-25 `
  --skip-vlm-metadata
```

## README Highlight

The README uses an animated GIF because it renders through standard Markdown image syntax:

```markdown
![Greenland ice/snow Sentinel-2 timelapse](media/timelapse/highlight-greenland-ice-timelapse.gif)
```

The current GIF is generated from:

```text
source/backend/assets/seeded_data/sh_cc0e95b7.webm
```

The tutorial proof may use the generated WebM as visual context while keeping the confidence score bound to replay metadata such as NDSI, SWIR/NIR, SCL quality, accepted-frame persistence, and rejected cloud windows.

Regenerate the README highlight:

```powershell
cd source/backend
uv run --no-sync python scripts/build_docs_timelapse_highlight.py
```

Outputs:

```text
docs/media/timelapse/highlight-greenland-ice-timelapse.gif
docs/media/timelapse/highlight-greenland-ice-timelapse.webm
```

The docs artifact test enforces that the GIF exists and stays under 10 MB for GitHub inline use.

## Visual Story Plates

The README use-case grid is generated by:

```powershell
cd source/backend
python scripts/build_visual_story_proofs.py --force-fetch
```

This reads Sentinel Hub OAuth credentials from environment variables, `.tools/.secrets/sentinel.txt`, or `.tools/.secrets/sh.txt`. Sentinel Hub frames are cached under:

```text
source/backend/assets/seeded_data/visual_story_frames/
```

The same folder also stores a manifest for replay, audit, and future training-data recycling. `export_orbit_dataset.py --include-seeded-cache` can turn those manifest rows into `visual_story_frame` training/review samples with local PNG assets. Story plates that need object-scale roofs or shelter rows use Esri World Imagery context instead of pretending Sentinel-2 can resolve those details. Every generated plate visibly labels `box_source=visual_story_fixture`; replace that label only when the boxes come from an actual model-backed detection path.
