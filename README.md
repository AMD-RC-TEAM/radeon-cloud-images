# radeon-cloud-images

The Dockerfiles behind the "stable" images in the Radeon Cloud image picker (PyTorch, vLLM, SGLang, ComfyUI and more).
A merged PR is built, smoke-tested on a Radeon W7900D GPU and released to users automatically.

## Add or change an image

1. **Change an image:** edit the files in `images/<name>/`. To update the base image, change the tag and
   `@sha256:` digest in the `FROM` line. For a pip package, change its pinned version.
2. **New image:** copy `docs/image-template/` to `images/<name>/` and fill in `Dockerfile`, `image.yaml` and
   `smoke.sh`. The template's comments say what goes where.
   You don't add SSH environment handling: `tools/release.py` appends one shared step (`tools/keep_image_env.sh`)
   to every image's build (so every image is built, even one that only mirrors an upstream image), and the smoke
   checks it for every image. A local `docker build` doesn't include that step.
3. Check it locally (below), then open a PR against `main`. In the description, say what changed and why, and link the
   upstream release notes for a version bump.
4. A bot also opens upgrade branches when an upstream image has a newer tag. Review those like any other PR.

## What each file does

| Path | Purpose |
|---|---|
| `images/<name>/Dockerfile` | The image: `FROM <public upstream image>:<tag>@sha256:<digest>`, then optional build steps. Use a public upstream image (exception today: `images/base` starts from a team-built image). |
| `images/<name>/image.yaml` | Release settings: image name, picker row name, smoke profile, and which upstream tags the upgrade bot may propose. |
| `images/<name>/smoke.sh` | Runs inside the image on one GPU and checks what users do with it. It must print `SMOKE PASS` as its last line. |
| `images/<name>/add_jupyterlab.sh` | (most images) Installs a pinned JupyterLab without changing any package already in the image, so notebooks start fast. |
| `images/<name>/add_openssh.sh` | (most images) Installs the SSH server so SSH access works without an install at launch. |
| other files in `images/<name>/` | Inputs to the build, such as `requirements.txt`. |
| `docs/image-template/` | Starting point for a new image. |
| `tools/` | Release scripts (`release.py`), shared smoke helpers (`smoke_lib.sh`), the upstream checker and catalog tools. |
| `help/` | The short help shown in a user's first terminal. It is built into the platform, not into the images. |
| `.github/` | CI workflows and `CODEOWNERS`. |

## Check it locally before the PR

You need Docker. The smoke test also needs an AMD GPU. Only gfx1100 (for example a W7900D) is smoke-tested.

```bash
# 1. Validate the image files (under 1 s). Pass = prints the parsed settings and exits 0.
python3 tools/release.py <name> --dry-run && test -x images/<name>/smoke.sh

# 2. Build (a few minutes to about an hour, depending on the build steps). Pass = the build finishes.
docker build --build-arg PIP_INDEX_URL=https://pypi.org/simple -t local/<name> images/<name>

# 3. Smoke test on the GPU (usually 5 to 30 min). Pass = the last line is "SMOKE PASS".
docker run --rm --device=/dev/kfd --device=/dev/dri --group-add video --shm-size 16g \
  -v "$PWD/images/<name>/smoke.sh:/smoke/smoke.sh:ro" \
  -v "$PWD/tools/smoke_lib.sh:/smoke/smoke_lib.sh:ro" \
  -v "$PWD/tools/hk_readme_smoke.sh:/smoke/hk_readme_smoke.sh:ro" \
  local/<name> bash /smoke/smoke.sh
```

If you have no GPU, run steps 1 and 2. The PR check runs the smoke test for you.

## Review

- CI on every PR: `validate` checks the image files and the tools, and `smoke` builds each changed image and runs its
  `smoke.sh` on a W7900D. Both must be green. A PR check takes about 10 min to 1 h per changed image.
- One approval from a code owner (@M4jupitercannon, see `.github/CODEOWNERS`) is required to merge. Nobody can
  approve their own PR. The reviewer checks the upstream release notes and that the smoke test still covers what
  users do.

## After merge

1. The release workflow builds each changed image again, or reuses the build that passed the PR check, and runs the
   smoke test again on a W7900D.
2. If it passes, the image is published as the new current version of that image. The previous version is kept
   for rollback.
3. The image picker is then updated. The test site goes first and launches one instance from the new image as a
   check. Only after that check passes do the production sites switch to it.
4. Users see the new version in the picker's stable row for that image, and a hidden "(previous)" row keeps the
   old one. Running instances keep the image they started with. Templates are never changed by a release.
5. If anything fails, nothing is published and the current version stays. The `rollback` workflow (Actions tab)
   switches an image back to its previous version.

## Build inputs from Harbor

An image's own build inputs come from its directory or from a pinned public upstream. One exception: a build artifact
that isn't public and doesn't belong in git (today: the Strata engine bundle for `strata-qwen38`) may come from a
one-file image in our Harbor, written as `COPY --from=rc-artifacts/<name>@sha256:…`. As with `FROM`, the Dockerfile names
no registry: `tools/release.py` points `rc-artifacts/` at Harbor when it builds, and refuses Dockerfiles that name it.
The Dockerfile says where the artifact came from and re-checks its sha256 during the build.
