# LFM-ORBIT / GenUni Repository Boundary

Updated August 4, 2026.

## Ownership and purpose

- `Shoozes/LFM-ORBIT` is the public application repository. Its `main` branch is the review, demo, and release source for the LFM-ORBIT app.
- `Shoozes/GenUni` is a separate training-cycle/producer repository. It may produce model bundles, datasets, or handoff manifests consumed by LFM-ORBIT, but it is not the application remote.
- `.tools/project.json` is the local controller authority: `git.remote` is public LFM-ORBIT and `git.trainingRemote` records the GenUni relationship.

## Recovery record

Before this synchronization, public LFM-ORBIT `main` was verified at `bb3196ad74ee8138cebb4b87cd10c5043611e164`. The reviewed Orbit application tree was preserved locally at `32eda0091df286473f0203e338e04d5a4cfe875a`. That tree had been pushed to the wrong GenUni `main` remote; GenUni's pre-migration state is `a413da770d588ff5b5b100447bfa13e9635e78e4`.

The repair keeps the public LFM-ORBIT history and adds the reviewed application tree on top of it. It rolls GenUni `main` back to its pre-migration state with an explicit lease check. Neither repository is treated as a mirror of the other.

## Review rules

- App code, app tests, hosted-demo assets, and app docs are reviewed and published from LFM-ORBIT.
- Training artifacts and producer metadata remain attributable to GenUni in the model handoff; this relationship does not change the app's Git remote.
- A future sync must verify both remote heads before pushing and must not force-rewrite LFM-ORBIT history.
