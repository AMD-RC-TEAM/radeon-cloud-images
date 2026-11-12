# radeon-cloud-images

The single source for the images behind the "stable" rows of the Radeon Cloud image picker
(owner decisions D-20261112-26, -27, -28, -29, -33). Every image is defined by a Dockerfile, and
**merging a change to `main` releases it**.

Everything in this repository is written in English: docs, comments, script output, workflow
names, issues, PRs and commit messages.

## Layout
```
images/<name>/
  Dockerfile   # first line "# upstream: <registry>/<repo>:<tag>@sha256:...", FROM points at the same digest in the Wuxi Harbor
  image.yaml   # rc_repo (Harbor alias repo), catalog_row (the stable row), smoke profile, upstream tag rule
  smoke.sh     # runs inside the image on one W7900D; prints "SMOKE PASS" last on success
tools/
  release.py         # release one image: mirror upstream -> smoke -> move rc-current
  mirror.sh          # resumable, digest-checked mirror (the Wuxi edge cuts single connections at ~10 min), then crane push
  harbor.py upstream_check.py
  ci/slot_pool.py    # CI GPU slot leases shared with Radeon-Cloud-Internal CI (vendored, keep in sync)
.github/workflows/
  pr-check.yml       # required on every PR: validate + smoke (smoke only; no tag or catalog change)
  release.yml        # on push to main touching images/**: release the changed images
  upstream-check.yml # daily: if upstream has a newer tag, push an upgrade branch and open an issue with a one-click PR link
  rollback.yml       # manual one-click rollback
```

## Release flow (`release.yml`)
1. **Mirror.** If Harbor does not have the upstream digest yet, mirror it to `radeon-cloud-global/<upstream repo>:<tag>`
   with the digest unchanged. Cluster nodes never pull large images from the internet.
2. **Smoke.** Claim a CI slot with `tools/ci/slot_pool.py`, run a 1-GPU Job in the slot namespace
   (nodes labelled `amd-oneclick.io/workload-ci=enabled`) that runs `smoke.sh`. No `SMOKE PASS` means failure.
   The slot is released only once the Job is confirmed gone; otherwise it is quarantined.
3. **Alias.** Copy the digest server-side into `radeon-cloud-global/rc/<category>`, move the old `rc-current`
   to `rc-prev`, and point `rc-current` at the new digest.
4. **Catalog (outside CI).** The stable catalog rows track `rc/<category>:rc-current`. rc-ops runs a small sync
   job (not in this repo's CI) that calls the existing `POST /api/admin/images/{id}/harbor` and `.../harbor/adopt`
   with an owner Admin session, GT first, then Global and China. It only touches stable rows and refuses a row
   that any template points at.
5. **Failure.** No alias move; one line is added to the day's "image pipeline daily" issue.
6. **Production +1 h.** rc-ops' existing post-deploy checks watch launch failures; a regression means rollback.

## Rollback
Actions -> rollback -> image: `rc-current` goes back to `rc-prev`; the catalog sync then adopts it.
The digest that was rolled back stays tagged `rc-rolled-back`.

## Adding or upgrading an image
- **Upgrade:** change the tag@digest on the Dockerfile's first line and the `FROM` digest (the daily bot prepares
  this branch for you), read the upstream release notes, merge.
- **New image:** add `images/<name>/` with the three files, after rc-ux has created a stable row in Admin that
  tracks `rc/<category>:rc-current`. Dockerfiles with RUN/COPY steps will be built with Kaniko (second batch;
  SGLang+hk-dsl comes as a PR from hk-B).

## Credentials (never in GitHub)
Only one, kept as a k8s Secret in the runner namespace `amd-oneclick-ci-runners` and copied to `$RUNNER_TEMP` at run
time, never printed:
- `radeon-images-harbor` (`.dockerconfigjson`): Harbor robot `radeon-cloud-images-ci`, limited to the
  `radeon-cloud-global` project (pull/push, artifact read/create, tag create/delete). Expires 180 days from 2026-11-12.

No catalog credential is stored in the cluster (D-20261112-33).

## Runner
One in-cluster runner that serves only this repository (label `radeon-images`, namespace `amd-oneclick-ci-runners`,
service account `gh-runner`, so it has the CI slot lease and slot namespace permissions). It was registered once
with a one-time registration token; the cluster stores only the runner's own credentials, no PAT.

## Branch protection (`main`)
Merging is gated by CI (D-20261112-29): `pr-check` must pass `validate` (parses every image and workflow) and
`smoke` (changed images on a W7900D). No human approval is required; CODEOWNERS is for notification only.
No direct pushes, admins included; no force pushes or branch deletion.

## Status
First batch: PyTorch stable, PyTorch latest, vLLM. Second batch: Base, Unsloth, SGLang+hk-dsl (hk-B).
llama.cpp and ComfyUI later.
