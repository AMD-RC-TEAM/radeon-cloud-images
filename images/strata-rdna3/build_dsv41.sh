#!/bin/sh
# Build strata-dsv41 for gfx1100 only (Kaniko: 16 CPU, 48Gi, 90 min, no GPU).
#   sh build_dsv41.sh <strata-src> <llama.cpp-src> <out-dir>
# COMMIT comes from the Dockerfile ARG STRATA_COMMIT (the v0.2.13 pin).
set -eu
SRC=$1
LLAMA=$2
OUT=$3
HP=${ROCM_PATH:-/opt/rocm}
export VARIANT=rx7900
export ARCHS=gfx1100
export STRATA_HIP_ARCHS=gfx1100
export SRC LLAMA HP CORE="$HP" LIBW="$HP"
export OUT PKGVER=0.1.59
export COMMIT=${COMMIT:?COMMIT=<strata source commit from ARG STRATA_COMMIT>}
export JOBS=${JOBS:-16}
export HIP_PLATFORM=amd HIP_COMPILER=clang HIP_RUNTIME=rocclr
export ROCM_PATH=$HP HIP_PATH=$HP
export PATH="$HP/bin:$HP/llvm/bin:${PATH:-/usr/bin}"
# The rocm/pytorch build stage already has the toolchain (same FROM as SGLang). Do not apt-get.
for b in cmake ninja g++ python3 patchelf; do
  command -v "$b" >/dev/null || { echo "missing $b; the rocm/pytorch image should already have it"; exit 1; }
done
mkdir -p "$OUT"
# The packaging script is bash (ARCHS//;/ ) and writes $OUT/*.log plus $OUT/build.status, not stdout.
bash "$SRC/packaging/build_dsv41_hip_linux.sh" || { cat "$OUT/build.status" 2>/dev/null; tail -n 80 "$OUT"/*.log 2>/dev/null; exit 1; }
exe=$(find "$OUT/components/dsv41" -type f -name strata-dsv41 | head -n1)
test -n "$exe" && test -x "$exe"
echo "built $exe"

# Compile-time gate (no GPU): the binary must start, and --pack-info must not report missing
# GPU kernels for the types this image's DeepSeek files use (IQ2_XS, IQ2_XXS, IQ4_NL, Q8_0).
# --pack-info needs a pack directory; a 1-layer stub is enough. CI smoke never runs dsv41 on GPU.
"$exe" --version
stub=$OUT/pack-stub
mkdir -p "$stub/w"
printf '%s\n' \
  "num_hidden_layers 1" \
  "n_routed_experts 1" \
  "num_experts_per_tok 1" \
  "hidden_size 8" \
  "moe_intermediate_size 8" \
  "vocab_size 8" \
  "model_dir $stub/w" \
  "format stub" > "$stub/ds4.txt"
printf '%s\n' \
  "file 0 stub.gguf" \
  "t layers.0.ffn.experts.0.w1.weight IQ2_XS 0 0 64" \
  "t layers.0.ffn.experts.0.w3.weight IQ2_XS 0 64 64" \
  "t layers.0.ffn.experts.0.w2.weight IQ2_XS 0 128 64" \
  "t embed.weight Q8_0 0 192 64" \
  "t layers.0.attn.engram.table IQ4_NL 0 256 64" \
  "t extra.iq2xxs IQ2_XXS 0 320 64" > "$stub/tensors.txt"
dd if=/dev/zero of="$stub/w/stub.gguf" bs=64 count=8 status=none
pi=$("$exe" --pack-info --pack "$stub")
printf '%s\n' "$pi"
printf '%s\n' "$pi" | grep -q 'no GPU kernel: none' \
  || { echo "FAIL: strata-dsv41 --pack-info reports missing GPU kernels"; exit 1; }
