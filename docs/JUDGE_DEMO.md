# Judge Demo

This is the recorded proof path for the Liquid AI x DPhi Space Hackathon submission.

Run the main recorded proof:

```bash
cd source/frontend
npm install
npm run demo:judge
```

What it proves:

1. Deterministic satellite replay
2. Edge triage
3. Liquid VLM result
4. Payload reduction
5. Provenance
6. Screenshot, video, and proof JSON artifacts
7. Tutorial-style subtitles and visible UI flow before the proof panel
8. Abstain and link-outage behavior in the full demo set

Artifacts:

```txt
source/frontend/e2e/artifacts/judge-mode/final-screen.png
source/frontend/e2e/artifacts/judge-mode/evidence-frame.png
source/frontend/e2e/artifacts/judge-mode/video.webm
source/frontend/e2e/artifacts/judge-mode/proof.json
docs/judge-mode-demo.webm
```

Payload accounting: `raw_payload_bytes` represents the local satellite frame payload. `alert_payload_bytes` represents the compact alert JSON that would be downlinked. The larger proof artifact envelope, screenshots, video, trace, and UI-only audit fields are intentionally excluded and are listed in `proof.json` under `payload_accounting.excluded_from_alert_payload_bytes`.

Use all recorded demos:

```bash
npm run demo:record
```

That writes one folder per demo under:

```txt
source/frontend/e2e/artifacts/
```

Docs video exports:

| Demo | Video |
|---|---|
| Judge Mode | `docs/judge-mode-demo.webm` |
| Payload Reduction | `docs/payload-reduction-demo.webm` |
| Provenance | `docs/provenance-demo.webm` |
| Greenland Abstain Safety | `docs/abstain-safety-demo.webm` |
| Suez Maritime Eclipse | `docs/orbital-eclipse-demo.webm` |
| Tutorial Walkthrough | `docs/tutorial_video.webm` |

Current mission split:

1. Judge Mode uses the deterministic Rondonia replay and cached real API WebM evidence.
2. Payload reduction uses a Pakistan Manchar Lake flood frame and compresses a flood alert to JSON.
3. Provenance uses an Atacama open-pit mining frame and keeps source, capture time, bbox, prompt, and model together.
4. Abstain safety uses the Greenland ice preset and shows no alert transmitted after the quality gate fails.
5. Orbital eclipse uses the Suez maritime preset, queues compact JSON while offline, then flushes on restore.

The tutorial walkthrough uses the app like an operator: load the Singapore maritime replay, inspect and analyze the retained alert, replace it with the Atacama mining replay, inspect that alert, then open Judge Mode on the active replay. The current recorded file is about 28 seconds and has distinct sampled frames across mission catalog, maritime evidence, Atacama evidence, and proof panel views.

Replay-backed Judge Mode can now keep the active replay instead of forcing Rondonia, so mission-specific proof copy stays attached to maritime, mining, flood, wildfire, and urban replay packs. Mission-preset demos use visible Sentinel-2 L2A frames and explicitly reject invalid still-image color-shift timelapses. Their real monthly WebMs are kept in the legacy `source/backend/assets/seeded_data/` cache for dataset export and training.

Replay WebMs may include cloudy context frames, but the proof panel keeps playback inside a clearer evidence window for final screenshots. Cloudy/no-data frames remain quality-gated in seeded creation and do not become positive detections.

Each recorded demo also saves `evidence-frame.png` beside `final-screen.png` and rejects blank or washed-out proof frames before copying the WebM into `docs/`.

Recorded demos preload their target mission or replay before the browser connects to telemetry. Demo config also disables the boot-time live agent pair, so recordings should not open on the legacy Amazonas sweep.

Cloud policy: cloudy or no-data Sentinel windows are not allowed to become positive detections. The backend quality gate records SCL cloud/no-data ratios, replay-cache creation skips cloudy frames, and the scanner emits no-transmit quality-gate results when cloud cover blocks evidence.

Refresh the tutorial video:

```bash
npm run demo:tutorial
```

Refresh high-quality Sentinel Hub replay cache after adding OAuth credentials:

```bash
cd source/backend
uv run --no-sync python scripts/seed_sentinel_cache.py --target rondoniaWS --grid 3 --cell-dim 0.05 --start 2023-01 --end 2025-01 --force --skip-vlm-metadata
```

Credentials can come from environment variables, `.tools/.secrets/sentinel.txt`, or `.tools/.secrets/sh.txt`. The Process API path needs an OAuth client id and client secret, either as `SH_CLIENT_ID`/`SH_CLIENT_SECRET` assignments or the legacy two-line secret-then-id format. A single OGC/WMS instance id is only usable if its `GetCapabilities` endpoint is valid; it is not enough for Process API seeding.

The current local `sh.txt` label format is also supported:

```txt
API <optional-ogc-instance-id>
CLIENTID <oauth-client-id>
CLIENT <oauth-client-secret>
```

Current cached Sentinel-2 replay assets:

| Demo | Use case | WebM |
|---|---|---|
| Payload Reduction | `flood_extent` | `source/backend/assets/seeded_data/sh_24541539.webm` |
| Provenance | `mining_expansion` | `source/backend/assets/seeded_data/sh_fbe644a9.webm` |
| Greenland Abstain Safety | `ice_cap_growth` | `source/backend/assets/seeded_data/sh_cc0e95b7.webm` |
| Suez Maritime Eclipse | `maritime_activity` | `source/backend/assets/seeded_data/sh_2d990c6b.webm` |
