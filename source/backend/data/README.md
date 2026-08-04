# Orbit Data Folder

This folder is for local data inputs that help Orbit gather, package, retag, and hand off training data. It is not the main runtime cache. Runtime-generated assets normally live under `runtime-data/`, while this folder holds repo-local data packs such as boundaries, local fixtures, or optional operator-managed imports.

## What This Is

Orbit's data cycle is:

1. The app gathers evidence during realtime missions, replay from cached real API imagery, monitor previews, imagery fetches, optional visual evidence helper calls, and timelapse generation.
2. The backend stores alert metadata, gallery evidence, thumbnails, videos, observations, agent decisions, and monitor reports.
3. `scripts/export_orbit_dataset.py` packages those records into an Orbit dataset export with JSONL manifests and local assets.
4. `scripts/retag_training_assets.py` walks the export, deduplicates images and frames by SHA-256, extracts timelapse frames, preserves temporal sequence context, and retags assets with a chosen provider.
5. The retagged folder can be reviewed locally, loaded as Hugging Face JSONL configs with `images/` assets, uploaded to Hugging Face, or used by external fine-tuning jobs.
6. Trained artifacts can come back through the model handoff/fetch path documented in `../../../docs/dev/MODEL_HANDOFF.md`.

The goal is a closed loop: collect evidence in Orbit, package it cleanly, retag it with a stronger vision model when useful, train or evaluate externally, then bring model artifacts back into Orbit.

![LFM-ORBIT data cycle](../../../docs/media/infographics/image-to-training-data-flow-info.png)

The app-growth loop starts even earlier: real operator prompts become confirmable actions, tests, docs, local semantics rows, and then model/app improvements. The archived method note lives in `../../../docs/dev/archive/AGENT_GROWTH_LOOP.md`.

![App usage to agent growth loop](../../../docs/media/infographics/app-usage-to-agent-growth-info.png)

## Folder Roles

- `source/backend/data/`
  Repo-local data inputs and fixtures. Keep this small and intentional.
- `source/backend/data/boundaries/`
  Boundary/concession/protected-area inputs used by overlay import tooling.
- `source/backend/data/ground_agent_tool_semantics.example.jsonl`
  Small product-specific Ground Agent routing/eval examples for local tool semantics such as map navigation, replay loading, mission-pack launch, and link-state changes. This is not a Hugging Face dataset and not a geography source of truth.
- `source/backend/data/ground_agent_tool_semantics.local.jsonl`
  Optional private extension for local experiments. It is ignored by git via `source/backend/data/*.local.jsonl`.
- `runtime-data/`
  Mutable local runtime state, generated exports, model bundles, and scratch outputs.
- `runtime-data/modeling/orbit-export/`
  Recommended output location for dataset exports.
- `runtime-data/modeling/orbit-export/retagged_training/`
  Recommended output location for retagged image/frame/sequence training data.

## Export Dataset

From the backend folder:

```powershell
cd source/backend
uv run --no-sync python scripts\export_orbit_dataset.py `
  --output-dir ..\..\runtime-data\modeling\orbit-export `
  --monitor-reports-dir ..\..\runtime-data\monitor-reports `
  --include-seeded-cache `
  --offline-context-thumbnails
```

The export writes:

- `samples.jsonl`
- `train.jsonl`
- `eval.jsonl`
- `training.jsonl`
- `train_training.jsonl`
- `eval_training.jsonl`
- `manifest.json`
- `samples/<sample_id>/sample.json`
- local assets such as `context_thumb.png` and `timelapse.webm`

Export rows include target task/category/action, temporal use-case metadata, alert scores, agent evidence, optional `visual_model_review`, local imagery/video references, provenance, replay-cache timelapse rows when enabled, weak-negative reject rows when available, and `orbit_training_contract_v1` review/localization metadata for LiquidAI Leap Tune-compatible import.

If a context thumbnail falls back to an offline SVG chip, the exporter rasterizes it to PNG before writing the sample asset. Use `--offline-context-thumbnails` for local refreshes that should not wait on ESRI thumbnail fetches. The exporter also clears generated `samples/` before writing the new footprint so retag loose scans do not pick up stale sample assets.

## Ground Agent Tool Semantics

