# README Guidelines

Current as of **May 2, 2026**.

The README is the public product surface. Keep it visually strong, short enough to scan, and organized like the live GitHub version that worked well:

1. Title, two-sentence pitch, and core links.
2. One hero visual.
3. Showcase command and verification command.
4. Short highlights.
5. Proof gallery.
6. Architecture sketch.
7. Validation snapshot.
8. Model/dataset handoff.
9. Local run commands.
10. Limits and doc links.
11. Optional footer workflow infographic for the app-usage-to-training loop.

## Visual Rules

- Use one top hero visual. The current hero is `docs/media/infographics/what-is-lfm-orbit-info.png`.
- A single footer workflow infographic is allowed after Docs when it explains the training/app-growth loop rather than proof output.
- Keep proof visuals inside the proof gallery, not as extra sections before the run command.
- Public visuals must come from `docs/media/` and be referenced by Markdown.
- Do not promote app-level CV screenshots unless a visual audit confirms boxes land on visible subjects.
- Story plates must disclose fixture scope unless they come from a real model-backed detection path.
- Timelapse media must show multiple contextual imagery slices, not a static image with changing color treatment.

## Copy Rules

- Lead with what the app does, then how to run it.
- Keep the local prerequisite line near the showcase command: Python `3.10+`, Node.js `20.19.0` or `22.12.0+`, launcher-managed repo-local `uv`, and the WSL `node`/`node.exe` note if the Bash path remains supported.
- Keep progress history out of README prose. Put run-by-run notes in `docs/TODO.md` and context grouping in `summary_bank.json`.
- Use proof language: retained evidence, compact JSON, provenance, payload accounting, queueing, and abstain safety.
- Do not claim direct image-conditioned runtime inference unless `/api/analysis/status` reports `image_conditioned_runtime_enabled=true`.
- Do not turn candidate object evidence into confirmed detections unless model/replay/operator provenance supports that claim.

## Update Checklist

- README local links resolve.
- Every public media file under `docs/media/` is referenced by Markdown.
- `source/backend/tests/test_docs_artifacts.py` passes.
- The README shape guard keeps the hero before `Run The Showcase`, keeps proof visuals inside `Proof Gallery`, and keeps validation/handoff/local-run/limits/docs in that order.
- `summary_bank.json` includes the relevant feature or issue group and uses repo-relative paths.
- Validation snapshot numbers match the latest completed verification run, or the table clearly says an earlier run is being referenced.
