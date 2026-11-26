#!/usr/bin/env python3
"""Fail if models.yaml file pins do not match Strata setup.py REPO_PINS / HF_REVISIONS."""
from __future__ import annotations

import ast, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, "/opt/rc-strata")
sys.path.insert(0, str(HERE))
import rc_strata  # noqa: E402


def parse_setup_pins(setup_py: pathlib.Path) -> tuple[dict, dict]:
    """Read HF_REVISIONS and the (bytes, sha256) tuples in REPO_PINS tables without importing setup.py."""
    src = setup_py.read_text(encoding="utf-8")
    tree = ast.parse(src)
    revisions: dict[str, str] = {}
    pins: dict[tuple[str, str], tuple[int, str]] = {}

    def const_str(node):
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

    # HF_REVISIONS = { "repo": "sha", ... }
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "HF_REVISIONS" for t in node.targets):
            if isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    ks, vs = const_str(k), const_str(v)
                    if ks and vs:
                        revisions[ks] = vs

    # Tables of "filename": (bytes, "sha256") assigned to *FILES names, then REPO_PINS maps repo -> table.
    tables: dict[str, dict[str, tuple[int, str]]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not names or not isinstance(node.value, ast.Dict):
            continue
        table = {}
        for k, v in zip(node.value.keys, node.value.values):
            ks = const_str(k)
            if ks is None or not isinstance(v, ast.Tuple) or len(v.elts) != 2:
                continue
            b, h = v.elts
            if isinstance(b, ast.Constant) and isinstance(b.value, int) and const_str(h):
                table[ks] = (b.value, const_str(h))
        if table:
            for n in names:
                tables[n] = table

    # REPO_PINS = { "repo": NAME, ... }  NAME is a Name pointing at a *FILES table
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "REPO_PINS" for t in node.targets):
            if not isinstance(node.value, ast.Dict):
                continue
            for k, v in zip(node.value.keys, node.value.values):
                repo = const_str(k)
                if not repo:
                    continue
                items = {}
                if isinstance(v, ast.Name) and v.id in tables:
                    items = tables[v.id]
                elif isinstance(v, ast.Dict):
                    # inline (not used in v0.2.13) 
                    pass
                for fname, pin in items.items():
                    pins[(repo, fname)] = pin
    if not revisions or not pins:
        raise SystemExit(f"{setup_py}: could not parse HF_REVISIONS / REPO_PINS")
    return revisions, pins


def main() -> int:
    manifest_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "models.yaml"
    setup_py = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path("/src/strata/setup.py")
    manifest = rc_strata.load_manifest(manifest_path)
    revisions, pins = parse_setup_pins(setup_py)
    errors = []
    for name, spec in manifest["models"].items():
        for entry in spec["files"]:
            repo, rev, path = entry["repo"], entry["revision"], entry["path"]
            fname = pathlib.Path(path).name
            if repo not in revisions:
                errors.append(f"{name}: repo {repo} is not in setup.py HF_REVISIONS")
                continue
            if revisions[repo] != rev:
                errors.append(f"{name}: {repo} revision {rev} != setup.py {revisions[repo]}")
            pin = pins.get((repo, fname))
            if pin is None:
                errors.append(f"{name}: {repo} {fname} is not in setup.py REPO_PINS")
                continue
            bytes_, sha = pin
            if int(entry["bytes"]) != bytes_:
                errors.append(f"{name}: {fname} bytes {entry['bytes']} != setup.py {bytes_}")
            if entry["sha256"] != sha:
                errors.append(f"{name}: {fname} sha256 {entry['sha256']} != setup.py {sha}")
    if errors:
        print("check_manifest: FAIL")
        print("\n".join(errors))
        return 1
    n = sum(len(s["files"]) for s in manifest["models"].values())
    print(f"check_manifest: {len(manifest['models'])} models, {n} files match {setup_py}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
