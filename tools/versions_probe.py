#!/usr/bin/env python3
"""Print the key software versions of the image this runs in, as one line: RC-VERSIONS {"ROCm": "7.2.3", ...}.

Run inside an image by the release smoke (and by `release.py --probe`). Standard library only, no GPU needed: package
versions come from installed metadata, ROCm from /opt/rocm. catalog_sync turns the line into the picker description
("<purpose> · ROCm 7.2.3 · Python 3.12 · PyTorch 2.10.0 · vLLM 0.33.0"); the docs images page reads the same JSON.
"""
import glob, json, os, platform, re, subprocess, sys
from importlib import metadata

ORDER = ["ROCm", "Python", "PyTorch", "vLLM", "SGLang", "ComfyUI", "llama.cpp", "Ollama", "Unsloth"]


# Tools installed outside the default interpreter (uv tool install unsloth, a venv under /opt).
OTHER_SITES = ["/root/.unsloth/studio/*/lib/python3*/site-packages", "/root/.local/share/uv/tools/*/lib/python3*/site-packages", "/home/*/.local/share/uv/tools/*/lib/python3*/site-packages",
               "/opt/*/lib/python3*/site-packages"]


def pkg(*names):
    for n in names:
        try:
            return metadata.version(n).split("+")[0]
        except Exception:
            pass
    for n in names:
        for site in OTHER_SITES:
            for d in sorted(glob.glob(os.path.join(site, n.replace("-", "_") + "-*.dist-info"))):
                m = re.search(r"-([0-9][^-]*)\.dist-info$", d)
                if m:
                    return m.group(1).split("+")[0]
    return None


def rocm():
    for f in ("/opt/rocm/.info/version", "/opt/rocm/.info/version-dev"):
        try:
            return open(f).read().strip().split("-")[0]
        except OSError:
            pass
    dirs = sorted(d for d in glob.glob("/opt/rocm-[0-9]*") if os.path.isdir(d))
    if dirs:
        return dirs[-1].split("rocm-", 1)[1]
    # ROCm installed as Python wheels (TheRock / rocm-sdk, e.g. vLLM on ROCm 10) has no /opt/rocm/.info: use the
    # ROCm version PyTorch was built for ("2.13.0+rocm10.0.0" -> "10.0.0"), or the rocm-sdk package version.
    try:
        m = re.search(r"\+rocm(\d+(?:\.\d+)*)", metadata.version("torch"))
        if m:
            return m.group(1)
    except Exception:
        pass
    return pkg("rocm-sdk-core", "rocm")


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


def ollama_version():
    # `ollama -v` prints "ollama version is 0.40.18" (plus a warning when no server is running); the first match wins.
    try:
        out = subprocess.run(["ollama", "-v"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"version(?: is)?\s*v?(\d+(?:\.\d+)+)", out.stdout + out.stderr)
    return m.group(1) if m else None


def main():
    v = {"ROCm": rocm(), "Python": ".".join(platform.python_version_tuple()[:2]),
         "PyTorch": pkg("torch"), "vLLM": pkg("vllm"), "SGLang": pkg("sglang"), "ComfyUI": comfyui(),
         "llama.cpp": llama_cpp(), "Ollama": ollama_version(), "Unsloth": pkg("unsloth")}
    print("RC-VERSIONS " + json.dumps({k: v[k] for k in ORDER if v.get(k)}, separators=(",", ":")))


if __name__ == "__main__":
    sys.exit(main())
