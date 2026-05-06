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
- Backend tests: 479 passed
- Frontend typecheck/build passing
- Playwright passing with intentional skips
- Demo media regenerated
- Docs/import guards passing

## Runtime boundaries

- Default hackathon runtime uses DPhi Space SimSat Sentinel.
- SimSat Mapbox is optional imagery/context support when configured.
- Replay fixtures are deterministic review assets.
- The local GGUF runtime performs evidence-packet reasoning.
- Image-conditioned retained-frame review is available only when the opt-in image runtime reports enabled; otherwise Orbit stays in evidence-packet reasoning mode with structured unavailable or abstain responses.
- Proof JSON carries `visual_model_review` so enabled reviews and unavailable fallback states stay auditable.
