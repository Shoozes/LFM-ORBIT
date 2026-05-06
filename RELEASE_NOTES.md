# LFM-ORBIT v0.4.0 Public Proof

LFM-ORBIT is a local-first satellite timelapse triage system. A space-side agent scans map cells and prunes low-value imagery before downlink. A ground-side agent reviews retained evidence packets with provenance, timelapse context, CV boxes, local model reasoning, and compact proof JSON.

## Proof package

- Critical Minerals Expansion Watch showcase
- Tutorial walkthrough video
- Payload reduction proof
- Provenance proof
- Link outage queue/restore proof
- Abstain safety proof
- Deterministic replay-backed public media

## Validation

- Root verify passing
- Backend tests: 465 passed
- Frontend typecheck/build passing
- Playwright passing with intentional skips
- Demo media regenerated
- Docs/import guards passing

## Runtime boundaries

- Default hackathon runtime uses DPhi Space SimSat Sentinel.
- SimSat Mapbox is optional imagery/context support when configured.
- Replay fixtures are deterministic review assets.
- The local GGUF runtime performs evidence-packet reasoning.
- Direct image-conditioned production inference is not claimed until mmproj/native VLM runtime support is wired and smoke-tested.
