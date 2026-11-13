"""RDNA3 serving default for vLLM in this image: ROCM_SEGMENTED_ATTN attention on gfx11 (Radeon PRO W7900 / W7900D).

Loaded at interpreter start by rc_vllm_defaults.pth. When `vllm.platforms.rocm` is imported, it wraps
RocmPlatform.get_attn_backend_cls. The change applies only when no backend was chosen (`--attention-backend` or
attention_config not set), the GPU is gfx11, and vLLM's own pick is the generic TRITON_ATTN or ROCM_ATTN for a
plain decoder layer (head size 64/128/256, fp16/bf16 KV cache, no MLA, sparse or sink attention). It also only
applies if vLLM accepts ROCM_SEGMENTED_ATTN for that layer; otherwise vLLM's own pick stands.

Why: on vLLM 0.33.0 / gfx1100, Qwen3-8B time-to-first-token at 32k context was TRITON_ATTN 26.7 s, ROCM_ATTN 18.4 s,
ROCM_SEGMENTED_ATTN 13.0 s, and accuracy on a 35B model was unchanged (McNemar p=0.63).

An explicit `--attention-backend` always wins. Set RC_VLLM_DEFAULTS=0 to disable this module entirely.
This file is identical in images/vllm and images/vllm-latest.
"""
import importlib.abc
import importlib.machinery
import os
import sys

TARGET = "vllm.platforms.rocm"
GENERIC = ("TRITON_ATTN", "ROCM_ATTN")
PREFERRED = "ROCM_SEGMENTED_ATTN"


def _plain_decoder(cfg):
    attn_type = getattr(cfg, "attn_type", "decoder")
    if getattr(attn_type, "value", attn_type) != "decoder":
        return False
    if getattr(cfg, "head_size", None) not in (64, 128, 256):
        return False
    if str(getattr(cfg, "kv_cache_dtype", None) or "auto") not in ("auto", "float16", "bfloat16"):
        return False
    return not any(getattr(cfg, f, False) for f in ("use_mla", "use_sparse", "has_sink"))


def _patch(module):
    cls = getattr(module, "RocmPlatform", None)
    if cls is None or getattr(cls, "_rc_rdna3_defaults", False):
        return
    original = cls.get_attn_backend_cls.__func__

    def get_attn_backend_cls(klass, selected_backend, attn_selector_config, num_heads=None):
        path = original(klass, selected_backend, attn_selector_config, num_heads)
        if selected_backend is not None:
            return path
        try:
            from vllm.v1.attention.backends.registry import AttentionBackendEnum as E
            if not (module.on_gfx1x() and not module.on_gfx12x()):
                return path
            if path not in [E[n].get_path() for n in GENERIC] or not _plain_decoder(attn_selector_config):
                return path
            return original(klass, E[PREFERRED], attn_selector_config, num_heads)
        except Exception:  # noqa: BLE001 -- any doubt keeps vLLM's own choice
            return path

    cls.get_attn_backend_cls = classmethod(get_attn_backend_cls)
    cls._rc_rdna3_defaults = True


class _Loader(importlib.abc.Loader):
    def __init__(self, inner):
        self.inner = inner

    def create_module(self, spec):
        return self.inner.create_module(spec)

    def exec_module(self, module):
        self.inner.exec_module(module)
        try:
            _patch(module)
        except Exception:  # noqa: BLE001 -- never break `import vllm`; the smoke checks the default took effect
            pass


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != TARGET:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is not None and spec.loader is not None:
            spec.loader = _Loader(spec.loader)
        return spec


def install():
    if os.environ.get("RC_VLLM_DEFAULTS") == "0":
        return
    if TARGET in sys.modules:
        _patch(sys.modules[TARGET])
    elif not any(isinstance(f, _Finder) for f in sys.meta_path):
        sys.meta_path.insert(0, _Finder())
