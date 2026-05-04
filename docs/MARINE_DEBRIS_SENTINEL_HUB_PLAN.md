# Sentinel Hub Marine Debris Lane

Updated **May 3, 2026**.

This is a future implementation plan, not a current runtime capability. LFM Orbit can route garbage-patch-style prompts into cautious candidate review today, but it must not claim confirmed garbage, confirmed plastic, illegal dumping, or visible open-ocean garbage-patch mass from optical bands.

## Current Boundary

- The active hackathon runtime remains DPhi SimSat-first.
- Sentinel Hub is optional local support for replay refreshes, close-look story plates, and dataset development.
- The current `plastic` target pack supports candidate coastal debris, slicks, and floating-material review language only.
- Great Pacific Garbage Patch prompts currently resolve to a North Pacific debris-convergence review window with explicit no-overclaim guidance.
- There is no live `marine_debris` scanner, Sentinel Hub Process API chip fetcher, marine-debris model wrapper, or `start_marine_debris_scan` action yet.

## Why This Needs A Separate Lane

Marine debris is not a vegetation change problem. The existing Sentinel path and scorer are intentionally narrow:

- `source/backend/core/sentinel_provider.py` fetches a small WMS band set oriented around existing spectral-change scoring.
- `source/backend/core/scorer.py` is vegetation and land-surface-change specific, with NDVI/NBR/EVI2/NDMI and canopy/soil reasoning.
- `source/backend/core/scanner.py` currently routes normal scans through the existing cell-change scorer.

The future marine-debris lane should be a single-scene or multi-scene floating-material detector. It should use water, cloud, land-edge, FDI, NDWI, NDVI, and optional model probability evidence, then downlink compact candidate alerts.

## Proposed Operator Flow

```text
Operator:
  "Find garbage near Durban Harbor"

Ground Agent:
  resolve location -> confirm bbox -> propose marine-debris scan

Backend:
  Sentinel Hub Catalog or Statistical API prefilter
  Sentinel Hub Process API chip/index fetch
  FDI / NDWI / NDVI / SCL / dataMask screening
  optional local marine-debris segmentation model
  compact suspected-debris alert packets

Frontend:
  MapLibre candidate heatmap or polygons
  Inspect evidence: RGB chip, FDI heatmap, mask, reason codes
  Proof JSON with candidate-only wording
```

Navigation and scanning should stay separate. A prompt with a new place should first produce a `navigate_map_location` proposal. Only after the operator confirms the bbox should Ground Agent offer a second `start_marine_debris_scan` proposal.

## Sentinel Hub Inputs

Use Sentinel-2 L2A through Sentinel Hub. The full inference chip should include the 12 optical bands commonly used by marine-debris segmentation work:

```text
B01, B02, B03, B04, B05, B06, B07, B08, B8A, B09, B11, B12
```

Also request quality bands such as:

```text
SCL, CLD or CLP when useful, dataMask
```

Do not depend on B10 for L2A, and do not treat RGB-only tiles as enough for marine-debris scoring.

## Lightweight Prefilter

The first pass should be cheap and conservative:

- Reject clouds, cloud shadow, no-data, snow/ice, and obvious land edge artifacts.
- Keep water or water-adjacent pixels using SCL and NDWI.
- Compute Floating Debris Index style NIR anomaly against red-edge/SWIR baseline.
- Use NDVI to separate likely vegetation from non-vegetation floating material.
- Use the Statistical API when a whole cell can be summarized without downloading full chips.
- Only call the Process API for cells that pass the prefilter or are needed for review evidence.

This prefilter is not proof. It should produce "candidate floating material" only.

## Optional Local Model

An optional local model wrapper can run a 12-band marine-debris segmentation model when weights and dependencies are installed. It should be capability-gated:

```text
model_available=false
reason=model_unavailable_prefilter_only
```

The app must remain bootable without the model. If model inference is unavailable, the lane can still emit low-confidence prefilter evidence or abstain.

## Proposed Files

Future implementation should add files in this shape:

```text
source/backend/core/sentinel_process_client.py
source/backend/core/marine_debris_provider.py
source/backend/core/marine_debris_scoring.py
source/backend/core/marine_debris_model.py
source/backend/core/evalscripts/marine_debris_lite.js
source/backend/tests/test_marine_debris_scoring.py
source/backend/tests/test_sentinel_process_client.py
source/frontend/components/MarineDebrisLayer.tsx
source/frontend/components/MarineDebrisPanel.tsx
```

Keep `source/backend/core/scorer.py` focused on its current land/vegetation lanes unless there is a deliberate routing abstraction for multiple use cases.

## Proposal Contract

Draft action shape:

