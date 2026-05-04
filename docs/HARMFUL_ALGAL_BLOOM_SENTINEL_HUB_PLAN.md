# Harmful Algal Bloom Sentinel Hub Plan

Updated **May 3, 2026**.

This is the scoped plan for adding a Florida harmful algal bloom lane to LFM Orbit. The current implementation is a safe Ground Agent planning scaffold: it can classify algal-bloom prompts, resolve Lake Okeechobee as a vetted context target, apply an `algae_bloom` target pack, and launch a confirmable custom mission. It does not yet run a live Sentinel Hub Process/Statistical API scorer.

## Claim Boundary

Use these labels:

- probable surface algal bloom
- high chlorophyll signal
- cyanobacteria-like signal
- surface scum candidate
- possible red-tide or HAB signal
- requires NOAA, FDEP, or field confirmation

Do not use these labels from Sentinel-2 alone:

- confirmed toxic algae
- confirmed microcystin
- confirmed cyanobacteria species
- confirmed Karenia brevis
- confirmed red tide

NASA's Lake Okeechobee example shows large blue-green algae blooms can be visible from orbit, while noting that surface sampling is needed to confirm exact bloom composition. NOAA NCCOS also publishes a Lake Okeechobee cyanobacteria satellite product derived from Copernicus Sentinel-3 OLCI, with image quality varying due to clouds and satellite position. Sentinel-2 is useful for finer spatial review, and published work shows Sentinel-2A/B plus in-situ data can map smaller HAB features with NDCI at high spatial detail.

References:

- [NASA Earth Observatory: Algae Bloom in Lake Okeechobee](https://earthobservatory.nasa.gov/images/151581/algae-bloom-in-lake-okeechobee)
- [NOAA NCCOS: Lake Okeechobee Cyanobacteria Bloom from Satellite](https://coastalscience.noaa.gov/science-areas/habs/hab-monitoring-system/cyanobacteria-algal-bloom-satellite-lake-okeechobee-fl/)
- [Scientific Reports: Sentinel-2A/B for small harmful algal blooms](https://www.nature.com/articles/s41598-020-65600-1)
- [Sentinel Hub Evalscript documentation](https://docs.sentinel-hub.com/api/latest/evalscript/)
- [Sentinel Hub aquatic plants and algae custom script](https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/apa_script/)

## Current Repo Scaffold

Implemented now:

- `harmful_algal_bloom` temporal use case in `source/backend/core/temporal_use_cases.py`
- `algae_bloom` target pack in `source/backend/assets/object_targets/default_target_packs.json`
- `Lake Okeechobee, FL` vetted location target in `source/backend/core/ground_agent_knowledge.py`
- Ground Agent semantics fixture row in `source/backend/data/ground_agent_tool_semantics.example.jsonl`
- Sentinel Hub evalscript draft at `source/backend/core/evalscripts/algae_bloom_s2_l2a.js`
- Focused tests for classification, proposal routing, target-pack loading, and confirmation flow

Current operator flow:

```text
Operator:
  check Lake Okeechobee for algae blooms

Ground Agent:
  classify use_case_id = harmful_algal_bloom
  resolve region = Lake Okeechobee, FL
  set target_pack_id = algae_bloom
  propose start_custom_mission

Operator confirms:
  active mission bbox moves to Lake Okeechobee
  target pack includes bloom, chlorophyll, cyanobacteria-like, scum, turbidity, and cloud/glint controls
```

## Future Live Scoring Lane

Add a separate scorer rather than using the forest-change scorer. The forest lane is NDVI/NBR/NDMI/canopy-loss oriented and should not produce algal-bloom claims.

Recommended module shape:

```text
source/backend/core/algae_bloom_provider.py
source/backend/core/algae_bloom_scoring.py
source/backend/core/algae_bloom_monitoring.py
source/backend/core/evalscripts/algae_bloom_s2_l2a.js
```

Sentinel-2 L2A inputs:

```text
B02, B03, B04, B05, B07, B08, B8A, B11, B12, SCL, dataMask
```

Core features:

- NDCI = `(B05 - B04) / (B05 + B04)`
- FAI-style red/red-edge/NIR surface signal
- NDWI and MNDWI water masks
- turbidity proxy
- SCL/dataMask cloud, shadow, snow/ice, and invalid-pixel rejection

Candidate alert shape:

```json
{
  "use_case_id": "harmful_algal_bloom",
  "observation_source": "sentinelhub_direct_algae_bloom",
  "runtime_truth_mode": "realtime",
  "imagery_origin": "sentinelhub",
  "scoring_basis": "multispectral_bands",
  "change_score": 0.71,
  "confidence": 0.68,
  "reason_codes": [
    "water_mask_passed",
    "cloud_mask_passed",
    "high_ndci",
    "surface_bloom_fai_signal",
    "requires_field_confirmation"
  ],
  "algae_bloom": {
    "label": "probable_surface_algal_bloom",
    "candidate_pixel_count": 183,
    "mean_ndci": 0.34,
    "mean_fai": 0.024,
    "water_valid_fraction": 0.82,
    "note": "Probable bloom evidence only. Toxicity and species require NOAA/FDEP or field confirmation."
  }
}
```

## Demo Targets

- Lake Okeechobee
- St. Lucie Canal and Estuary
- Caloosahatchee River
- Indian River Lagoon
- Tampa Bay or Charlotte Harbor for cautious red-tide-adjacent context

Lake Okeechobee should be the first demo target because it has large visible bloom history, NOAA satellite products, and strong public context.
