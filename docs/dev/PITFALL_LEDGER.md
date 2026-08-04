# Pitfall Ledger

Updated August 4, 2026.

This is a compact regression-prevention ledger. It records observed workflow failures and the checks that keep them from recurring. It is not a progress log; current work belongs in TODO.md.

### Q: What pitfall are we preventing?

**What:** Publishing the LFM-ORBIT application tree to the GenUni repository because the local origin remote pointed at GenUni.

**Context and constraints:** The reviewed Orbit tree was at 32eda0091df286473f0203e338e04d5a4cfe875a. The intended app target was public Shoozes/LFM-ORBIT; GenUni is a separate training-cycle/producer repository. Main-branch work is direct and must not expose the wrong app in either repository.

**Why it happened:** The checkout inherited GenUni migration configuration. origin and .tools/project.json git.remote identified GenUni even though the working tree was the LFM-ORBIT app.

**Where:** Git remotes, .tools/project.json, .tools/gitpush.ps1, README/docs links, and the repository-boundary contract.

**Evidence:** Before repair, git remote -v reported origin https://github.com/Shoozes/GenUni.git, and authenticated git ls-remote origin refs/heads/main returned 32eda0091df286473f0203e338e04d5a4cfe875a. Public LFM-ORBIT main was separately verified at bb3196ad74ee8138cebb4b87cd10c5043611e164. The resulting GenUni content rollback is recorded at 4068dbae0d2b3317770c45a8532536a49e077d18.

**Developer story:** A normal app push went to the inherited GenUni origin. The remote heads and app tree were then checked independently. The repair renamed the training remote to genuni, configured public LFM-ORBIT as origin, corrected the controller/docs, and verified both remote heads before pushing.

**How to catch it:** Before any publish, inspect git remote -v, compare origin with .tools/project.json git.remote, and run authenticated git ls-remote for both origin/main and genuni/main. Run python -m pytest -q tests/test_project_config.py from source/backend.

**Solutions tried:**

1. 35/100 — Rely on the current branch name or the user-facing app name. Failed because branch names do not prove remote ownership.
2. 95/100 — Make public LFM-ORBIT the configured origin, retain GenUni as a named genuni remote and trainingRemote, and enforce the identity in tests/docs. Verified by the final clean checkout and remote-head audit.

**Current solution:** .tools/project.json is app-owned: git.remote is public LFM-ORBIT and git.trainingRemote is GenUni. The boundary note and controller test preserve that distinction.

**Decision rationale:** The publish target is an explicit repository contract, not an inference from training provenance. A named training remote preserves the useful relationship without allowing it to become the app destination.

**Effectiveness:** 95/100, durable. The config, docs, test assertion, and pre-push remote audit cover both automated and manual publishing paths; a raw Git command can still bypass the helper.

**Relevance check:** Current. The remote configuration and test remain active on main, and the two remote heads are part of the recovery record.

**Next prevention step:** Keep the two-remote audit as a required step before future direct pushes.

### Q: What pitfall are we preventing?

**What:** Replacing a repository’s history with an unrelated donor history, or assuming a force push is an acceptable rollback for a protected main branch.

**Context and constraints:** Public LFM-ORBIT and the reviewed local Orbit tree had unrelated histories. GenUni main was protected against force pushes. The goal was to restore GenUni’s app content while preserving public LFM-ORBIT history and branch protections.

**Why it happened:** The Orbit tree had been developed in a GenUni-based history after migration. Treating the donor commit as a public branch continuation would have exposed the wrong history; treating rollback as a force push ignored the protected-branch contract.

**Where:** Public main, GenUni main, local recovery refs, docs/dev/REPOSITORY_BOUNDARY.md, and Git push/recovery commands.

**Evidence:** git rev-list --left-right --count public/main...HEAD returned 89 811 with no merge base. The exact GenUni force-with-lease attempt was rejected with GH006: Protected branch update failed and Cannot force-push to this branch. A normal commit 4068dbae0d2b3317770c45a8532536a49e077d18 was then created with the exact a413da770d588ff5b5b100447bfa13e9635e78e4 tree and fast-forwarded to GenUni main. Public LFM-ORBIT was synchronized from bb3196ad to 8fe6ae2c without force.

