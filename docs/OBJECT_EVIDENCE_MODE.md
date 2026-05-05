# LFM-ORBIT Target-Pack Proof Contracts

Current as of **May 5, 2026**.

Target packs are the backend contract for what a mission should retain, not a separate operator workspace. The submission UI keeps the Mission tab focused on plan, replay, scan progress, and timelapse. Target-pack details remain attached to missions, alerts, replay snapshots, dataset exports, and Proof Mode so evidence can be audited without adding a second tuning panel.

## Wired Runtime

- `source/backend/core/contracts.py` defines `ObjectTarget`, `TargetPack`, `DetectionBox`, `DetectionSummary`, `ObjectDelta`, and `ObjectEvidencePayload`.
- Versioned default packs live in `source/backend/assets/object_targets/default_target_packs.json`.
- Runtime custom packs stay under `runtime-data/object-targets/custom_target_packs.json` and never mutate defaults.
- `source/backend/core/object_targets.py` normalizes labels, merges duplicates, rejects unsafe target labels, and saves/deletes custom packs.
- `source/backend/core/mission.py` stores `target_pack_id` and normalized `object_targets` with migration-safe columns for old local databases.
- `source/backend/core/object_evidence.py` skips disabled targets, clamps boxes to `unit_xyxy`, drops degenerate boxes, summarizes counts, and preserves provenance.
- Alerts persist compact `detection_summary` and `object_deltas` so evidence survives reloads, replay loads, Logs, Inspect, and Proof Mode.
- Replay snapshots preserve target packs and object targets for portable proof and dataset export.

## Current UI Boundary

- Normal Mission UI exposes mission text, bbox, date window, presets, replay loading, scan state, and timelapse.
- Target/monitor subtabs and the old visual-evidence tools panel are intentionally retired from the submission UI.
- Ground Agent can launch curated mission packs after operator confirmation; it does not expose target tuning controls.
- Proof Mode is explicit. It opens only when a mission or replay exists and stays scoped to that mission or replay.
- The legacy port audit video is retained as proof-history media, not as a current Mission-tab workflow.

## API Surface

Development and test APIs remain available:

```text
GET    /api/object-targets/packs
GET    /api/object-targets/packs/{pack_id}
POST   /api/object-targets/packs
DELETE /api/object-targets/packs/{pack_id}
GET    /api/mission/targets
POST   /api/mission/targets/add
POST   /api/mission/targets/remove
POST   /api/mission/targets/set-pack
POST   /api/mission/targets/clear
POST   /api/vlm/grounding/batch
```

These routes support backend contracts, fixtures, replay proof, and future model-training cycles. They should not reappear as normal first-run UI without a deliberate product review.

## Pack Scope

| Pack | Purpose |
|---|---|
| `critical_minerals` | Region-level extraction evidence: evaporation ponds, tailings, open-pit expansion, roads, facility clusters, exposed soil, and surface color change |
| `deforestation` | Clearing, canopy boundary, exposed soil, road/corridor, and land-use change candidates |
| `fireline` | Smoke, burn-scar, road obstruction, building-context, and vehicle-queue candidates |
| `camp` | Shelter and aid-infrastructure counting without person-level claims |
| `port` | Container clusters, docked-vessel groups, crane/yard context, and berth basin context |
| `plastic` | Coastal debris, slick, foam-line, or storm-debris candidates without garbage-patch mass claims |
| `waterline` | Water extent, shoreline retreat, exposed lakebed, dry basin, and water-color boundary evidence |
| `glacier` | Ice terminus, open water expansion, exposed bedrock, retreat boundary, and debris-region evidence |
| `lifeline` | Civilian mobility, water-service, aid, logistics, and infrastructure-continuity context |

## Safety Rules

- Denied labels such as people, individuals, weapons, military targeting, protected wildlife, and population targets are rejected before persistence.
- Broad or low-resolution boxes use group, area, region, zone, corridor, cluster, or candidate wording.
- Fixture boxes must disclose `box_source=visual_story_fixture` and must not be described as live model detections.
- Critical-minerals output stays region-level unless independently validated.
- Coastal debris/slick and HAB-style outputs stay candidate-only without external confirmation.
- Image-trained artifacts are not described as direct image-conditioned runtime inference unless `/api/analysis/status` reports `image_conditioned_runtime_enabled=true`.

## Data Flow

```text
default target packs
        +
runtime custom packs
        +
confirmed mission intent
        =
mission target pack metadata
        =
retained alert/replay proof fields
        =
Proof Mode JSON + reset-safe archive + dataset rows
```

Current follow-up items live in `dev/TODO.md`. This document is the stable contract and scope boundary.