`ground_agent_tool_semantics.example.jsonl` is a small local eval/guidance fixture for product-specific operator language. It helps keep phrases such as "take me to the Bronx, NY", "show me the Suez canal", "scan the Bronx for changes", "show me a monthly 10-year garbage patch timelapse", "load the Manchar flood replay", and "restore the downlink" aligned with the intended proposal kinds.

The file must stay local to the repo and should not be uploaded to Hugging Face. It is too small and product-specific for public training value. It also must not become a hidden gazetteer: location names still resolve through explicit vetted targets or a future geocoding provider behind `/api/location/resolve`.

Future marine-debris examples should stay out of the active fixture until `start_marine_debris_scan` exists in the backend whitelist, scan path, and UI. Prototype those rows in `ground_agent_tool_semantics.local.jsonl` only; archived Sentinel lane boundaries live in `../../../docs/dev/archive/FUTURE_SENTINEL_LANES.md`.

## Optional Sentinel Replay Data

LFM Orbit's portfolio runtime is DPhi Space SimSat-first. Sentinel Hub is optional support for local real-data testing, replay-cache refreshes, and dataset development; the default showcase does not need Sentinel Hub credentials.

High-quality replay timelapses can be refreshed from Sentinel Hub and then reused by demos and dataset export through the existing `assets/seeded_data/sh_<signature>.webm` cache. The folder name is legacy; the data is stored real API imagery, not generated evidence.

Generated `nasa_*` and `sh_*` WebM/meta pairs are ignored by default. Promote only reviewed fixtures with `git add -f`, then record the provenance and docs references in this file, `docs/dev/TODO.md`, and `summary_bank.json`.

The seeder requests Sentinel SCL quality data before each visual frame. Cloud shadow, medium/high cloud probability, cirrus, no-data, and defective pixels are quality-gated before WebM creation. Accepted frames store `frame_quality` metadata; rejected windows are stored in `_meta.json` under `rejected_windows`.

Credentials can come from environment variables or local developer secret files. The Sentinel Hub Process API uses OAuth credentials. Supported local forms include `SH_CLIENT_ID=...` / `SH_CLIENT_SECRET=...`, two-line legacy secret-then-id files, or labeled trial bundles:

```txt
API <optional-ogc-instance-id>
CLIENTID <oauth-client-id>
CLIENT <oauth-client-secret>
```

```powershell
cd source/backend
uv run --no-sync python scripts\seed_sentinel_cache.py `
  --target rondoniaWS `
  --grid 3 `
  --cell-dim 0.05 `
  --start 2023-01 `
  --end 2025-01 `
  --force `
  --skip-vlm-metadata
```

Current high-quality replay assets:

| Use case | Target | Replay WebM |
|---|---|---|
| `flood_extent` | Pakistan Manchar Lake flood | `assets/seeded_data/sh_24541539.webm` |
| `mining_expansion` | Atacama open-pit mining | `assets/seeded_data/sh_fbe644a9.webm` |
| `ice_cap_growth` | Greenland Ilulissat ice edge abstain preview | Legacy static cache excluded from Replay Cache |
| `ice_snow_extent` | Greenland ice/snow extent replay with NDSI/SCL metadata | Metadata-only curated replay until a refreshed contextual WebM is seeded |
| `maritime_activity` | Suez maritime channel | `assets/seeded_data/sh_2d990c6b.webm` |
| `maritime_activity` | Singapore Strait maritime anchorage | `assets/seeded_data/sh_99548137.webm` |
| `wildfire` | Florida SR-26/Balu Forest wildfire candidate | `assets/seeded_data/sh_83e3aea2.webm` |
| `wildfire` | Highway 82 Georgia wildfire candidate | `assets/seeded_data/sh_4015e8b8.webm` |
| `wildfire` | Pineland Road wildfire smoke/cloud review candidate | `assets/seeded_data/sh_af5954b2.webm` |
| `wildfire` | Spain Larouco wildfire burn-scar review | `assets/seeded_data/sh_09384ab0.webm` |
| `crop_phenology` | Kansas seasonal crop-control sequence | `assets/seeded_data/sh_8342a218.webm` |
| `urban_expansion` | Delhi NCR urban expansion review | `assets/seeded_data/sh_f03170dc.webm` |
| `volcanic_surface_change` | Mauna Loa lava-flow surface-change review | `assets/seeded_data/sh_53c969f1.webm` |
| `flood_extent` | Lake Urmia water persistence review | `assets/seeded_data/sh_3ceea0a9.webm` |
| `urban_expansion` | Black Rock City recurring temporary-settlement review | `assets/seeded_data/sh_73634fe8.webm` |
| `wildfire` | Lahaina wildfire burn-scar recovery review | `assets/seeded_data/sh_a7815591.webm` |
| `flood_extent` | Kakhovka reservoir drawdown review | `assets/seeded_data/sh_b9993f84.webm` |
| `volcanic_surface_change` | Kilauea summit eruption review | `assets/seeded_data/sh_07ea2b1b.webm` |
| `flood_extent` | Lake Mead shoreline recovery review | `assets/seeded_data/sh_c8ec6b43.webm` |

Each replay asset stores a matching `_meta.json` with bbox, frame dates, provider, use-case id, target category, and target task. These rows flow into export when `--include-seeded-cache` is set.

Event-specific wildfire seeds should use explicit date windows and the real Sentinel-2 SWIR/NIR/Red burn-scar composite instead of generic monthly mosaics:

```powershell
uv run --no-sync python scripts\seed_sentinel_cache.py `
  --lat 31.223 `
  --lon -81.836 `
  --grid 1 `
  --cell-dim 0.08 `
  --visual-mode burn_scar `
  --use-case-id wildfire `
  --target-category wildfire `
  --target-pack-id fireline `
  --target-task wildfire_close_look_candidate_review `
  --date-window pre-fire=2026-04-01:2026-04-10 `
  --date-window ignition-window=2026-04-20:2026-04-23 `
  --date-window active-fire=2026-04-24:2026-04-26 `
  --date-window latest-clear=2026-04-27:2026-04-28 `
  --skip-vlm-metadata
