#!/usr/bin/env python3
"""Set the integration version everywhere it is stored.

Usage:
  scripts/bump_version.py 2.8.0              update every version file
  scripts/bump_version.py --normalize 2.8.0  only validate and print the version

A leading "v" and surrounding whitespace are dropped. Lowering the version
below the one in manifest.json is refused.

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

# X.Y.Z with an optional suffix such as b1, -rc.1 or .b (dot-separated
# alphanumeric parts, no empty parts).
VERSION_RE = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)(?:[-.]?[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)?$"
)
JSON_VERSION_RE = re.compile(r'("version"\s*:\s*")([^"]*)(")')


def set_json_version(path: pathlib.Path, version: str) -> None:
    # Replace only the value so the file's formatting stays as it is.
    text = path.read_text(encoding="utf-8")
    new_text, count = JSON_VERSION_RE.subn(
        rf"\g<1>{version}\g<3>", text, count=1
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


def release_tuple(version: str) -> tuple[int, int, int]:
    match = VERSION_RE.match(version)
    if not match:
        raise SystemExit(f"Cannot parse version {version!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def current_version() -> str:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]


def main(argv: list[str]) -> int:
    args = argv[1:]
    only_normalize = bool(args) and args[0] == "--normalize"
    if only_normalize:
        args = args[1:]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    version = normalize(args[0])
    if only_normalize:
        print(version)
        return 0

    current = current_version()
    if release_tuple(version) < release_tuple(current):
        raise SystemExit(f"Refusing to lower the version from {current} to {version}")
    for path, updater in VERSION_FILES:
        updater(path, version)
        print(f"{path.relative_to(ROOT)} -> {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
