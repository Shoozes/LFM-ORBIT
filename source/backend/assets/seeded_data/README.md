This folder is the local timelapse cache for replay and dataset work.

Tracked files here are promoted review fixtures. New `nasa_*` and `sh_*` WebM/meta pairs are ignored by default so normal app runs and cache refreshes do not dirty the repo. Promote a new fixture only after visual/provenance review, then force-add it and update `source/backend/data/README.md`, `docs/dev/TODO.md`, and `summary_bank.json`.
