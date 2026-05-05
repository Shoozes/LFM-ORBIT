# LFM-ORBIT Object Evidence Mode

Current as of **May 2, 2026**.

LFM-ORBIT Object Evidence Mode turns satellite imagery into compact object evidence onboard. Operators describe a mission, choose the objects or signals that matter, and the system keeps raw imagery local while compact proof JSON carries the reason a frame matters.

Built in the Liquid AI x DPhi Space AI in Space context, this mode is product framing for the repo's existing strengths: onboard triage, DPhi SimSat-first runtime, replay-safe evidence, Liquid evidence-packet reasoning, payload accounting, provenance, link-outage queueing, and operator workflows.

## What Is Wired Now

- Object evidence contracts exist in `source/backend/core/contracts.py`: `ObjectTarget`, `TargetPack`, `DetectionBox`, `DetectionSummary`, `ObjectDelta`, and `ObjectEvidencePayload`.
- Versioned default target packs live in `source/backend/assets/object_targets/default_target_packs.json`.
- Runtime custom packs are stored separately under `runtime-data/object-targets/custom_target_packs.json`.
- The target-pack registry in `source/backend/core/object_targets.py` normalizes labels, merges duplicate object targets, rejects unsafe target labels, and saves/deletes custom packs without modifying defaults.
- Missions now carry `target_pack_id` and normalized `object_targets` in `source/backend/core/mission.py`, with migration-safe columns for old local databases.
- The API exposes the registry through:
  - `GET /api/object-targets/packs`
  - `GET /api/object-targets/packs/{pack_id}`
  - `POST /api/object-targets/packs`
  - `DELETE /api/object-targets/packs/{pack_id}`
- The API exposes mission target editing through:
  - `GET /api/mission/targets`
  - `POST /api/mission/targets/add`
  - `POST /api/mission/targets/remove`
  - `POST /api/mission/targets/set-pack`
  - `POST /api/mission/targets/clear`
- `POST /api/vlm/grounding/batch` runs all enabled mission targets through the visual grounding path and returns normalized boxes plus a detection summary.
- Mission Control shows a target-pack selector, object chips, add/remove controls, enable/disable toggles, reset-to-pack, save-custom-pack, and clear actions backed by the mission target API.
- Ground Agent keeps mission evidence tied to confirmed mission actions. Target-pack editing APIs remain available for development, but the submission UI runs preset mission targets instead of exposing tuning controls.
- VLM tools can run all enabled mission targets for the active bbox, then push normalized boxes to the glowing map overlay.
- Batch grounding skips disabled targets, normalizes all returned boxes to `unit_xyxy`, and drops degenerate zero-area boxes before detection counts are computed.
- Visual evidence boxes now render with glowing semantic outlines, object labels, a map legend, and hover details for label, confidence, bbox, prompt, source model, runtime truth mode, imagery origin, and scoring basis.
- Replay snapshot import/export preserves mission target packs and object targets, so portable runtime snapshots keep the operator's object-evidence intent.
- Runtime reset archives mission metadata under `runtime-data/mission-archive/mission_history.jsonl` by default, and dataset export can emit current or archived mission metadata rows without making new satellite API calls.
- Alert persistence now stores compact `detection_summary` and `object_deltas` JSON so object evidence can survive reloads, replay loads, Logs, Inspect, and Proof Mode.
- Inspect and Proof Mode now surface searched targets, found counts, top boxes, compact proof JSON fields, and object count deltas when alerts carry object evidence.
- Deterministic object-box replays exist for Critical Minerals Expansion Watch, Southeast Fireline Watch, humanitarian shelter count, port supply-chain activity, and coastal debris/slick candidate watch.
- Object count deltas are available through `core/object_tracking.py`, and `scripts/evaluate_object_evidence.py` runs a frozen JSONL eval with schema, bbox, label-recall, IoU@0.5 grounding, action, fallback, and payload-reduction metrics.
- JSON-backed operational watchlists can start missions from named assets through `/api/watchlists/*`; the Southeast Fireline Watch seed carries Georgia/Florida bbox assets and target packs without requiring external credentials, and list responses expose repo-relative paths instead of local machine paths.
- Focused backend and Playwright tests cover default/custom target packs, unsafe target rejection, custom-pack delete, mission target mutation, Ground Agent proposals, batch grounding, visual box glow, object legend, and object tooltip behavior.