```json
{
  "kind": "start_marine_debris_scan",
  "title": "Scan for Marine Debris: Durban Harbor",
  "summary": "Use Sentinel-2 multispectral evidence to find probable floating debris candidates. This does not confirm material type.",
  "details": {
    "use_case_id": "marine_debris",
    "bbox": [30.86, -30.02, 31.12, -29.78],
    "start_date": "2026-04-01",
    "end_date": "2026-05-03",
    "provider": "sentinelhub_direct",
    "scoring_basis": "multispectral_bands_prefilter_optional_model",
    "state_impact": [
      "Search Sentinel-2 L2A scenes over the confirmed bbox",
      "Run conservative floating-debris prefilters",
      "Run a local segmentation model only if installed",
      "Show candidate evidence for operator review"
    ]
  },
  "confirm_label": "Start Debris Scan",
  "cancel_label": "Cancel",
  "risk_level": "medium"
}
```

Do not add this proposal kind to the active whitelist until the backend scan path, response shape, and UI handling exist.

## Alert Contract

Candidate alert packets should fit Orbit's existing compact proof story:

```json
{
  "cell_id": "8928308280fffff",
  "use_case_id": "marine_debris",
  "runtime_truth_mode": "realtime",
  "imagery_origin": "sentinelhub",
  "scoring_basis": "multispectral_bands_prefilter_optional_model",
  "change_score": 0.74,
  "confidence": 0.66,
  "reason_codes": [
    "marine_debris_lane",
    "water_mask_passed",
    "cloud_mask_passed",
    "high_fdi_response",
    "requires_review"
  ],
  "debris": {
    "candidate_pixel_count": 42,
    "candidate_area_m2": 16800,
    "model_available": false,
    "note": "Probable floating marine debris candidate, not confirmed plastic composition."
  }
}
```

## Semantics Fixture Rule

The local semantics fixture can document future phrasing only after the runtime action exists. Until then, keep experimental rows in ignored local files:

```text
source/backend/data/ground_agent_tool_semantics.local.jsonl
```

Expected future examples:

```jsonl
{"id":"marine_debris_001","utterance":"find garbage near Durban Harbor","intent":"start_marine_debris_scan","tool":"resolve_location_then_prepare_scan","arguments":{"query":"Durban Harbor","use_case_id":"marine_debris"},"expected_proposal":{"kind":"navigate_map_location","requires_confirmation":true},"notes":"Resolve location first. Do not claim confirmed plastic."}
{"id":"marine_debris_002","utterance":"scan this coast for floating trash","intent":"start_marine_debris_scan","tool":"prepare_bbox_scan","arguments":{"use_current_bbox":true,"use_case_id":"marine_debris"},"expected_proposal":{"kind":"start_marine_debris_scan","risk_level":"medium","requires_confirmation":true},"notes":"Use current bbox. Candidate evidence only."}
```

The JSONL file is guidance and regression coverage, not a gazetteer and not a public Hugging Face dataset.

## Tests Before Runtime Promotion

Add focused tests before turning this on:

- Provider tests for missing Sentinel credentials, invalid bbox, cloud-only scenes, and empty Process API responses.
- Evalscript or feature tests for FDI, NDWI, NDVI, SCL, and dataMask behavior on synthetic chips.
- Scoring tests for prefilter-only, model-unavailable, model-positive, and all-invalid cases.
- API tests for location-first proposal sequencing and no direct mission launch from map navigation.
- Frontend tests for confirmation, scan proposal copy, candidate heatmap rendering, and candidate-only warning text.
- Docs tests proving public wording does not claim confirmed garbage or plastic composition.

## Acceptance Criteria

- A user can ask for garbage, floating trash, plastic pollution, or marine debris near a location.
- Ground Agent resolves and confirms the location before scan setup.
- The scan uses `use_case_id=marine_debris`, not the vegetation scorer.
- Sentinel Hub calls are optional, rate-aware, and unavailable-safe.
- Output says "probable floating marine debris candidate" or similar cautious wording.
- The UI shows evidence layers and warnings without implying confirmation.
- Existing SimSat-first showcase, replay, object-evidence, and map-navigation flows still pass.

## References

- [Large-scale detection of marine debris in coastal areas with Sentinel-2](https://www.sciencedirect.com/science/article/pii/S2589004223024793)
- [Sentinel-2 L2A data collection](https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l2a/)
- [Sentinel Hub Process API](https://docs.sentinel-hub.com/api/latest/api/process/)
- [Sentinel Hub Statistical API](https://docs.sentinel-hub.com/api/latest/api/statistical/)
- [Sentinel Hub Evalscript V3](https://docs.sentinel-hub.com/api/latest/evalscript/v3/)
- [Finding Plastic Patches in Coastal Waters using Optical Satellite Data](https://www.nature.com/articles/s41598-020-62298-z)
- [marinedebrisdetector](https://github.com/marccoru/marinedebrisdetector)
