#!/usr/bin/env python3
"""Print the images a change touches, as `images=<json list>` for $GITHUB_OUTPUT.

  changed_images.py <base-ref> <head-ref>

A change to tools/keep_image_env.* (the shared SSH-environment step release.py adds to every image) counts as a change
to every image. Otherwise an image counts as changed when any file under images/<name>/ differs between the two refs, except when the only
changed file is image.yaml and it parses to the same data (comment or formatting edits). Those would otherwise
re-build and re-release the image with no functional change.
"""
import json, os, subprocess, sys
import yaml


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def yaml_at(ref, path):
    try:
        return yaml.safe_load(git("show", f"{ref}:{path}"))
    except subprocess.CalledProcessError:
        return None  # file absent at that ref


SHARED_STEP = "tools/keep_image_env."   # the SSH-environment script and its Dockerfile lines, added to every image


def changed_images(base, head):
    if any(f.startswith(SHARED_STEP) for f in git("diff", "--name-only", base, head, "--", "tools/").split()):
        print("tools/keep_image_env.* changed: every image is affected", file=sys.stderr)
        return sorted(d for d in os.listdir("images") if os.path.isdir(os.path.join("images", d)))
    files = {}
    for path in git("diff", "--name-only", base, head, "--", "images/").split():
        parts = path.split("/")
        if len(parts) >= 3:
            files.setdefault(parts[1], set()).add(parts[2] if len(parts) == 3 else "/".join(parts[2:]))
    images = []
    for name, changed in sorted(files.items()):
        path = f"images/{name}/image.yaml"
        if changed == {"image.yaml"} and yaml_at(base, path) is not None and yaml_at(base, path) == yaml_at(head, path):
            print(f"{name}: only comments/formatting changed in image.yaml, not released", file=sys.stderr)
            continue
        images.append(name)
    return images


if __name__ == "__main__":
    print("images=" + json.dumps(changed_images(sys.argv[1], sys.argv[2])))
