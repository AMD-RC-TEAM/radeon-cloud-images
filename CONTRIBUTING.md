# Contributing an image change

Anyone on the team can upgrade an image or add a new one with a pull request. You never upload anything to
Harbor by hand: write the public upstream image in the Dockerfile, and the pipeline mirrors it, builds, smoke-tests
on a real W7900D and releases it.

## How it works
1. **Dockerfile `FROM` names the public upstream, pinned by digest**, for example
   `FROM docker.io/rocm/pytorch:rocm7.14.1_ubuntu24.04_py3.12_pytorch_release_2.12.0@sha256:cc9b00f9…`.
   Never write our Harbor address in a Dockerfile (`validate` rejects it).
2. **The pipeline mirrors that digest into Harbor on demand** (`tools/mirror.sh`, resumable, digest-checked) and
   builds and runs everything from the Harbor copy, so cluster nodes never pull from the internet. This happens
   in the PR check too, so a new upstream digest needs nothing done in advance. Docker Hub upstreams are mirrored
   automatically; for any other registry, ask rc-ops to copy the image first.
3. **The PR check** (`validate`, then `smoke`) builds the image (with Kaniko, if the Dockerfile has RUN/COPY steps)
   and runs `images/<name>/smoke.sh` on one W7900D. A red smoke blocks the merge.
4. **One Approve** from a code owner, then merge. Merging releases: `rc/<name>:rc-current` moves to the new digest,
   and the previous one stays as `rc-prev` (and as a hidden "(previous)" catalog row).
5. **To the picker** (rc-ops `catalog_sync`): the Global Test stable row adopts the new digest, and an automatic
   launch check starts one instance from it. Only when that passes do Global and China follow. In production, a
   +1h check rolls back automatically if launch failures get clearly worse. Templates are never changed by this.

## Example (a): bump a version
Upgrade vLLM · Stable to a newer upstream tag:
1. Find the tag and its digest on Docker Hub (or `docker buildx imagetools inspect docker.io/vllm/vllm-openai-rocm:<tag>`).
2. Change the one `FROM` line in `images/vllm/Dockerfile`:
   ```diff
   -FROM docker.io/vllm/vllm-openai-rocm:v0.33.0-rocm72@sha256:4fe7bc12…
   +FROM docker.io/vllm/vllm-openai-rocm:<new tag>@sha256:<new digest>
   ```
3. Open a PR and read the upstream release notes into the description. The PR check mirrors the new digest,
   builds, and runs the smoke (gfx1100, JupyterLab fast path, `vllm serve` on a 0.5B model, the hk-dsl README flow).
4. Get one Approve, then merge.

Bumping a pip package works the same way: change the pin (for example in `images/sglang/requirements.txt` or the
versions in `add_jupyterlab.sh`) and open a PR. The daily upgrade bot does example (a) for you when Docker Hub has
a newer tag matching `image.yaml`'s `tag_regex`: it pushes a branch with the same one-line FROM change and opens an
issue with a one-click "open PR" link.

## Example (b): add a new image
1. Copy `docs/image-template/` to `images/<name>/` and fill in:
   - `Dockerfile`: `FROM <public upstream>:<tag>@sha256:<digest>`, then your RUN/COPY steps if any. Declare
     `ARG PIP_INDEX_URL` before any pip install (the build passes a PyPI mirror reachable from the cluster). Keep
     `add_jupyterlab.sh` unless the upstream already ships JupyterLab 4.2–4.x with jupyter_server 2.14–2.x on
     Python 3.10–3.12; otherwise every launch installs it (slow).
   - `image.yaml`: `name`, `rc_repo: rc/<name>`, `catalog_row`, and `upstream.tag_regex` for the upgrade bot.
   - `smoke.sh`: must end with `SMOKE PASS`; start with `. "$(dirname "$0")/smoke_lib.sh"` and
     `jupyterlab_fast_path`, then test what the image is for (a GPU op, a server answering, a training step).
     Models download through `HF_ENDPOINT` (set by the smoke Job).
2. Open a PR. After merge, ask rc-ux to create the catalog stable row tracking `rc/<name>:rc-current`; from then on,
   the flow above applies.

## Who approves
`main` needs one Approve from a code owner (see README, "Branch protection and who approves") and green `validate`
and `smoke`. The approver checks the upstream release notes and that the smoke still tests what users do.
