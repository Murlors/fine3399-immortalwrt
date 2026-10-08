"""Shared path validation for POSIX-format archive members."""

from pathlib import PurePosixPath


def safe_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe archive member: {name}")
    return path
