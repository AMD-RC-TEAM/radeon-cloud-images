#!/usr/bin/env python3
"""Upgrade bot: for each image, find the newest upstream tag matching image.yaml tag_regex; if it differs from the
Dockerfile's `# upstream:` line, rewrite the upstream line and the FROM digest and print the branch/title for the
workflow to open a PR. Never touches the catalog; merging the PR is the release gate (D-20261112-27).

  upstream_check.py [--write]     # without --write only reports
"""
import json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def hub_tags(repo, rx):
    url, out = f"https://hub.docker.com/v2/repositories/{repo}/tags?page_size=100&ordering=last_updated", []
    for _ in range(5):
        with urllib.request.urlopen(url, timeout=60) as r:
            d = json.load(r)
        out += [(t["name"], t.get("digest") or "", t.get("tag_last_pushed") or "") for t in d.get("results", [])
                if re.match(rx, t["name"]) and (t.get("digest") or "").startswith("sha256:")]
        url = d.get("next")
        if not url:
            break
    return sorted(out, key=lambda t: t[2], reverse=True)


def version_key(tag):
    return [int(x) for x in re.findall(r"\d+", tag)]


def pypi_latest(name):
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=60) as r:
        return json.load(r)["info"]["version"]


def watch_notices():
    """image.yaml `watch_pypi: <package>`: report when PyPI has a newer release than requirements.txt pins.
    These need a human (for SGLang: pick the SGLang commit the new plugin supports), so they become an issue, not a branch."""
    out = []
    for image in sorted(os.listdir(os.path.join(ROOT, "images"))):
        d = os.path.join(ROOT, "images", image)
        m = re.search(r"^watch_pypi:\s*(\S+)", open(os.path.join(d, "image.yaml")).read(), re.M)
        req = os.path.join(d, "requirements.txt")
        if not m or not os.path.exists(req):
            continue
        pkg = m.group(1)
        pin = re.search(rf"^{re.escape(pkg)}==(\S+)", open(req).read(), re.M | re.I)
        latest = pypi_latest(pkg)
        if pin and version_key(latest) > version_key(pin.group(1)):
            out.append(f"{image}: {pkg} {pin.group(1)} -> {latest} on PyPI")
        print(f"{image}: watch {pkg} pinned {pin.group(1) if pin else '?'}, PyPI {latest}")
    return out


def main():
    write = "--write" in sys.argv
    changes = []
    notices = watch_notices()
    for image in sorted(os.listdir(os.path.join(ROOT, "images"))):
        d = os.path.join(ROOT, "images", image)
        y = open(os.path.join(d, "image.yaml")).read()
        repo = re.search(r"^\s+repo:\s*(\S+)", y, re.M).group(1)
        rx = re.search(r"^\s+tag_regex:\s*'([^']+)'", y, re.M).group(1)
        dfp = os.path.join(d, "Dockerfile"); df = open(dfp).read()
        cur = re.search(r"^# upstream: \S+?/\S+?:([^:@/\s]+)@(sha256:[0-9a-f]{64})", df, re.M)
        tags = hub_tags(repo, rx)
        if not tags:
            print(f"{image}: no upstream tag matches {rx}"); continue
        best = max(tags, key=lambda t: version_key(t[0]))
        if (best[0], best[1]) == (cur.group(1), cur.group(2)):
            print(f"{image}: up to date ({best[0]})"); continue
        print(f"{image}: {cur.group(1)} -> {best[0]} ({best[1][:19]})")
        changes.append(f"{image} {cur.group(1)} -> {best[0]}")
        if write:
            df = df.replace(f":{cur.group(1)}@{cur.group(2)}", f":{best[0]}@{best[1]}").replace(f"@{cur.group(2)}", f"@{best[1]}")
            open(dfp, "w").write(df)
    if notices and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("notice=" + "; ".join(notices)[:300] + "\n")
    if changes and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("changed=true\n")
            f.write("title=chore(images): upstream " + "; ".join(changes)[:200] + "\n")


if __name__ == "__main__":
    main()
