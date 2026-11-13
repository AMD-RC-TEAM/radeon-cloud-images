# radeon-cloud-images

The single source for the images behind the "stable" rows of the Radeon Cloud image picker
(owner decisions D-20261112-26, -27, -28, -29, -33, -37, -39). Every image is defined by a Dockerfile. The standard flow (D-20261112-37):
**a PR (from the bot or a person) → one human Approve → build and smoke → release**.

Everything in this repository is written in English: docs, comments, script output, workflow
names, issues, PRs and commit messages.

**To upgrade an image or add one, see [CONTRIBUTING.md](CONTRIBUTING.md).**

## Layout
```
images/<name>/
  Dockerfile   # FROM <public upstream>:<tag>@sha256:... (never our Harbor); the pipeline mirrors it and builds from Harbor
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
  upstream-check.yml # daily: if upstream has a newer tag, push an upgrade branch (the FROM line) and open an issue with a one-click PR link
  rollback.yml       # manual one-click rollback
```

## Release flow
1. **PR and Approve.** Every change to `main` needs one Approve from a code owner, plus green `validate` and `smoke`.
   The Approve is the only human gate; there is no extra waiting period or second approval.
2. **Mirror.** If Harbor does not have the upstream digest yet, mirror it to `radeon-cloud-global/<upstream repo>:<tag>`
   with the digest unchanged. Cluster nodes never pull large images from the internet.
3. **Smoke.** Claim a CI slot with `tools/ci/slot_pool.py`, run a 1-GPU Job in the slot namespace
   (nodes labelled `amd-oneclick.io/workload-ci=enabled`) that runs `smoke.sh`. No `SMOKE PASS` means failure.
   The slot is released only once the Job is confirmed gone; otherwise it is quarantined.
4. **Alias.** Copy the digest server-side into `radeon-cloud-global/rc/<category>`, move the old `rc-current`
   to `rc-prev`, and point `rc-current` at the new digest. CI stops here.
5. **Catalog (outside CI, rc-ops job).** GT first: the stable row adopts the new digest, then an automatic launch
   check starts one minimal instance from that row on GT and deletes it once it is ready. Only after that check
   passes do the Global and China stable rows adopt the same digest. If the check fails, production keeps the
   previous digest and the daily issue says why.
6. **Failure anywhere:** nothing further moves; one line in the day's "image pipeline daily" issue.

## JupyterLab in every stable image
Radeon Cloud's launch step checks the image for `jupyter` on PATH, Python 3.10-3.12, `jupyter_server` >=2.14,<3 and
`jupyterlab` >=4.2,<5. If they are missing, it pip-installs JupyterLab on every launch (measured 18-188 s, 11-13).
So every image here carries a pinned JupyterLab. Images that do not already include one get it from
`add_jupyterlab.sh`, which pins everything already installed as a constraint (nothing existing may change). Their
digests are therefore our own builds on top of the mirrored upstream image, not the upstream digest itself. Each
smoke checks the fast path and that the Jupyter layer changed no existing package (`tools/smoke_lib.sh`).

## Templates
**Point templates at a fixed-version image row, not at a stable row.** Stable rows move with this pipeline.
Updating a template's image is done by the template's owner, by hand in Admin, and tested by them (D-20261112-39).
The pipeline never changes a row that any template (public or private) references, and the daily issue names
every template that points at a stable row so its owner can move it to a fixed-version row.

## Old images stay usable
- **Templates are pinned.** Templates reference catalog rows that hold a fixed digest. The pipeline only ever
  updates the per-category *stable* rows, and refuses to adopt on any row that a template references.
- **One previous version stays available.** On every release the old digest is kept in Harbor as `rc-prev`, and
  each site keeps one hidden catalog row "<category> (previous)" tracking `rc/<category>:rc-prev`, for users or
  templates that need the older environment and as the one-click rollback target. Only the latest previous
  version is kept. The same rule applies to it: if a template references the "(previous)" row, the pipeline
  stops moving that row (it becomes a frozen row like any other template-referenced row) and says so in the
  daily issue.
  This should be rare: the new UI has no personal templates, so once the old UI is retired only public
  templates exist, and those are pointed at fixed-version rows by their owners.
- **Running instances are not affected.** A release changes which digest new launches use. Instances that are
  already running keep the image they started with until they are deleted.

## Rollback
Actions -> rollback -> image: `rc-current` goes back to `rc-prev`; the catalog job then adopts it on every site.
The digest that was rolled back stays tagged `rc-rolled-back`.

## Adding or upgrading an image
- **Upgrade:** change the `FROM` line's tag@digest (the daily bot prepares this branch for you), read the upstream
  release notes, merge. See CONTRIBUTING.md.
- **New image:** add `images/<name>/` with the three files, after rc-ux has created a stable row in Admin that
  tracks `rc/<category>:rc-current`.
- **Images with build steps** (RUN/COPY, for example `sglang`) are built with Kaniko in the runner namespace, with
  no GPU, into `build/<name>:ctx-<hash of the build context>`. Files other than `image.yaml` and `smoke.sh` are the
  context. A context that was already built (by the PR check) is reused on release, so the release ships exactly the
  digest that passed the smoke. pip uses a PyPI mirror reachable from the cluster (passed as the `PIP_INDEX_URL`
  build argument; declare `ARG PIP_INDEX_URL` in the Dockerfile); smoke Jobs get `HF_ENDPOINT` pointing at a
  Hugging Face mirror.

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

## Branch protection and who approves (`main`)
`main` requires one Approve from a code owner (the owner or Zijun) and green `validate` and `smoke`; no direct
pushes, admins included; no force pushes or branch deletion. GitHub does not let anyone approve their own PR, so:
- **Today (no bot App):** the upgrade bot pushes a branch and opens an issue with a one-click "open PR" link. The
  owner opens the PR from that link, so the owner is the PR author, and **Zijun approves**. A PR opened by Zijun is
  approved by the owner.
- **Later, if the GitHub App is created** (manifest kept by rc-ops): the bot itself opens the PR, so the PR author is
  the bot and **the owner can approve** directly.

## Status
First batch: PyTorch stable, PyTorch latest, vLLM. Second batch: SGLang (built, without hk-dsl while hk-dsl is paused), Base, Unsloth.
llama.cpp and ComfyUI later.
