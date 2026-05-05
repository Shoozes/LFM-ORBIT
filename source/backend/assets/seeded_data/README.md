This folder is the local timelapse cache for replay and dataset work.

Tracked files here are promoted review fixtures. New `nasa_*` and `sh_*` WebM/meta pairs and `sh_*_frames/` PNG frame folders are ignored by default so normal app runs and cache refreshes do not dirty the repo. Promote a new fixture only after visual/provenance review, then force-add the WebM, metadata, and reviewed frame PNGs, and update the relevant docs/backlog notes.
