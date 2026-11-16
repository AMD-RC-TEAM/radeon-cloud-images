#!/usr/bin/env python3
"""Teach the upstream docker/entrypoint.sh SPEED and STRATA_LAUNCH_EXTRA (build-time only)."""
from pathlib import Path
import sys

p = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/strata/entrypoint.sh")
t = p.read_text()
needle = '[ -n "${STRATA_SET:-}" ]'
insert = (
    '[ -n "${SPEED:-}" ] && { set -- "$@" --speed "$SPEED"; have=1; }\n'
    '[ -n "${STRATA_LAUNCH_EXTRA:-}" ] && [ -f "$STRATA_LAUNCH_EXTRA" ] && { '
    'while IFS= read -r a || [ -n "$a" ]; do [ -n "$a" ] && set -- "$@" "$a"; done '
    '< "$STRATA_LAUNCH_EXTRA"; have=1; }\n'
)
if needle not in t:
    sys.exit(f"{p}: STRATA_SET line not found")
if "${SPEED:-}" not in t:
    t = t.replace(needle, insert + needle, 1)
    p.write_text(t)
print(f"patched {p}")
