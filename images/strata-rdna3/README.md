# Strata · RDNA3 on Radeon PRO W7900 / W7900D (gfx1100)

One image: Strata v0.2.13 (upstream `ghcr.io/niko1221/strata:0.2.13-rocm-gfx110x`, pinned by digest) with a gfx1100
DeepSeek engine (`strata-dsv41`) built in, JupyterLab, and one command per model. Weights are **not** in the image.
This image has not been built or run as an image yet; the DeepSeek numbers below come from runs outside an image on
4× W7900D.

**DeepSeek is frozen at v0.2.13.** Upstream dropped DeepSeek from 0.2.14 (no engine built or signed; 0.2.13 is the last
version that ran it). Niko1221/Strata#5829 will likely never merge. The DeepSeek engine in this image is a permanent
fork pinned to v0.2.13 (`d2f096475817d4666c364c820b0ca830f751cfc5`). No in-tree `pr-5829.patch`: on v0.2.13 a
`STRATA_DSV41_EXE` build already passes BUILD.json `archs` as `covered`, and a gfx1100-only package keeps the Linux
picker on gfx1100 (`_is_rdna4` does not see gfx1100, so it does not default to 5 experts). Qwen can move later after
measuring: 0.2.14 HIP is about 40% slower on cold prefill on gfx1100 (#6067, `STRATA_MMQ=OFF`). Do not split this into
two images.

Build: `STRATA_HIP_ARCHS=gfx1100`, `VARIANT=rx7900`, `COMMIT` from Dockerfile `ARG STRATA_COMMIT`. The DeepSeek build
stage fails unless `strata-dsv41 --version` and `strata-dsv41 --pack-info` succeed with no missing GPU kernels.

Start a server with one command; gfx1100 flags are already in the image. Radeon Cloud starts the instance with JupyterLab
(`jupyter` is on PATH). In that terminal:

```bash
strata-serve --model qwen3.6-35b-a3b-q4
```

Docker (same image; extra args replace the upstream `run` CMD):

```bash
docker run --device /dev/kfd --device /dev/dri -v <data>:/data -p 8080:8080 <image> strata-serve --model qwen3.6-35b-a3b-q4
```

- `strata-serve --list` lists the presets. `strata-serve --plan --model <name>` prints the download and an approximate
  `entrypoint.sh run` (env). It is not a `strata launch` line: the upstream entrypoint hard-codes
  `--data-dir /data/Strata-data`, so `STRATA_DATA_DIR` is ignored, and it adds `--preset docker`.
- The first start downloads the pinned files to `$STRATA_MODELS_ROOT/<name>` (default `/data/Strata-data/rc-models`,
  through `HF_ENDPOINT` if set) and checks every sha256. That folder is outside the names the upstream entrypoint
  migrates (`models`, `packs`, `mtp`). Later starts reuse files whose size and hash still match. Downloads resume;
  a connection that delivered bytes does not count toward the give-up limit (Wuxi cuts ~10 min connections).
- DeepSeek defaults to `--speed full` (`--experts 6`). Extra flags after `--model` override the preset, the way
  `vllm serve` takes extra flags: `strata-serve --model deepseek-v4.1-flash-2.25 --speed faster`.
- `--set prefill-chunk=1024` is a separate measured optimization (4× W7900D, ISTA-DAS 2.25, 8K: prompt 365.15 →
  744.63 tok/s, greedy ids unchanged). It is not part of the 5-expert speedup.
- Named `*-fast` presets use `--speed faster` (5 experts) until a quality check exists.
- The server listens on port 8080 with OpenAI- and Anthropic-compatible APIs, plus `GET /health`.
- On a Radeon Cloud instance, run `strata-serve` in a terminal, then `rc-tunnel expose --port 8080` to reach the API
  from outside.
- A new model, patch, or gfx1100 preset ships as a **new image tag**. Update the image; the command stays
  `strata-serve --model <name>`.

## Weights, disk, and China

A 257–274 GB first-start download will not fit a normal instance disk. Set `HF_ENDPOINT` to a mirror if
huggingface.co is not reachable (required in China). After that first download, drop the page cache or expect
0.2.13 paged-memory queue stalls.

4-GPU DeepSeek is not the default picker experience (no picker row until smoke plus owner decision D-20261112-26).

| `--model` | GPUs | Disk | Notes |
| --- | --- | --- | --- |
| `deepseek-v4.1-flash-2.25` | 4 | 274 GB | Default `--speed full` (`--experts 6`) and `--set prefill-chunk=1024`; `HSA_USERPTR_FOR_PAGED_MEM=0`, `GPU_PINNED_MIN_XFER_SIZE=1048576`, `HSA_DISABLE_COREDUMP_ON_EXCEPTION=1`, `DS4_FAST_ATTN=1`. Expert shards are **IQ2_XS** (not IQ4_XS); Engram is IQ4_NL. Measured 2026-11-13 outside an image. |
| `deepseek-v4.1-flash-2.25-fast` | 4 | 274 GB | Same files as 2.25. `--speed faster` (5 experts) until a quality check exists. Same prefill-chunk. |
| `deepseek-v4.1-flash-2.00` | 4 | 257 GB | Same gfx1100 default as 2.25. Expert shards are IQ2_XXS. Shares Engram / DSpark / Unsloth metadata with 2.25. Measured 2026-11-11 outside an image. |
| `deepseek-v4.1-flash-2.00-fast` | 4 | 257 GB | Same files as 2.00. `--speed faster` (5 experts). |
| `qwen3.8-flash-next-iq3_s` | 2 | 83.6 GB | Ran on 2× W7900D before; not re-checked in this image. Manual 2-GPU smoke is not attached. |
| `qwen3.6-35b-a3b-q4` | 1 | 22.9 GB | CI smoke serve + completion on 1× W7900D, resumable via `/hf-cache/strata-models`. |

DeepSeek file pins and the Qwen pins are copied from Strata v0.2.13 `setup.py`. `check_manifest.py` compares
them at build. Feed model updates are off (`STRATA_FEED_MODELS=0`).

## IQ4_XS

#5829 reports `ds4_iq_test` IQ4_XS wmma vs scalar outside tolerance. The 2.25 files in `models.yaml` / v0.2.13
`setup.py` are named `DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XS-*.gguf` (and Engram `…-IQ4_NL.gguf`), not IQ4_XS.
2.00 is IQ2_XXS. The IQ4_XS wmma issue was checked against these filenames; 2.25 is IQ2_XS. 2.25 is a preset, not
the headline, until that is written (this paragraph). No hashes were invented.

## Environment (ROCm 7.2.4)

- `HSA_USERPTR_FOR_PAGED_MEM=0`
- `GPU_PINNED_MIN_XFER_SIZE=1048576`
- `HSA_DISABLE_COREDUMP_ON_EXCEPTION=1`; `strata-serve` also runs `ulimit -c 0`
- With ROCm ≥ 10.2 also set `HSA_SVM_FOR_PAGED_MEM=0`. This image is 7.2.4, so that variable is not set.
- `STRATA_MODELS_ROOT` (default `/data/Strata-data/rc-models`) is where weights land. Do not use `/data/models`:
  the upstream entrypoint moves that name into `/data/Strata-data/models`.
- `STRATA_DATA_DIR` is not honoured by the upstream entrypoint (`--data-dir /data/Strata-data` is hard-coded).

## Smoke

CI (1× W7900D, 48Gi, 1h) checks JupyterLab, gfx1100 `rocminfo`, `strata-serve --list`, `--plan` for every preset
including the `*-fast` names, then a mandatory serve and completion of `qwen3.6-35b-a3b-q4` with
`STRATA_MODELS_ROOT=/hf-cache/strata-models`. Health answering is not enough: the server must return a completion.
The 22.9 GB file downloads once, resumably, and later runs reuse it.

Manual 2-GPU (`qwen3.8-flash-next-iq3_s`) and 4-GPU (DeepSeek 2.25 / 2.00) smokes on W7900D are **not attached**.
This README does not claim they ran.

## How this was checked

- Patch dropped: `patch -p1 --dry-run` against a clean `git archive` of v0.2.13 `d2f096475` failed
  (`packaging/build_dsv41_hip_linux.sh` 2/2 hunks, `strata_control/dsv41_fit.py` 2/3 hunks). Reason: a gfx1100-only
  package is enough; `setup.py` `dsv41_covered_archs` already passes BUILD.json `archs` as `covered` for
  `STRATA_DSV41_EXE`, and `_is_rdna4` does not treat gfx1100 as RDNA4. The `dsv41_fit.py` copy was dropped with the patch.
- `python3 tools/release.py strata-rdna3 --dry-run`: both FROM lines rewritten to Harbor (dsv41-build docker.io and
  ghcr runtime). `ensure_mirror` still errors on ghcr at a real smoke until rc-ops copies the digest.
- `bash -n images/strata-rdna3/smoke.sh`
- `python3 -m py_compile` on the changed Python files
- `python3 -m unittest tests.test_release_from`
- No GPU occupied for this change. Manual 2-GPU / 4-GPU smokes were not run.
