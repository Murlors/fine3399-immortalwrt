#!/usr/bin/env python3
"""Rename downloaded APK assets to the canonical name encoded in metadata."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def filename_component(value: Any, label: str) -> str:
    """Reject path/control characters without imposing package syntax rules."""
    forbidden = '<>:"/\\|?*'
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or any(char in value for char in forbidden)
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError(f"invalid APK {label} for filename: {value!r}")
    return value


def package_identity(metadata: dict[str, Any]) -> tuple[str, str]:
    packages = metadata.get("packages")
    if packages is None and isinstance(metadata.get("info"), dict):
        # `apk adbdump` reports one APK as an object containing its package
        # record under `info`, alongside file/path metadata.
        packages = [metadata["info"]]
    if packages is None and "name" in metadata and "version" in metadata:
        package = metadata
    elif isinstance(packages, list) and len(packages) == 1:
        package = packages[0]
    else:
        sample = json.dumps(metadata, sort_keys=True)[:1200]
        raise ValueError(f"APK metadata must describe exactly one package; got {sample}")
    if not isinstance(package, dict):
        raise ValueError("APK metadata package record is not an object")
    name = filename_component(package.get("name"), "package name")
    version = filename_component(package.get("version"), "package version")
    return name, version


def normalize(apk_tool: Path, packages_dir: Path, assets_file: Path) -> list[tuple[str, str]]:
    renamed: list[tuple[str, str]] = []
    for asset in assets_file.read_text(encoding="utf-8").splitlines():
        if not asset:
            continue
        if Path(asset).name != asset or not asset.endswith(".apk"):
            raise ValueError(f"invalid APK asset filename: {asset!r}")
        source = packages_dir / asset
        if not source.is_file():
            raise FileNotFoundError(f"missing copied APK asset: {source}")
        result = subprocess.run(
            [str(apk_tool), "adbdump", "--format", "json", str(source)],
            check=True,
            capture_output=True,
            text=True,
        )
        name, version = package_identity(json.loads(result.stdout))
        target = packages_dir / f"{name}-{version}.apk"
        if target == source:
            continue
        if target.exists():
            raise FileExistsError(f"refusing to overwrite normalized APK: {target}")
        source.rename(target)
        renamed.append((asset, target.name))
    return renamed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk-tool", type=Path, required=True)
    parser.add_argument("--packages-dir", type=Path, required=True)
    parser.add_argument("--assets-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        for original, normalized in normalize(args.apk_tool, args.packages_dir, args.assets_file):
            print(f"Normalized local APK filename: {original} -> {normalized}")
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
