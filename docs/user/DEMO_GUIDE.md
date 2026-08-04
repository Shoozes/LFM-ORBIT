# Full application demo

Owner: application reviewers and operators. This is the shortest reliable path through the full local mission-control app; the browser-only route has its own [hosted handoff](HOSTED_DEMO.md).

## Prerequisites

- Windows: Python `3.10+`, Node.js from `.nvmrc`, and PowerShell.
- Linux/macOS: Python `3.10+`, Node.js from `.nvmrc`, and Bash.
- The launcher installs locked dependencies. The trained GGUF is optional for fallback development runs and required only for the full-runtime model path.

## Start

From the repository root:

```powershell
.\run.ps1 -Install
```

```bash
./run.sh --install
```

Open `http://127.0.0.1:5173`. The default local provider is the bundled SimSat/replay path; external credentials are not needed for the deterministic review.

## Five-step reviewer path

1. Open **Mission** and choose **Critical Minerals Expansion Watch** or **Replay**.
2. Load the saved replay or start the selected mission. Confirm the area, time window, and scan status are visible.
3. Open **Logs** and **Inspect**. Check the retained evidence, source metadata, acquisition identity, and candidate wording.
4. Open **Agents** and then **Proof Mode**. Confirm SAT/GND messages, queue state, provenance, payload accounting, and the compact proof JSON.
5. Reload or replace the mission and confirm the visible replay/scan context follows the new mission rather than a stale demo URL.

## Expected proof

The app demonstrates satellite-first triage, bounded retention, agent handoff, replayable evidence, and training-ready export metadata. It does not prove live imagery, exact object counts, or image-conditioned GGUF inference unless the corresponding runtime status and provenance say so. Candidate, proxy-only, and fixture evidence remains clearly labeled.

For target-pack contracts and safety wording, see [OBJECT_EVIDENCE_MODE.md](OBJECT_EVIDENCE_MODE.md). For the data/model boundary, see [architecture](../dev/ARCHITECTURE.md) and [model handoff](../dev/MODEL_HANDOFF.md).

## Verification and media

```powershell
.\run.ps1 -Verify
```

For frontend-only checks:

```bash
cd source/frontend
npm run test:e2e
npm run demo:showcase
npm run demo:tutorial
```

Media production is intentionally outside the required application E2E suite. Its explicit commands use `playwright.media.config.ts`; generated artifacts belong under `docs/media/`.

## Troubleshooting

- Hosted route: [HOSTED_DEMO.md](HOSTED_DEMO.md).
- Runtime pitfalls: [PITFALL_LEDGER.md](../dev/PITFALL_LEDGER.md).
- Current unfinished external gates: [TODO.md](../dev/TODO.md).
