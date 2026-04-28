# Fine-Tuning Plan

Base model: `LFM2.5-VL-450M`

Dataset target: reviewed Orbit evidence tuples with image chip, bbox, task, model answer, confidence, provenance, and abstain label.

Metric: downlink decision precision/recall, abstain precision, and grounded bbox agreement.

Expected artifact: versioned adapter or checkpoint plus evaluation manifest.

Not required for Judge Mode demo.
