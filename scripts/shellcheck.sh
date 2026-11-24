P='import os,time,torch; n=4096; a=torch.randn(n,n,device="cuda"); b=torch.randn(n,n,device="cuda"); a@b; torch.cuda.synchronize(); t=time.perf_counter()
for _ in range(20): a@b
torch.cuda.synchronize(); print("env=%s blas=%s fp32_4096=%.1f TFLOPS" % (os.environ.get("TORCH_BLAS_PREFER_HIPBLASLT"), torch.backends.cuda.preferred_blas_library(), 2*n**3*20/(time.perf_counter()-t)/1e12))'
printf '%s\n' "$P" > /tmp/probe.py
echo "login shell, clean env:";       env -i HOME=/root PATH=/usr/bin:/bin TERM=dumb bash -l -c 'command -v python3; python3 /tmp/probe.py' 2>&1 | grep -v Warning | tail -2
echo "interactive shell, clean env:"; env -i HOME=/root PATH=/usr/bin:/bin TERM=dumb bash -i -c 'command -v python3; python3 /tmp/probe.py' 2>&1 | grep -v -E "Warning|no job control|cannot set terminal" | tail -2
echo "user export wins in login shell:"; env -i HOME=/root PATH=/usr/bin:/bin TORCH_BLAS_PREFER_HIPBLASLT=1 bash -l -c 'python3 /tmp/probe.py' 2>&1 | grep -v Warning | tail -1
rm -f /tmp/probe.py
