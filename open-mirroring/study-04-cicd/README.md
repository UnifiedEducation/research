# Study-04: CI/CD

Answers decision question **Q6 (version control and deployment)**.

## Goal

Prove the Mirrored Database fits the existing `Fabric_BMAD_DEV` -> `Fabric_BMAD_PROD` deployment flow with a small, explicit bolt-on to the current GitHub Actions workflows.

## How Fabric handles mirrored-DB CI/CD

- **Git integration**: Once Git is connected to the workspace, committing the mirrored DB item produces a folder in the repo:
  ```
  bronze_mirror.MirroredDatabase/
    mirroring.json    # the item definition
    .platform         # system file, holds stable logicalId
  ```
  For open mirroring (no source connection), `mirroring.json` is small and changes rarely. New tables being added by producers are a **runtime** event - they don't show up in the item definition, which is a simplification for us.
  Only the mirrored DB item itself is tracked. The SQL analytics endpoint and any views are **not** tracked.

- **Deployment pipelines**: The built-in Fabric DEV -> PROD deployment pipeline propagates the item across stages. Because open mirroring has no source connection, the "Data source rules" step that other mirroring types need is a no-op for us.

## Critical gotcha

**Mirroring does NOT auto-start on the target after deployment.** Every environment needs an explicit "start mirroring" call after the item is deployed.

`poc_start_mirroring.py` in this folder is the post-deploy hook - it reads `BRONZE_MIRROR_ID` and `FABRIC_WORKSPACE_ID` and calls `POST /mirroredDatabases/{id}/startMirroring`.

## Per-environment configuration

Producer apps (notebooks, User Data Functions, Claude Routines) need the landing-zone URL, which is per-item. So:

| Secret / env var | DEV value | PROD value |
|------------------|-----------|------------|
| `FABRIC_WORKSPACE_ID` | `Fabric_BMAD_DEV` GUID | `Fabric_BMAD_PROD` GUID |
| `BRONZE_MIRROR_ID` | DEV mirror GUID | PROD mirror GUID |

Derived at use time:
```
landing_zone_url = f"https://onelake.dfs.fabric.microsoft.com/{FABRIC_WORKSPACE_ID}/{BRONZE_MIRROR_ID}/Files/LandingZone"
mirror_root_path = f"abfss://{FABRIC_WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_MIRROR_ID}"
```

Both forms are already built by `feasibility/open-mirroring/clients/config.py` (`landing_zone_url()` and `tables_abfss_root()`).

## Deployment shape - likely a different path from existing CI

The current `.github/workflows/deploy-to-*.yml` were built for the dbt project. The mirrored-DB deployment flow is different enough that forcing it into that workflow is probably the wrong fit:

- The mirrored DB item is promoted by the **Fabric deployment pipeline** (portal or REST) rather than by uploading files through `fab cp`.
- The only external step from CI is the post-deploy "start mirroring" REST call.
- Producer apps (YouTube scraper, Skool agent, Claude Routines) have their own deployment lifecycles that are not tied to the dbt project.

Treat the CI path as open: during Study-04 execution, validate each step manually first. Decide the home of the `start_mirroring` hook only after observing what the portal / deployment pipeline leaves unfinished on the target stage. `deploy-mirror-workflow.yml.example` in this folder is illustrative only - do not wire it up yet.

## Run order to validate

1. Enable Git integration on `Fabric_BMAD_DEV` workspace.
2. In the portal, commit the `bronze_mirror` item. Verify that `bronze_mirror.MirroredDatabase/mirroring.json` appears in git.
3. In the portal, create a deployment pipeline from `Fabric_BMAD_DEV` -> `Fabric_BMAD_PROD` and deploy. Verify a new `bronze_mirror` item appears in PROD, NOT started.
4. Set `BRONZE_MIRROR_PROD_ID` in repo secrets.
5. Run `python poc_start_mirroring.py --wait` against PROD. Verify mirroring reaches `Running`.
6. Run Study-01's smoke upload with PROD env vars. Verify rows land in PROD mirror.

## Verdict (2026-04-20 - partial)

What's been verified from Claude's side:

- [x] `poc_start_mirroring.py` calls the REST API correctly. Against a running mirror it short-circuits with `"Already running. Nothing to do."` - the intended behaviour. `start_mirroring` in `mirror_api.py` returns HTTP 202 on a cold-start (was the PROD item's state earlier in this session, before it was deleted).
- [x] `mirror_api.create_mirrored_database` now includes a `GenericMirror` definition part so a REST-created item is immediately startable. (Originally the bare POST left the item in `MirroringDefinitionMissing` and `startMirroring` returned 400. Fixed in `mirror_api.open_mirror_definition()`.)

Requires portal / user action:

- [ ] Enable Git integration on `Fabric_BMAD_DEV`, commit the `bronze_mirror` item, confirm `bronze_mirror.MirroredDatabase/mirroring.json` appears in git.
- [ ] Inspect the `mirroring.json` diff - confirm it doesn't include stage-specific values (landing zone URL, workspace ID) that would break promotion.
- [ ] Create a DEV -> PROD deployment pipeline, deploy, confirm target item arrives with `status: Initialized` (not started).
- [ ] Call `poc_start_mirroring.py --wait` against the PROD target, confirm it transitions to `Running`.
- [ ] Re-run Study-01's smoke upload against the PROD mirror to prove end-to-end promotion.
- [ ] Decide where the post-deploy start hook lives: a Fabric notebook, a new dedicated GitHub Action, or a manual checklist entry. Per user redirect, **do not** bolt it onto the existing dbt GitHub Actions.

## Open questions to resolve during execution

- Can `fab` CLI handle Git commit / deployment pipeline trigger, or is manual portal action required?
- Is there a Fabric Git integration REST API we can use to automate the commit step from CI? (Per-item commits, not branch-level.)
- Does the `mirroring.json` contain the landing-zone URL (bad for promotion - it's stage-specific) or only the logical definition (good for promotion)?