## Current Target Packs

| Pack | Purpose |
|---|---|
| `critical_minerals` | Evaporation pond regions, tailings regions, open-pit expansion, industrial roads, facility clusters, exposed soil, and surface color change |
| `fireline` | Smoke, burn-scar, road obstruction, buildings, and vehicle queue evidence |
| `camp` | Shelter and aid-infrastructure counting without person-level claims |
| `port` | Ships, containers, cranes, trucks, and vessel queues |
| `plastic` | Coastal debris candidates, slick candidate areas, foam-line regions, and storm-debris zones without garbage-patch mass claims |
| `waterline` | Water extent, shoreline retreat, exposed lakebed, dry basin, and water color boundary evidence |
| `glacier` | Ice terminus, open water expansion, exposed bedrock, retreat boundary, and moraine/debris-region evidence |
| `lifeline` | Civilian mobility, water-service, aid, logistics, and infrastructure continuity |

## Safety Scope

Object targets stay inside civilian evidence mode. Denied labels such as `person`, `people`, `individual`, `soldier`, `weapon`, `target`, and `strike`, including common plurals, are rejected by the registry. Humanitarian shelter counting estimates shelters and aid infrastructure, not individual people or identities.

Fallback detections remain candidate evidence. A fallback box is not a confirmed object detection unless replay context, model-backed provenance, or operator review supports escalation.

Critical-minerals targets are region-level review evidence. They can support "expansion of industrial extraction features" wording, but they must not claim illegal mining, confirmed pollution, exact production, or resource output without external validation.

Coastal debris/slick targets are experimental candidate evidence. They should stay near visible coastal, river-mouth, port, or storm-aftermath context and must not be described as Great Pacific Garbage Patch mass monitoring from optical imagery.

Story plates are visual fixtures over cached context imagery unless their provenance says otherwise. Promoted public plates live under `docs/media/story-plates/`; non-promoted plates stay under `source/backend/assets/seeded_data/visual_story_frames/story_plates/` for training/export review. They are useful for showing product behavior, dataset rows, and box geometry, but they must keep `box_source=visual_story_fixture` visible and must not be described as live model detections. Object-scale plates should use tight boxes over visible subjects; signal-oriented plates should be described as candidate evidence regions rather than object counts.

The frozen eval now follows the satellite-VLM grounding discipline used in external references: normalized `unit_xyxy` boxes are schema-checked, then matched against expected boxes with IoU@0.5 before the payload-reduction story is counted as valid.

## Data Flow

```text
default_target_packs.json
        +
runtime custom packs
        +
operator / Ground Agent edits
        =
mission.object_targets
        =
retained-cell object evidence
        =
detection boxes + compact proof JSON
        +
reset-safe mission archive / training metadata rows
```

The flow is wired through mission state, Mission Control, Ground Agent proposals, VLM batch grounding, replay snapshots, alert persistence, reset-safe mission archive, and dataset export.

## Product-Safe Examples

```text
Run Critical Minerals Expansion Watch. Look for evaporation pond regions, tailings regions, open-pit expansion, industrial roads, facility clusters, exposed soil, and surface color change.
```

```text
Run Southeast Fireline Watch. Look for dark smoke, burn scar, road obstruction, buildings, and vehicle queues.
```

```text
Run a port activity scan. Look for shipping container clusters, container yard clusters, docked-vessel groups, and berth basin context.
```

```text
Run a humanitarian shelter count. Look for shelters, tents, vehicles, water tanks, and clinic roofs.
```

## Remaining Integration Work

1. Expand frozen eval fixtures beyond the first two replay-safe cases.
2. Add regression thresholds to CI once the object-evidence fixture set stabilizes.
3. Continue responsive/mobile coverage for fixed operator rails and Proof Mode.

Those items are tracked in `docs/TODO.md`; this document describes the current product mode and its contracts.
