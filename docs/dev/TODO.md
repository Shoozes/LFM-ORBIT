# TODO

Owner: maintainers of unfinished release and operational work. Keep this file limited to active tasks; current architecture is [ARCHITECTURE.md](ARCHITECTURE.md), product proof is the root [README](../../README.md), and historical work is in Git, the [summary-bank archive](archive/summary_bank_history.json), and the [documentation compaction archive](archive/2026-08-04-integrity-review/README.md).

## P1

### Task: Approve the public browser-model handoff

What: resolve derivative GGUF redistribution, upstream terms, attribution, pinned revision, and displayed model metadata.

Why: the default Pages artifact must remain saved-packages-only until the 219 MB browser artifact is legally publishable.

Where: `source/frontend/hosted/model-manifest.json`, `docs/model/orbit_model_handoff.json`, `docs/dev/MODEL_HANDOFF.md`, and `docs/legal/THIRD_PARTY_NOTICES.md`.

How/When: owner/legal review the source model card and derivative handoff before enabling `VITE_HOSTED_MODEL_ENABLED=true` in a public deployment.

Done when: the approved terms and attribution match the manifest and notices, and an owner records the promotion decision.

Verification: run the explicit model-enabled build and the release-only model proof only after approval.

### Task: Verify iOS Safari model behavior after licensing approval

What: exercise the HTTPS model-enabled route on a real supported iOS Safari device.

Why: local Chromium cannot prove WebAssembly, storage, secure-context, and single-thread behavior on mobile Safari.

Where: hosted model entry, `useBrowserModel.ts`, Wllama runtime, and the deployed HTTPS origin.

How/When: use the pinned manifest over HTTPS; record initial transfer, local response, cancellation, reload, and cached reuse without backend traffic.

Done when: the device completes the supported text path with readable fallback/error state and no unsafe cross-origin or backend dependency.

Verification: attach device/browser/version and network evidence to the release review; keep public wording limited to the tested device matrix.

### Task: Verify preserved submission references

What: confirm that the preserved branch/tag references resolve to the intended historical submission.

Why: archive provenance is an external Git state, not something local tests can infer from current source.

Where: repository refs, `docs/dev/REPOSITORY_BOUNDARY.md`, and the history archive.

How/When: authenticated `git ls-remote --heads --tags origin` followed by immutable `git show` checks.

Done when: the intended refs are confirmed or an owner-approved replacement is recorded without changing unrelated history.

Verification: compare commit identity and repository boundary before documenting the result.

## Scope boundary

No local production stub is currently scheduled. Optional `mmproj` support and broader live-provider/model lanes remain explicitly gated capabilities; they must not be described as shipped until their runtime contracts and proof tests exist.
