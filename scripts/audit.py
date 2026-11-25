# Per-image perf-default audit: CPU threads vs the container's CPU limit, CPU matmul speed, MIOpen first-call cost, env.
import os, sys, time, json, subprocess
def cgroup_cpus():
    try:
        q, p = open("/sys/fs/cgroup/cpu.max").read().split()
        return None if q == "max" else int(q) / int(p)
    except Exception:
        return None
res = {"cpu_count": os.cpu_count(), "affinity": len(os.sched_getaffinity(0)), "cgroup_cpus": cgroup_cpus(),
       "env": {k: v for k, v in os.environ.items() if k.split("_")[0] in ("OMP", "MKL", "OPENBLAS", "MIOPEN", "PYTORCH", "TORCH", "HIP", "HSA", "TOKENIZERS", "TRITON", "HF") and "TOKEN" not in k[3:]}}
import torch, numpy as np
res["torch"] = torch.__version__; res["torch_threads"] = torch.get_num_threads(); res["interop_threads"] = torch.get_num_interop_threads()
def cpu_mm(threads=None):
    if threads: torch.set_num_threads(threads)
    a = torch.randn(2048, 2048); a @ a; t = time.perf_counter()
    for _ in range(10): a @ a
    return round(10 * 2 * 2048**3 / (time.perf_counter() - t) / 1e9, 1)
lim = int(res["cgroup_cpus"] or res["affinity"])
res["cpu_mm_gflops"] = {"default_%d" % res["torch_threads"]: cpu_mm(), "limit_%d" % lim: cpu_mm(lim)}
torch.set_num_threads(res["torch_threads"])
# numpy BLAS: fresh processes, default vs OMP_NUM_THREADS=<limit>
NP = "import numpy as np,time;a=np.random.rand(2048,2048);a@a;t=time.perf_counter()\nfor _ in range(10): a@a\nprint(round(10*2*2048**3/(time.perf_counter()-t)/1e9,1))"
res["numpy_mm_gflops"] = {}
for label, extra in (("default", {}), ("omp_%d" % lim, {"OMP_NUM_THREADS": str(lim), "OPENBLAS_NUM_THREADS": str(lim), "MKL_NUM_THREADS": str(lim)})):
    out = subprocess.run([sys.executable, "-c", NP], env={**os.environ, **extra}, capture_output=True, text=True, timeout=600).stdout.strip()
    res["numpy_mm_gflops"][label] = out
# MIOpen: first vs steady conv fwd+bwd (find/compile cost paid per new instance when the user DB is empty)
x = torch.randn(32, 64, 56, 56, device="cuda", requires_grad=True); conv = torch.nn.Conv2d(64, 128, 3, padding=1).cuda()
def step(): y = conv(x); y.sum().backward(); torch.cuda.synchronize()
t = time.perf_counter(); step(); first = time.perf_counter() - t
t = time.perf_counter(); [step() for _ in range(5)]; steady = (time.perf_counter() - t) / 5
res["miopen_conv_ms"] = {"first": round(first * 1000), "steady": round(steady * 1000, 1)}
res["miopen_user_db"] = [p for p in (os.path.expanduser("~/.config/miopen"), os.path.expanduser("~/.cache/miopen")) if os.path.isdir(p)]
print("AUDIT_JSON", json.dumps(res))
