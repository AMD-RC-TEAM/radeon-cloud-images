# One process: fp32/fp16/bf16 GEMM under hipBLASLt vs rocBLAS, interleaved round-robin; fp32 conv2d; correctness gate.
import torch, time, json, statistics as st
dev = "cuda"
def tflops(fn, flop, iters):
    for _ in range(3): fn()
    torch.cuda.synchronize(); t = time.perf_counter()
    for _ in range(iters): fn()
    torch.cuda.synchronize(); return flop * iters / (time.perf_counter() - t) / 1e12
BACK = {"hipblaslt": "cublaslt", "rocblas": "cublas"}
shapes = [(1024,1024,1024),(4096,4096,4096),(8192,8192,8192),(4096,11008,4096),(32,4096,4096)]
res = {"default_blas": str(torch.backends.cuda.preferred_blas_library()), "torch": torch.__version__, "gemm": {}, "conv": {}, "check": {}}
for dt in (torch.float32, torch.bfloat16):
    for (m,n,k) in shapes:
        a = torch.randn(m,k,device=dev,dtype=dt); b = torch.randn(k,n,device=dev,dtype=dt)
        outs = {}
        for name, lib in BACK.items():
            torch.backends.cuda.preferred_blas_library(lib); outs[name] = (a@b).float()
        ref = (a.double()@b.double())
        err = {kk: float(((v-ref).abs().max()/ref.abs().max())) for kk, v in outs.items()}
        res["check"][f"{dt}_{m}x{n}x{k}"] = err
        flop = 2*m*n*k; iters = max(3, min(200, int(2e12/flop)))
        samples = {kk: [] for kk in BACK}
        for r in range(5):
            for name, lib in (BACK.items() if r % 2 == 0 else reversed(list(BACK.items()))):
                torch.backends.cuda.preferred_blas_library(lib)
                samples[name].append(tflops(lambda: a@b, flop, iters))
        res["gemm"][f"{str(dt)[6:]}_{m}x{n}x{k}"] = {kk: round(st.median(v),2) for kk, v in samples.items()}
        print(str(dt)[6:], m, n, k, res["gemm"][f"{str(dt)[6:]}_{m}x{n}x{k}"], "relerr", {kk: f"{v:.1e}" for kk,v in err.items()}, flush=True)
print("BLAS_JSON", json.dumps(res))