```

Treat this as candidate evidence until the contact sheet is visually reviewed; cloud, smoke, or missing-scene artifacts should not replace a clearer demo. Wildfire exports should carry `wildfire` as the category, `fireline` as the target pack, frame PNGs, and the SWIR/NIR/Red band stats from accepted frames. If too many windows are rejected, widen the date window or pick another clear acquisition instead of forcing a cloudy timelapse.

## Risk Watch Manifests

Timestamped watch manifests live under `source/backend/assets/watchlists/`. They are not labels and they are not predictions that an ignition will occur. They record an official risk outlook before the outcome is known so a later verification pass can prove whether an incident source or satellite evidence appeared after the valid window.

Current watch:

| Watch | Valid window | Status | Proof file |
|---|---|---|---|
| SPC Day 2 critical fire-weather corridor, eastern New Mexico into western Texas | `2026-04-28T12:00:00Z` to `2026-04-29T12:00:00Z` | `incident_report_verified_candidate` via NM Fire Info Sparks Fire report; satellite confirmation still pending | `assets/watchlists/wildfire_spc_day2_southern_high_plains_2026-04-28.json` |

Only seed Sentinel-2 post-event imagery after an independent active-fire or incident source exists inside the bbox. The Sparks Fire report clears that source gate, but it is not yet a satellite-confirmed burn-scar row.

## Retag Assets

Run the second pass after export:

```powershell
cd source/backend
uv run --no-sync python scripts\retag_training_assets.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export `
  --provider ollama `
  --model qwen3.6:27b `
  --reuse-existing-dir ..\..\runtime-data\modeling\orbit-export\retagged_training `
  --reuse-existing-only
```

`--max-provider-assets` keeps local visual-model retagging bounded for show-ready runs. `--max-provider-sequences 0` keeps temporal sequence rows heuristic by default because multi-image local visual-model calls are slower; set a positive number when you intentionally want sequence-level model calls.

Use `--reuse-existing-dir <previous-retagged-folder>` to avoid sending already-tagged image hashes back through Qwen/Ollama. Add `--reuse-existing-only` for normal refresh/upload cycles where existing visual-model labels should be preserved and any new hashes should receive deterministic heuristic labels. Use `--no-reuse-existing-sequences` when sequence-level prompts changed and should be regenerated while still reusing image-level tags.

Provider options:

- `heuristic`
  Local metadata-based retagging. No network or model dependency. Good for dry runs and packaging checks.
- `queue`
  Writes `review_queue.jsonl` for manual or external retagging while still packaging deduplicated assets.
- `ollama`
  Sends images to a local Ollama vision model such as Qwen VL. The CLI and UI default to `qwen3.6:27b` with thinking disabled for cleaner JSON responses.
- `openai`
  Sends images to an OpenAI-compatible vision endpoint. Requires `OPENAI_API_KEY`.

Example with Ollama:

```powershell
uv run --no-sync python scripts\retag_training_assets.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export `
  --provider ollama `
  --model qwen3.6:27b `
  --max-provider-assets 16
```

