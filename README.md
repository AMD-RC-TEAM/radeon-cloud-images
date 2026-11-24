Evidence for the PR "Use rocBLAS for torch matmuls on gfx1100 images" (2026-11-24). Not for merge.
logs/bench-{old,new}.log: previous vs new Base, GEMM/conv/launch-bound/HF Trainer. logs/blas-<image>.log: GEMM hipBLASLt vs rocBLAS per image.
logs/serve-<image>.log: Qwen3-8B serving with TORCH_BLAS_PREFER_HIPBLASLT unset vs 0. logs/floor-*.log: torch_gemm_floor runs. scripts/: what produced them.