**Developer story:** The public history was fetched read-only first. The missing merge base separated a safe tree synchronization from a dangerous history replacement. The public branch was based on its own head and received the reviewed tree as a new commit. GenUni recovery used a content-equivalent fast-forward because protection rejected the force path.

**How to catch it:** Check git merge-base or the left/right commit count before cross-repository synchronization. Require the destination head as a force-with-lease guard when a force operation is explicitly authorized. Prefer a normal tree rollback when branch protection rejects rewriting, and verify git rev-parse rollback^{tree} equals the intended prior tree.

**Solutions tried:**

1. 20/100 — Force-with-lease rollback of protected GenUni main. Safe in intent and correctly rejected by the branch rule; it did not restore content.
2. 96/100 — Public-history-preserving sync plus a normal fast-forward GenUni tree rollback. Both remote heads and the final trees were verified.
3. 0/100 — Force-replacing public LFM-ORBIT history with the GenUni-derived history. Rejected by policy because it would erase the public history boundary.

**Current solution:** Preserve each destination’s history. Public LFM-ORBIT receives an ordinary fast-forward sync commit; GenUni receives a normal content rollback when force updates are blocked.

**Decision rationale:** Tree equivalence restores the user-visible repository state without weakening branch protection or silently rewriting the public project’s provenance.

**Effectiveness:** 96/100, durable. The procedure was verified against actual unrelated histories, a protected-branch rejection, and both final remote heads; future changes still require deliberate destination selection.

**Relevance check:** Current. The repositories retain separate histories and the boundary note records the exact recovery commits.

**Next prevention step:** Keep public syncs fast-forward-only and record destination/base/rollback SHAs in the boundary note.

### Q: What pitfall are we preventing?

**What:** Treating GenUni’s role as application ownership, or removing GenUni from the model handoff because the app is published elsewhere.

**Context and constraints:** LFM-ORBIT consumes training-cycle outputs. The model handoff must preserve producer attribution, while app branding, Git remotes, and release docs must identify LFM-ORBIT as the application.

**Why it happened:** The migrated README and controller used GenUni as the app name and publish target, while the handoff metadata correctly identified GenUni as the training producer. Those are different contracts.

**Where:** README, .tools/project.json, docs/model/orbit_model_handoff.json, source/backend/data/HF_DATASET_CARD.md, and their contract tests.

**Evidence:** The corrected project test asserts name == LFM-ORBIT, public git.remote, and GenUni trainingRemote; the docs-artifact test still asserts handoff["producer"]["name"] == "GenUni". Active boundary references now describe GenUni only as a training-cycle/producer repository.

**Developer story:** The initial cleanup overcorrected the boundary by presenting GenUni as the app owner. The model handoff and dataset-card evidence showed that GenUni still belongs in training provenance. The final change separated runtime/public ownership from producer attribution instead of deleting the valid training relationship.

**How to catch it:** Review active docs for app links and branding, verify project remote tests, and keep the producer assertion in test_docs_artifacts.py. A GenUni reference is valid in training provenance but invalid as the public app remote or app title.

**Solutions tried:**

1. 40/100 — Remove all GenUni references from the Orbit repository. Would hide valid training provenance and weaken handoff auditability.
2. 94/100 — Keep GenUni only in explicit training-producer fields and boundary docs while making LFM-ORBIT the app identity and publish target. Verified by docs and project-config tests.

**Current solution:** LFM-ORBIT owns the application, public GitHub remote, release docs, and hosted demo. GenUni remains named in training manifests, dataset provenance, and trainingRemote only.

**Decision rationale:** Separating ownership from provenance preserves truthful attribution without allowing the training repository to become an accidental deployment or publication target.

**Effectiveness:** 94/100, durable. The distinction is encoded in config, docs, and tests; future model-handoff changes still need owner review for licensing and artifact terms.

**Relevance check:** Current. The producer contract and public app contract are both exercised on main.

**Next prevention step:** Do not rename or remove the producer field without updating the model-handoff contract and its provenance tests.