Example with OpenAI-compatible vision:

```powershell
$env:OPENAI_API_KEY = "..."
uv run --no-sync python scripts\retag_training_assets.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export `
  --provider openai `
  --model gpt-4.1-mini
```

## Retag Output

The retagger writes:

- `retagged_training/images/`
  Deduplicated image assets and extracted video frames.
- `retagged_training/metadata.jsonl`
  Image asset metadata with labels, reason codes, quality, confidence, and duplicate-reference counts.
- `retagged_training/retagged_assets.jsonl`
  Full Orbit asset records with provider/model output and source references.
- `retagged_training/training_assets.jsonl`
  Image-level SFT rows.
- `retagged_training/temporal_sequences.jsonl`
  Ordered timelapse sequence records.
- `retagged_training/training_temporal_sequences.jsonl`
  Sequence-level SFT rows.
- `retagged_training/review_queue.jsonl`
  Prompts and references for manual/external review.
- `retagged_training/skipped_assets.jsonl`
  Assets skipped due to unsupported type, unresolved paths, or invalid videos.
- `retagged_training/manifest.json`
  Counts, paths, provider, model, and processing notes.

## Duplicate Policy

Training assets are deduplicated by SHA-256. If the same image or extracted frame appears in multiple samples, Orbit writes one asset row and stores every source under `references`.

This avoids duplicate training examples while preserving auditability.

Extracted timelapse frames are also namespaced by the source video SHA-256. That prevents different samples named `timelapse.webm` from overwriting one another in the generated frame folder.

## Timelapse Policy

Timelapse videos are not trained as opaque video blobs by default.

The retagger:

1. Decodes each video.
2. Rejects videos with fewer than two frames.
3. Samples a configurable number of frames.
4. Deduplicates extracted frames by SHA-256.
5. Writes still-frame training rows.
6. Writes ordered temporal sequence rows so before/after context is preserved.

This matters because a true timelapse must contain multiple contextual satellite imagery slices. A static image that only changes color is invalid temporal evidence and should be reviewed or rejected.

Useful options:

```powershell
uv run --no-sync python scripts\retag_training_assets.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export `
  --video-frame-count 6 `
  --min-video-frames 2
```

## Hugging Face Handoff

The Hub dataset is shaped as explicit JSONL configs so single-image SFT rows, ordered temporal SFT rows, metadata, review queues, and optional mission metadata do not get inferred as one mixed schema. Do not include an empty `mission_metadata` config in the Hub card; Dataset Viewer treats empty JSONL configs as split-parse failures.

```python
from datasets import load_dataset

assets = load_dataset("Shoozes/LFM-Orbit-SatData", "default", split="train")
temporal = load_dataset("Shoozes/LFM-Orbit-SatData", "temporal_sft", split="train")
metadata = load_dataset("Shoozes/LFM-Orbit-SatData", "asset_metadata", split="train")
```

For local validation before upload, point `load_dataset()` at `runtime-data/modeling/orbit-export/retagged_training` with the same config names. For sequence-aware training, use `training_temporal_sequences.jsonl` alongside the referenced frame paths in `images/`.

Upload helper:

```powershell
cd source/backend
uv run --no-sync python scripts\upload_orbit_dataset_hf.py `
  --dataset-dir ..\..\runtime-data\modeling\orbit-export\retagged_training `
  --repo-id your-user-or-org/lfm-orbit-dataset `
  --create-repo `
  --private
```

The helper reads `HF_TOKEN`, `HUGGINGFACE_HUB_TOKEN`, or a local developer token file, then calls the `hf` CLI with the token in process environment only. Before upload it validates root JSONL files, referenced image assets, local path leaks, orphaned image files, and README config paths. Use `--dry-run` to inspect the upload command without network calls. Use repeated `--delete` patterns when a cleaned export should replace generated Hub files such as `samples/**`, `samples.jsonl`, and `manifest.json`.

Current training-focused replay/cache export result after the wildfire refresh:

