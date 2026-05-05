# Docs Media

This folder keeps generated and hand-polished media out of the main docs root.

| Folder | Contents |
|---|---|
| `infographics/` | Product and training-flow explainers used by README files |
| `readme/` | Current README proof screenshots and retained audit captures that are directly referenced by docs |
| `story-plates/` | Promoted, visually audited public target-pack proof plates |
| `timelapse/` | GitHub-safe GIF/WebM timelapse highlights |
| `videos/` | Recorded Playwright demo WebMs |

Keep `docs/*.md` as the written docs layer. Put new visual artifacts under the appropriate media subfolder, link them from a doc when they are public proof, and update `source/backend/tests/test_docs_artifacts.py` when the artifact is part of the public proof surface. Unreferenced public media is treated as stale. Raw Playwright screenshots should stay under `source/frontend/e2e/screenshots/` or `source/frontend/test-results/` until promoted and visually audited.

## Truth Rules

- Public README media must show app state that exists in the current build.
- Public proof screenshots and story plates should carry enough `what / where / when / why` context to stand alone when shared outside the README.
- Public proof boxes must land on visible subjects or clearly labeled areas/groups; otherwise keep the asset local as a fixture/training plate instead of public detection proof.
- Non-promoted story plates stay under `source/backend/assets/seeded_data/visual_story_frames/story_plates/` for training/export review instead of public docs media.
- Story plates are deterministic visual fixtures unless their manifest says otherwise.
- App-level CV screenshots and videos stay local until visually audited.
- Timelapse media must be built from sequential imagery slices, not a static image with changing color treatment.
