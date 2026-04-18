# Codex Tasks — Acceptance Criteria

Explicit pass/fail criteria for the offline-first architecture migration.

## 1. Install fetches real model over HTTP

**Pass:**
- Running option `1) Install/Repair` successfully downloads `models/lfm2.5-vlm-450m/model.safetensors` via HTTP.
- File size is > 1 MB after download.
- Re-running Install skips the download if the file is already valid.
- `$env:LFM_MODEL_URL` / `LFM_MODEL_URL` env var overrides the default URL.

**Fail:**
- File is created as empty/zero-byte (placeholder behavior).
- Download silently succeeds but file is < 1 MB.
- Re-run triggers an unnecessary re-download.

---

## 2. Running app after install works without external AI API

**Pass:**
- `GET /api/analysis/status` returns `default_model: "offline_lfm_v1"` with `available: true`.
- `POST /api/analysis/alert` returns `model: "offline_lfm_v1"` and valid `severity`, `summary`, `findings`.
- `POST /api/agent/chat` returns a reply without any external HTTP call.
- No `openai`, `OPENAI_API_KEY`, or similar external AI dependency is present in runtime code paths.

**Fail:**
- Any analysis endpoint attempts an outbound HTTP call to an AI vendor.
- Response body contains `openai_used`, `openai_available`, or `prefer_openai` fields.

---

## 3. Offline/local status is reflected in API and UI

**Pass:**
- `GET /api/analysis/status` includes `satellite_inference_loaded: bool`.
- Settings panel shows **LOCAL MODEL** section (not "AI MODEL").
- Settings panel shows **Offline Ready: Yes**.
- Settings panel shows satellite inference engine status (loaded vs standby).
- Provider status and model status are reported in separate API sections.

**Fail:**
- UI implies cloud AI dependency (e.g., "Powered by OpenAI", "API key required").
- `openai_available` field present in `/api/analysis/status`.

---

## 4. Satellite API support is preserved and documented

**Pass:**
- `/api/provider/status` returns SimSat and Sentinel Hub tier information.
- `/api/simsat/status` returns SimSat connection info.
- Settings panel shows **SIMSAT API** and **PROVIDER STATUS** sections.
- `docs/ARCHITECTURE.md` describes providers as imagery/data sources, not AI dependencies.

**Fail:**
- Provider status endpoint removed or broken.
- Providers described as AI providers.

---

## 5. Docs match code and scripts

**Pass:**
- `README.md` states "install once online, run locally/offline afterward."
- `README.md` proof table lists all five verified claims.
- `docs/ARCHITECTURE.md` describes the install vs. runtime networking split.
- No reference to "external AI", "API fallback", or "guaranteed zero-debug" in docs.
- Model storage requirement (~900 MB) noted in README.

**Fail:**
- Docs contradict code behavior.
- Setup docs omit the model download step.
- External AI API mentioned as a runtime requirement.

---

## 6. Backend test suite passes cleanly

**Pass:**
- `python -m pytest` exits 0 with 117+ passed tests.
- `test_analysis_status_endpoint_returns_model_info` asserts `satellite_inference_loaded` (bool).
- No test references `openai_available`, `prefer_openai`, or `openai_used`.
- `test_analyzer.py` docstring describes offline-only routing.

**Fail:**
- Any test imports or asserts OpenAI-related fields.
- Pytest exits non-zero.

---

## 7. Frontend E2E tests pass cleanly

**Pass:**
- Phase 7 tests assert `satellite_inference_loaded` (bool) on analysis status.
- Phase 7 analysis alert test does not send `prefer_openai` or assert `openai_used`.
- Phase 4.5 settings panel test checks for `LOCAL MODEL` section.
- Frontend lint and build exit 0.

**Fail:**
- E2E tests assert removed fields (`openai_available`, `openai_used`).
- Frontend build fails due to type errors from removed fields.