- Dataset export: `46` samples, `33` replay-cache rows, `7` visual story frames, `5` monitor-report rows, `0` mission metadata rows, and `34` rows with timelapse references.
- Retag output: `265` image-level SFT rows, `33` temporal-sequence SFT rows, `145` reused image tags, `14` reused sequence tags, `0` skipped assets, `0` image tagger failures, and `0` sequence tagger failures.
- Wildfire seeds include Florida SR-26/Balu Forest, Georgia Highway 82, Pineland Road, Spain Larouco, Lahaina, and related fireline/burn-scar review candidates. Applicable rows are tagged `wildfire` / `fireline`, include Sentinel-2 burn-scar composite provenance, and carry frame-level labels for model training.
- The Hub upload uses the retagged folder, not raw `samples/`, so training rows point to `images/` assets and export-relative provenance.

## Dataset Refresh Cadence

- Use semantic refresh labels such as `orbit-satdata-YYYY-MM-DD` for local export/retag folders.
- Publish only changed assets and metadata configs; avoid re-uploading already-present hashes unless a schema changes.
- Keep `mission_metadata` for metadata-only missions such as the Greenland ice/snow extent replay instead of forcing invalid timelapse assets into image configs.
- For public training refreshes, use `--no-missions --no-archived-missions` when local operator mission archives would flood image training with repeated intent-only rows. Include `mission_metadata` deliberately when the refresh goal is tool/intent tuning.
- Record each Hub refresh in this README, `docs/dev/DATASET_CYCLE_TUTORIAL.md`, and `summary_bank.json` with counts, commit hash, tagger source, and skipped/failed asset counts.
- For portfolio demos, prefer seeded replay data and SimSat runtime evidence before spending direct-provider quota on refreshes.
- Hugging Face dataset: `Shoozes/LFM-Orbit-SatData`, data payload commit `9ccff9ce7315e270ca1b280c82c39414ce591d01`, Dataset Viewer verification commit `2df07094f36037e71c7e14e28dfbd298343be359`, final card documentation commit `550c98f7c9b84eefbe3c0c6eb77b33a70028402a`, with `records=46`, `seeded_cache_records=33`, `monitor_report_records=5`, `mission_metadata_records=0`, `unique_training_assets=265`, `unique_temporal_sequences=33`, remote `num_rows=1126`, `70` wildfire image rows, and `11` wildfire temporal rows.
- Dataset Viewer schema note: upload `source/backend/data/HF_DATASET_CARD.md` as the Hub `README.md` so single-image SFT rows, temporal SFT rows, metadata, mission metadata, and review records load as separate configs instead of one mixed inferred JSON split.

## Optional Tkinter UI

The CLI is the source of truth. `scripts/retag_training_assets_ui.py` is a small Tkinter wrapper around the same retag command; it does not implement separate data logic.

Run it from the backend folder:

```powershell
cd source/backend
uv run --no-sync python scripts\retag_training_assets_ui.py
```

The UI exposes:

- Dataset directory picker.
- Output directory picker.
- Provider selector: `heuristic`, `queue`, `ollama`, `openai`.
- Model text field.
- Frame count and minimum video frames.
- Model image-call and sequence-call budgets. Defaults use Qwen for representative still images and keep sequence rows heuristic unless explicitly enabled.
- Run button that calls `scripts/retag_training_assets.py` in a subprocess.
- Optional Hugging Face upload controls for repo id, create-repo, private repo, and upload-as-PR after a successful retag pass.
- Scrollable output log.
- Manifest summary after a successful run.

Recommended behavior:

- Default `dataset_dir` to `runtime-data/modeling/orbit-export`.
- Default provider to `ollama`.
- Default model to `qwen3.6:27b`.
- Keep provider secrets in environment variables, not UI fields, especially `OPENAI_API_KEY`.
- Disable the run button while the subprocess is active.
- Never write retag output into `source/backend/data/`; keep generated results under `runtime-data/`.

Tkinter is useful for operator convenience, but the repeatable workflow remains the CLI commands above. If Python was installed without Tkinter, use the CLI directly.

## What Goes Where

Use `source/backend/data/` for:

- Boundary files before import.
- Small local fixtures.
- Human-maintained notes about local datasets.

Use `runtime-data/` for:

- Generated dataset exports.
- Retagged training outputs.
- Runtime SQLite files.
- Downloaded model artifacts.
- Large imagery/video caches.

Avoid committing large generated datasets unless the repo intentionally tracks a small replay fixture pack.
