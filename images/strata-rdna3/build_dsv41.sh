#!/bin/sh
# Build strata-dsv41 for gfx1100 only (Kaniko: 16 CPU, 48Gi, 90 min, no GPU).
#   sh build_dsv41.sh <strata-src> <llama.cpp-src> <out-dir>
set -eu
SRC=$1
LLAMA=$2
OUT=$3
HP=${ROCM_PATH:-/opt/rocm}
export VARIANT=rx7900 ARCHS=gfx1100
export SRC LLAMA HP CORE="$HP" LIBW="$HP"
export OUT PKGVER=0.1.59
export COMMIT=d2f096475817d4666c364c820b0ca830f751cfc5
export JOBS=${JOBS:-16}
export HIP_PLATFORM=amd HIP_COMPILER=clang HIP_RUNTIME=rocclr
export ROCM_PATH=$HP HIP_PATH=$HP
export PATH="$HP/bin:$HP/llvm/bin:${PATH:-/usr/bin}"
apt-get update
apt-get install -y --no-install-recommends cmake ninja-build patchelf g++ binutils python3
rm -rf /var/lib/apt/lists/*
mkdir -p "$OUT"
# The packaging script cd's to SRC and writes $OUT/components/dsv41/<ver>-linux-x86_64-hip-rx7900/
sh "$SRC/packaging/build_dsv41_hip_linux.sh"
exe=$(find "$OUT/components/dsv41" -type f -name strata-dsv41 | head -n1)
test -n "$exe" && test -x "$exe"
echo "built $exe"
