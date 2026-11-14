#!/usr/bin/env python3
"""Print the key software versions of the image this runs in, as one line: RC-VERSIONS {"ROCm": "7.2.3", ...}.

Run inside an image by the release smoke (and by `release.py --probe`). Standard library only, no GPU needed: package
versions come from installed metadata, ROCm from /opt/rocm. catalog_sync turns the line into the picker description
("<purpose> · ROCm 7.2.3 · Python 3.12 · PyTorch 2.10.0 · vLLM 0.33.0"); the docs images page reads the same JSON.
"""
import glob, json, os, platform, re, subprocess, sys
from importlib import metadata

ORDER = ["ROCm", "Python", "PyTorch", "vLLM", "SGLang", "ComfyUI", "llama.cpp", "Unsloth"]


def pkg(*names):
    for n in names:
        try:
            return metadata.version(n).split("+")[0]
        except Exception:
            pass
    return None


def rocm():
    for f in ("/opt/rocm/.info/version", "/opt/rocm/.info/version-dev"):
        try:
            return open(f).read().strip().split("-")[0]
        except OSError:
            pass
    dirs = sorted(d for d in glob.glob("/opt/rocm-[0-9]*") if os.path.isdir(d))
    return dirs[-1].split("rocm-", 1)[1] if dirs else None


def comfyui():
    for d in ("/opt/ComfyUI", "/workspace/ComfyUI", os.path.expanduser("~/ComfyUI")):
        try:
            m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", open(os.path.join(d, "comfyui_version.py")).read())
            if m:
                return m.group(1)
        except OSError:
            pass
    return pkg("comfyui")


def llama_cpp():
    for exe in ("llama-server", "llama-cli"):
        try:
            out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            continue
        m = re.search(r"version:\s*(\d+)", out.stdout + out.stderr)
        if m:
            return f"b{m.group(1)}"
    return pkg("llama_cpp_python", "llama-cpp-python")


def main():
    v = {"ROCm": rocm(), "Python": ".".join(platform.python_version_tuple()[:2]),
         "PyTorch": pkg("torch"), "vLLM": pkg("vllm"), "SGLang": pkg("sglang"), "ComfyUI": comfyui(),
         "llama.cpp": llama_cpp(), "Unsloth": pkg("unsloth")}
    print("RC-VERSIONS " + json.dumps({k: v[k] for k in ORDER if v.get(k)}, separators=(",", ":")))


if __name__ == "__main__":
    sys.exit(main())
