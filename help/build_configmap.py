#!/usr/bin/env python3
"""Build the amd-oneclick-shell-help ConfigMap (D-20261114-06) from help/rc-help.sh.in + help/text/*.txt.

    python3 help/build_configmap.py --namespace <runtime-namespace> > shell-help.yaml
    kubectl apply -f shell-help.yaml          # new instances pick it up; running ones keep theirs

Editing the help = editing help/text/*.txt (common.txt for every image; <family>.txt for quick start), then
rebuild and apply. Families are detected inside the instance (sglang, vllm, comfyui, pytorch); anything else gets
common.txt only. Placeholders: {B} {D} {R} (bold/dim/reset), {PORT}, {HFSLOW} from a family file's
"# port=N" / "# hfslow=<cmd>" lines.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_BYTES = 64 * 1024


def render() -> str:
    tpl = open(os.path.join(HERE, "rc-help.sh.in"), encoding="utf-8").read()
    cases = []
    for name in sorted(os.listdir(os.path.join(HERE, "text"))):
        if not name.endswith(".txt"):
            continue
        key = name[:-4]
        body = open(os.path.join(HERE, "text", name), encoding="utf-8").read().rstrip("\n")
        if "RC_HELP_EOF" in body:
            sys.exit(f"{name}: contains the heredoc terminator")
        cases.append(f"    {key}) cat <<'RC_HELP_EOF'\n{body}\nRC_HELP_EOF\n    ;;")
    script = tpl.replace("@@TEXTS@@", "\n".join(cases))
    if len(script.encode()) > MAX_BYTES:
        sys.exit(f"rc-help.sh is {len(script.encode())} bytes; the platform ignores more than {MAX_BYTES}")
    return script


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--script-only", action="store_true", help="print rc-help.sh instead of the ConfigMap")
    a = ap.parse_args()
    script = render()
    if a.script_only:
        sys.stdout.write(script); return
    cm = {"apiVersion": "v1", "kind": "ConfigMap",
          "metadata": {"name": "amd-oneclick-shell-help", "namespace": a.namespace,
                       "labels": {"app.kubernetes.io/part-of": "radeon-cloud", "radeon-cloud/decision": "D-20261114-06"}},
          "data": {"rc-help.sh": script}}
    json.dump(cm, sys.stdout, indent=2, ensure_ascii=False); sys.stdout.write("\n")


if __name__ == "__main__":
    main()
