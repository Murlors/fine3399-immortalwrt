#!/usr/bin/env python3
"""Safely extract the matching kernel header archive from an ophub bundle."""

from __future__ import annotations

import argparse
import io
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

if __package__:
    from .archive_paths import safe_member_path
else:
    from archive_paths import safe_member_path


class ExtractError(RuntimeError):
    pass


def extract_headers(kernel: Path, output: Path) -> None:
    candidates: list[bytes] = []
    with tarfile.open(kernel, "r:gz") as outer:
        for member in outer.getmembers():
            path = safe_member_path(member.name)
            if member.isfile() and path.name.startswith("header-") and path.name.endswith(".tar.gz"):
                stream = outer.extractfile(member)
                if stream:
                    candidates.append(stream.read())
    if len(candidates) != 1:
        raise ExtractError(f"expected one ophub header archive, found {len(candidates)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".ophub-headers-", dir=output.parent))
    try:
        with tarfile.open(fileobj=io.BytesIO(candidates[0]), mode="r:gz") as headers:
            for member in headers.getmembers():
                safe_member_path(member.name)
            headers.extractall(staging, filter="data")
        required = ("Makefile", "Module.symvers", "include/config/kernel.release")
        missing = [name for name in required if not (staging / name).is_file()]
        if missing:
            raise ExtractError(f"ophub headers are incomplete: {', '.join(missing)}")
        (staging / ".fine3399-ophub-headers").touch()
        if output.exists():
            if not (output / ".fine3399-ophub-headers").is_file():
                raise ExtractError(f"refusing to replace unmarked output: {output}")
            shutil.rmtree(output)
        staging.rename(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        extract_headers(args.kernel, args.output)
    except (ExtractError, OSError, tarfile.TarError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
