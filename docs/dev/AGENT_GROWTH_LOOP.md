# Agent Growth Loop

Updated **May 3, 2026**.

This document turns real app usage into repeatable app and agent improvement work. It is the operating method for prompts that reveal product gaps, semantics misses, UX friction, timing issues, or evidence-boundary risk.

![App usage to agent growth loop](../media/infographics/app-usage-to-agent-growth-info.png)

## Method

1. Ask Ground Agent for a realistic operator task.
2. Observe the proposal, confirmation, map movement, bbox selection, scan behavior, and completion state as a new user would see them.
3. Record any gap as one of: semantic routing, location resolution, safety/evidence boundary, mission state, UI clarity, async timing, artifact export, or documentation.
4. Add or update a local JSONL semantics row when the phrase is product-specific tool-routing guidance.
5. Add backend contract tests for the proposal kind, details, risk level, bbox, dates, target pack, and evidence limits.
6. Add frontend or Playwright coverage for the operator flow when UI state or confirmation behavior matters.
7. Update `TODO.md`, `summary_bank.json`, and any focused doc that owns the workflow.
8. Re-run focused tests first, then broader validation when the change touches shared runtime or public proof artifacts.

## Scenario Card Format

Each reusable scenario should be short enough for future coding agents to execute without rediscovering the whole app:

```json
{
  "id": "scenario_garbage_patch_monthly_10y",
  "operator_prompt": "show me one of the biggest garbage patches in the ocean and make a timelapse for every month in the last 10 years to current",
  "expected_intent": "prepare_location_mission",
  "expected_proposal_kind": "start_custom_mission",
  "expected_target_pack": "plastic",
  "expected_region": "North Pacific Debris Convergence Review Window",
  "expected_review_bbox": [-145.6, 34.4, -145.4, 34.6],
  "must_confirm_before": ["mission launch", "map movement", "scan loop"],
  "evidence_boundary": "Candidate slick/debris review only; do not claim visible Great Pacific Garbage Patch mass or material identity from optical bands.",
  "validation": ["backend proposal test", "Ground Agent semantics fixture", "Playwright confirmation/completion flow"]
}
```

## Current Edge Scenario

Prompt:

```text
show me one of the biggest garbage patches in the ocean and make a timelapse for every month in the last 10 years to current
```

Expected flow:

1. Ground Agent drafts a `start_custom_mission` proposal, not an uncontrolled map/tool action.
2. The proposal resolves to the North Pacific debris convergence review window and applies the `plastic` target pack.
3. The proposal shows monthly cadence, a 10-year date window, bbox, target pack, and explicit candidate-only evidence limits.
4. The proposal can preserve a wider context bbox, but the mission uses a compact review bbox so the selected area scans quickly and does not pretend to cover a whole open-ocean gyre.
5. Confirming launches the mission, moves the UI to Mission, selects the bbox, and starts the live scan loop.
6. The pass reaches a visible Mission Pass Complete summary, then the operator can review alerts, timelapse, and Proof Mode.
7. Outputs remain coastal/open-ocean slick, foam-line, windrow, or floating-debris candidates. They must not claim that the Great Pacific Garbage Patch is directly visible as a coherent mass.

## Browser Flow Runbook

Future coding agents should execute this as a user story, not only as an API assertion:

1. Reset runtime state and open the app from a fresh Agent tab.
2. Send the scenario prompt through Ground Agent.
3. Verify the chat card shows `start_custom_mission`, `plastic`, `monthly`, a 10-year window, the North Pacific region label, and no-overclaim evidence guidance.
4. Confirm the proposal.
5. Verify Mission becomes active, the map selects the compact review bbox, and progress is visible.
6. Wait for Mission Pass Complete.
7. Open Logs, Inspect, or Proof Mode and verify candidate evidence remains bounded.
8. Capture any gap as semantics, location resolution, evidence boundary, mission state, UI clarity, async timing, artifact export, or docs.

## Dataset Rule

`source/backend/data/ground_agent_tool_semantics.example.jsonl` is a small local routing/eval fixture. It can guide product semantics, but it is not a world gazetteer, not a broad training corpus, and not uploaded to Hugging Face. Private expansions belong in ignored `source/backend/data/*.local.jsonl` files.
