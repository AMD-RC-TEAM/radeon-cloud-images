"""Load images/strata-rdna3/models.yaml (a small YAML subset) and plan a strata launch."""
from __future__ import annotations

import hashlib, os, re, urllib.request
from pathlib import Path

MANIFEST = Path(os.environ.get("STRATA_MODELS_YAML", "/opt/rc-strata/models.yaml"))
MODELS_ROOT = Path(os.environ.get("STRATA_MODELS_ROOT", "/data/models"))


def _promote_lists(path: Path, lines: list[str], root: dict) -> dict:
    """Rebuild with knowledge of whether a key is followed by list items."""
    stack: list[tuple[int, object, str | None]] = [(-1, root := {}, None)]
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if stripped.startswith("- "):
            rest = stripped[2:]
            if not isinstance(parent, list):
                # convert the empty dict placeholder to a list
                holder_indent, _, key = stack[-1]
                grand = stack[-2][1]
                parent = []
                grand[key] = parent  # type: ignore[index]
                stack[-1] = (holder_indent, parent, key)
            if ":" in rest and not rest.startswith(("{", "[")):
                key, _, val = rest.partition(":")
                item: dict = {}
                v = val.strip()
                item[key.strip()] = _atom(v) if v else {}
                parent.append(item)  # type: ignore[union-attr]
                if not v:
                    stack.append((indent, item, None))
                else:
                    stack.append((indent, item, None))
            else:
                parent.append(_atom(rest))  # type: ignore[union-attr]
            continue
        key, _, val = stripped.partition(":")
        key, val = key.strip(), val.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"{path}: {key!r} not under a mapping ({raw})")
        if val == "":
            parent[key] = {}
            stack.append((indent, parent[key], key))
        else:
            parent[key] = _atom(val)
    return root


def _atom(raw: str):
    raw = raw.strip()
    if raw in ("", "~", "null"):
        return None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if (len(raw) >= 2) and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw.startswith("{") and raw.endswith("}"):
        out = {}
        body = raw[1:-1].strip()
        if body:
            for part in body.split(","):
                k, _, v = part.partition(":")
                out[k.strip()] = _atom(v)
        return out
    if raw.startswith("[") and raw.endswith("]"):
        body = raw[1:-1].strip()
        return [] if not body else [_atom(p) for p in body.split(",")]
    return raw


def load_manifest(path: Path | None = None) -> dict:
    path = path or MANIFEST
    data = _promote_lists(path, path.read_text(encoding="utf-8").splitlines(), {})
    if "models" not in data:
        raise SystemExit(f"{path} has no models:")
    return data


def hf_endpoint() -> str:
    return (os.environ.get("HF_ENDPOINT") or "").strip().rstrip("/") or "https://huggingface.co"


def file_url(entry: dict) -> str:
    return f"{hf_endpoint()}/{entry['repo']}/resolve/{entry['revision']}/{entry['path']}"


def dest_path(model_name: str, entry: dict, dest_dir: Path | None = None) -> Path:
    folder = dest_dir or (MODELS_ROOT / model_name)
    return folder / Path(entry["path"]).name


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stamp_path(path: Path) -> Path:
    return path.with_name(path.name + ".sha256")


def file_ok(path: Path, entry: dict) -> bool:
    if not path.is_file() or path.stat().st_size != int(entry["bytes"]):
        return False
    stamp = stamp_path(path)
    if stamp.is_file() and stamp.read_text().strip() == entry["sha256"]:
        return True
    digest = sha256_file(path)
    if digest != entry["sha256"]:
        return False
    stamp.write_text(digest + "\n")
    return True


def find_existing(entry: dict, root: Path) -> Path | None:
    want = entry["sha256"]
    name = Path(entry["path"]).name
    for p in root.rglob(name):
        if file_ok(p, entry):
            return p
        stamp = stamp_path(p)
        if p.is_file() and stamp.is_file() and stamp.read_text().strip() == want and p.stat().st_size == int(entry["bytes"]):
            return p
    return None


def ensure_files(model_name: str, spec: dict, dest_dir: Path | None = None, download: bool = True) -> Path:
    folder = dest_dir or Path(spec.get("dest") or (MODELS_ROOT / model_name))
    folder.mkdir(parents=True, exist_ok=True)
    for entry in spec["files"]:
        dest = dest_path(model_name, entry, folder)
        if file_ok(dest, entry):
            continue
        existing = find_existing(entry, MODELS_ROOT)
        if existing and existing.resolve() != dest.resolve():
            dest.unlink(missing_ok=True)
            try:
                os.link(existing, dest)
            except OSError:
                os.symlink(existing, dest)
            stamp_path(dest).write_text(entry["sha256"] + "\n")
            continue
        if not download:
            raise SystemExit(f"missing {dest} ({entry['bytes']} bytes); download is off")
        _download(file_url(entry), dest, int(entry["bytes"]))
        if not file_ok(dest, entry):
            dest.unlink(missing_ok=True)
            raise SystemExit(f"sha256 mismatch after download: {dest}")
    return folder


def _download(url: str, dest: Path, size: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    have = tmp.stat().st_size if tmp.is_file() else 0
    headers = {"User-Agent": "strata-rdna3-image"}
    if have:
        headers["Range"] = f"bytes={have}-"
    print(f"downloading {url} -> {dest} ({have}/{size} bytes)", flush=True)
    last_err = None
    for attempt in range(1, 6):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as r, tmp.open("ab" if have else "wb") as out:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
            last_err = None
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"download attempt {attempt} failed: {e}", flush=True)
            have = tmp.stat().st_size if tmp.is_file() else 0
            headers["Range"] = f"bytes={have}-"
    if last_err:
        raise SystemExit(f"could not download {url}: {last_err}")
    tmp.replace(dest)
    if dest.stat().st_size != size:
        raise SystemExit(f"{dest} is {dest.stat().st_size} bytes, expected {size}")


def launch_argv(name: str, spec: dict, extra: list[str], *, model_path: Path | None = None) -> list[str]:
    gfx = spec.get("gfx1100") or {}
    n = int((spec.get("needs") or {}).get("gpus") or 1)
    argv = ["launch", "--no-tui", "--access", "lan", "--port", os.environ.get("PORT", "8080"),
            "--family", spec["family"], "--model", spec["model"],
            "--data-dir", os.environ.get("STRATA_DATA_DIR", "/data/Strata-data")]
    if model_path:
        argv += ["--model-path", str(model_path)]
    if gfx.get("speed"):
        argv += ["--speed", str(gfx["speed"])]
    if gfx.get("vision"):
        argv += ["--vision", str(gfx["vision"])]
    if n:
        argv += ["--gpu", ",".join(str(i) for i in range(n))]
    for item in gfx.get("set") or []:
        argv += ["--set", str(item)]
    argv += extra
    return argv


def env_for(spec: dict) -> dict[str, str]:
    gfx = spec.get("gfx1100") or {}
    out = {"STRATA_FEED_MODELS": "0"}
    out.update({str(k): str(v) for k, v in (gfx.get("env") or {}).items()})
    return out
