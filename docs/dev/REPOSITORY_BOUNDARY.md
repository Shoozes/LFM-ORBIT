# LFM-ORBIT / GenUni Repository Boundary

Updated August 4, 2026.

## Ownership and purpose

- `Shoozes/LFM-ORBIT` is the public application repository. Its `main` branch is the review, demo, and release source for the LFM-ORBIT app.
- `Shoozes/GenUni` is a separate training-cycle/producer repository. It may produce model bundles, datasets, or handoff manifests consumed by LFM-ORBIT, but it is not the application remote.
- `.tools/project.json` is the local controller authority: `git.remote` is public LFM-ORBIT and `git.trainingRemote` records the GenUni relationship.

## Recovery record

Before this synchronization, public LFM-ORBIT `main` was verified at `bb3196ad74ee8138cebb4b87cd10c5043611e164`. The reviewed Orbit application tree was preserved locally at `32eda0091df286473f0203e338e04d5a4cfe875a`. That tree had been pushed to the wrong GenUni `main` remote; GenUni's pre-migration state is `a413da770d588ff5b5b100447bfa13e9635e78e4`.

The repair keeps the public LFM-ORBIT history and adds the reviewed application tree on top of it. GenUni `main` now points to rollback commit `4068dbae0d2b3317770c45a8532536a49e077d18`, whose tree is exactly `a413da770d588ff5b5b100447bfa13e9635e78e4`. Because GenUni protects `main` from force-pushes, this is a normal fast-forward content rollback: the mistaken commits remain in GenUni history, but the branch no longer presents the Orbit application tree. Neither repository is treated as a mirror of the other.

The initial public synchronization commit was `d9206163` on top of the verified LFM-ORBIT base `bb3196ad74ee8138cebb4b87cd10c5043611e164`; the recovery-note follow-up reached `8fe6ae2c258f25c98b8a6caf1b66ededd326fb95`, and the published pitfall-ledger update is now `e20af69e847422f88f365257da7e509e24cdc950`.

## Current remote observation

As of August 4, 2026, local `main` and `origin/main` match `cc5edcc85487a92ac1a306a872643aff4cdd1717`, and the working tree is clean. CI run [30921740198](https://github.com/Shoozes/LFM-ORBIT/actions/runs/30921740198), Documentation Contracts run [30921741330](https://github.com/Shoozes/LFM-ORBIT/actions/runs/30921741330), and Pages run [30921739777](https://github.com/Shoozes/LFM-ORBIT/actions/runs/30921739777) all passed for that commit. GitHub Pages is enabled for workflow publishing with HTTPS enforced at `https://shoozes.github.io/LFM-ORBIT/`. Re-run the authenticated remote-head and tag checks below before documenting a later release.

## Review rules

- App code, app tests, hosted-demo assets, and app docs are reviewed and published from LFM-ORBIT.
- Training artifacts and producer metadata remain attributable to GenUni in the model handoff; this relationship does not change the app's Git remote.
- A future sync must verify both remote heads before pushing and must not force-rewrite LFM-ORBIT history.
- The current release handoff and unfinished external gates are owned by [TODO.md](TODO.md); this boundary document does not become a second status ledger.
