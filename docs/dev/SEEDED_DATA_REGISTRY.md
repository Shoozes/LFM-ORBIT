# Seeded Data Registry

Current as of **May 7, 2026**.

This registry tracks promoted real provider cache assets that should be reused during testing, training, replay polishing, and demo QA. Check this file and the matching `_meta.json` before calling Sentinel Hub again. Do not re-download the same bbox/date windows unless the bbox, frame windows, visual mode, band contract, or cloud/smoke policy intentionally changes.

Sentinel Hub is a development/cache-seeding source for these real-data fixtures. The hackathon default runtime remains SimSat/Mapbox, with these files used as bundled cached replay proof so reviewers can reproduce the same result without Sentinel Hub credentials or quota.

## Cache-First Rules

- Promoted Sentinel Hub cache assets live under `source/backend/assets/seeded_data/` and are deterministic replay inputs, not throwaway runtime output.
- A replay that references a `seeded_video` must commit the matching `.webm`, `_meta.json`, and any `frame_images` listed in metadata.
- Reuse existing cache keys for tests and training exports. Use `--force` only when refreshing the exact asset is the intended task, then rerun timelapse integrity and replay tests.
- Keep active-fire/smoke wording candidate-only unless source-backed burn indices, hotspot context, or other fire-specific evidence supports escalation.
- Never treat a color-shifted still image as a timelapse. Promoted replay WebMs must contain at least three real frames and pass the edge-delta integrity guard.

## Promoted Wildfire Assets

| Cache key | Curated replay | Location | Bbox | Frame windows | Why reuse it |
| --- | --- | --- | --- | --- | --- |
| `sh_83e3aea2` | `florida_sr26_wildfire_replay` | SR-26/Balu Forest, Alachua County, Florida | `[-82.2012, 29.6116, -82.1312, 29.6816]` | `baseline_2026_04_01`, `prefire_2026_04_05`, `active_2026_04_16` | Real Sentinel-2 L2A burn-scar candidate; postfire window was rejected and preserved in metadata, so the replay stays candidate-only. |
| `sh_4015e8b8` | `georgia_wildfire_replay` | Highway 82, Brantley County, Georgia | `[-81.916, 31.143, -81.756, 31.303]` | `baseline_2026_03_15`, `ignition_2026_04_16`, `active_2026_04_20` | Real active-window smoke/cloud review case; SCL cloud support is preserved instead of being hidden. |
| `sh_af5954b2` | `pineland_road_wildfire_replay` | Pineland Road Fire, Clinch/Echols Counties, Georgia | `[-82.8880591941128, 30.6363947250726, -82.64805919411279, 30.8763947250726]` | `baseline_2026_03_15`, `ignition_2026_04_16`, `active_2026_04_20` | Wider crop fixed the failed two-frame/static-timelapse pitfall and preserves smoke/cloud ambiguity for Proof Mode. |
| `sh_09384ab0` | `spain_larouco_wildfire_replay` | Larouco/Seadur, Ourense, Galicia, Spain | `[-7.3027999999999995, 42.23681, -7.0228, 42.51681]` | `baseline_2025_07_20`, `active_2025_08_16`, `postfire_2025_09_05` | Real Spain burn-scar review case with low postfire cloud support and positive dNBR/NDMI/NDVI burn context. |

## Required Reuse Checks

Before adding or refreshing a promoted wildfire replay:

```powershell
cd source/backend
uv run --no-sync pytest tests/test_seeded_timelapse_integrity.py tests/test_replay.py tests/test_seed_sentinel_cache.py tests/test_wildfire_smoke.py -q
```

For full wildfire replay handoff:

```powershell
cd source/backend
uv run --no-sync pytest tests/test_wildfire_smoke.py tests/test_spectral_band_contract.py tests/test_seed_sentinel_cache.py tests/test_replay.py tests/test_api.py tests/test_seeded_timelapse_integrity.py tests/test_vlm.py -q

cd ../frontend
npm run lint
```

Expected result after adding the Spain Larouco replay: backend `159 passed` in the focused suite, frontend typecheck clean.
