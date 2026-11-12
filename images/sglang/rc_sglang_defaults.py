"""RDNA3 serving defaults for SGLang in this image, so a plain `python -m sglang.launch_server --model-path X` or
`sglang serve --model-path X` works on Radeon PRO W7900 / W7900D (gfx1100) without extra flags.

Loaded at interpreter start by rc_sglang_defaults.pth. When `sglang.srt.server_args` is imported, it changes two
defaults only (an explicit command-line value always wins):
  - attention backend: SGLang's ROCm default is aiter, which is CDNA-only (decode fails on gfx1100). Default to
    triton, the backend the RDNA3 plugin validates (sglang-rdna3 serve-args).
  - CUDA/HIP graphs: capture hangs on gfx1100 (sgl-project/sglang#30245), so they are off by default. Throughput
    is therefore not tuned. Set RC_SGLANG_CUDA_GRAPH=1 to leave SGLang's own setting alone.
Set RC_SGLANG_DEFAULTS=0 to disable this module entirely.
"""
import importlib.abc
import importlib.machinery
import os
import sys

TARGET = "sglang.srt.server_args"


def _patch(module):
    cls = getattr(module, "ServerArgs", None)
    if cls is None or getattr(cls, "_rc_rdna3_defaults", False):
        return
    original_default = cls._get_default_attn_backend
    original_post_init = cls.__post_init__

    def _get_default_attn_backend(self, use_mla_backend, model_config):
        backend = original_default(self, use_mla_backend, model_config)
        return "triton" if backend == "aiter" else backend

    def __post_init__(self):
        if os.environ.get("RC_SGLANG_CUDA_GRAPH") != "1":
            self.disable_cuda_graph = True
        return original_post_init(self)

    cls._get_default_attn_backend = _get_default_attn_backend
    cls.__post_init__ = __post_init__
    cls._rc_rdna3_defaults = True


class _Loader(importlib.abc.Loader):
    def __init__(self, inner):
        self.inner = inner

    def create_module(self, spec):
        return self.inner.create_module(spec)

    def exec_module(self, module):
        self.inner.exec_module(module)
        _patch(module)


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != TARGET:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is not None and spec.loader is not None:
            spec.loader = _Loader(spec.loader)
        return spec


def install():
    if os.environ.get("RC_SGLANG_DEFAULTS") == "0":
        return
    if TARGET in sys.modules:
        _patch(sys.modules[TARGET])
    elif not any(isinstance(f, _Finder) for f in sys.meta_path):
        sys.meta_path.insert(0, _Finder())
