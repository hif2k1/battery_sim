#!/usr/bin/env python3
"""Set the integration version everywhere it is stored.

Usage: scripts/bump_version.py 2.8.0   (a leading "v" is accepted and dropped)

Every file that carries the version is listed in VERSION_FILES. When a new
place starts carrying the version, add it there so releases keep it in sync.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "battery_sim" / "manifest.json"

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[.-]?[0-9A-Za-z.]+)?$")


def set_json_version(path: pathlib.Path, version: str) -> None:
    # Replace only the value so the file's formatting stays as it is.
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r'("version"\s*:\s*")[^"]*(")', rf"\g<1>{version}\g<2>", text, count=1
    )
    if count != 1:
        raise SystemExit(f'No "version" field found in {path}')
    if json.loads(new_text).get("version") != version:
        raise SystemExit(f"Failed to set version in {path}")
    path.write_text(new_text, encoding="utf-8")


# (file, updater) pairs. hacs.json has no version field: HACS uses the
# release tag, and the config flow reads the version from manifest.json.
VERSION_FILES = [
    (MANIFEST, set_json_version),
]


def normalize(raw: str) -> str:
    version = raw.strip().removeprefix("v")
    if not VERSION_RE.match(version):
        raise SystemExit(f"Invalid version: {raw!r} (expected e.g. 2.8.0)")
    return version


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    version = normalize(argv[1])
    for path, updater in VERSION_FILES:
        updater(path, version)
        print(f"{path.relative_to(ROOT)} -> {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
