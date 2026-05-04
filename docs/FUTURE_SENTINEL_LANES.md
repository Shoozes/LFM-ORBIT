# Future Sentinel Lanes

Updated **May 4, 2026**.

These are post-handoff implementation notes. They are not current runtime capabilities.

The current showcase remains DPhi SimSat-first. Sentinel Hub is optional local support for replay refreshes, close-look story plates, and dataset development. Any future direct Sentinel lane must stay unavailable-safe, rate-aware, and candidate-only until source evidence plus operator review supports stronger claims.

## Shared Rules

- Keep navigation and scanning separate. Resolve and confirm a location or bbox first; propose the specialist scan second.
- Do not route specialist lanes through the current land/vegetation scorer unless a deliberate multi-lane scorer abstraction exists.
- Use Sentinel Hub Catalog or Statistical API as a cheap prefilter before Process API chip downloads when possible.
- Reject no-data, cloud, shadow, snow/ice, invalid pixels, and obvious land/water mask mismatches before scoring.
- Keep fallback/model-unavailable output explicit. A prefilter-only result is review evidence, not proof.
- Do not add proposal kinds to the Ground Agent whitelist until backend scan paths, API response shapes, UI handling, and tests exist.

## Marine Debris Candidate Lane

Current boundary:

- The active `plastic` target pack supports coastal debris, slick, and floating-material review language only.
- Great Pacific Garbage Patch prompts resolve to a cautious North Pacific review context with explicit no-overclaim guidance.
- There is no live `marine_debris` scanner, Process API chip fetcher, segmentation model wrapper, or `start_marine_debris_scan` action.

Use these labels:

- probable floating marine debris candidate
- floating-material candidate
- slick or foam candidate
- requires operator/source review

Do not use these labels from optical imagery alone:

- confirmed plastic
- confirmed garbage
- illegal dumping
- visible garbage-patch mass
- continuous open-ocean garbage growth

Recommended Sentinel-2 L2A inputs:

```text
B01, B02, B03, B04, B05, B06, B07, B08, B8A, B09, B11, B12, SCL, dataMask
```

Core features:

- water or water-adjacent mask with SCL and NDWI
- Floating Debris Index style NIR anomaly against red-edge/SWIR baseline
- NDVI separation for vegetation-like floating material
- cloud/shadow/no-data rejection
- optional local segmentation only when model artifacts are installed

Future module shape:

```text
source/backend/core/sentinel_process_client.py
source/backend/core/marine_debris_provider.py
source/backend/core/marine_debris_scoring.py
source/backend/core/marine_debris_model.py
source/backend/core/evalscripts/marine_debris_lite.js
```

Draft proposal kind: `start_marine_debris_scan`.

## Harmful Algal Bloom Candidate Lane

Current boundary:

- Ground Agent can classify algal-bloom prompts, resolve Lake Okeechobee, apply the `algae_bloom` target pack, and launch a confirmable custom mission.
- Sentinel Hub evalscript draft: `source/backend/core/evalscripts/algae_bloom_s2_l2a.js`.
- There is no live Process/Statistical API algal-bloom scorer.

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

Recommended Sentinel-2 L2A inputs:

```text
B02, B03, B04, B05, B07, B08, B8A, B11, B12, SCL, dataMask
```

Core features:

- NDCI: `(B05 - B04) / (B05 + B04)`
- FAI-style red/red-edge/NIR surface signal
- NDWI and MNDWI water masks
- turbidity proxy
- SCL/dataMask cloud, shadow, snow/ice, and invalid-pixel rejection

Future module shape:

```text
source/backend/core/algae_bloom_provider.py
source/backend/core/algae_bloom_scoring.py
source/backend/core/algae_bloom_monitoring.py
source/backend/core/evalscripts/algae_bloom_s2_l2a.js
```

First demo target: Lake Okeechobee, because it has public satellite context and official NOAA/FDEP follow-up paths.

## Promotion Checklist

- Add provider tests for missing credentials, invalid bbox, cloud-only scenes, and empty Process API responses.
- Add feature tests for each index/mask on synthetic chips.
- Add scoring tests for prefilter-only, model-unavailable, model-positive, and all-invalid cases.
- Add API tests for two-step location confirmation and no direct scan launch from navigation.
- Add frontend tests for proposal copy, candidate layers, warnings, and proof JSON.
- Add docs tests that reject confirmed-garbage, confirmed-plastic, confirmed-toxicity, and confirmed-species wording.

## References

- [Sentinel-2 L2A data collection](https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l2a/)
- [Sentinel Hub Process API](https://docs.sentinel-hub.com/api/latest/api/process/)
- [Sentinel Hub Statistical API](https://docs.sentinel-hub.com/api/latest/api/statistical/)
- [Sentinel Hub Evalscript V3](https://docs.sentinel-hub.com/api/latest/evalscript/v3/)
- [NASA Earth Observatory: Algae Bloom in Lake Okeechobee](https://earthobservatory.nasa.gov/images/151581/algae-bloom-in-lake-okeechobee)
- [NOAA NCCOS Lake Okeechobee cyanobacteria satellite product](https://coastalscience.noaa.gov/science-areas/habs/hab-monitoring-system/cyanobacteria-algal-bloom-satellite-lake-okeechobee-fl/)
