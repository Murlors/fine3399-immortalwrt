#!/usr/bin/env python3
"""Create a checked local ophub kernel bundle with the custom Fine3399 DTB."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

if __package__:
    from .archive_paths import safe_member_path
else:
    from archive_paths import safe_member_path


REQUIRED_MODULES = (
    "drivers/net/tun.ko",
    "drivers/net/veth.ko",
    "drivers/net/usb/r8152.ko",
    "drivers/net/wireless/broadcom/brcm80211/brcmfmac/brcmfmac.ko",
    "drivers/gpu/drm/bridge/analogix/analogix_dp.ko",
    "drivers/gpu/drm/panfrost/panfrost.ko",
    "drivers/gpu/drm/rockchip/rockchipdrm.ko",
    "drivers/spi/spidev.ko",
    "drivers/staging/fbtft/fbtft.ko",
    "drivers/staging/fbtft/fb_st7735r.ko",
    "net/bridge/br_netfilter.ko",
    "net/netfilter/nft_fullcone.ko",
    "net/netfilter/nft_socket.ko",
    "net/netfilter/nft_tproxy.ko",
)
CUSTOM_MODULE_NAME = "fb_fine3399_st7735s.ko"


class ImportError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nested_archives(outer: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with tarfile.open(outer, "r:gz") as archive:
        for member in archive.getmembers():
            path = safe_member_path(member.name)
            if member.isfile() and path.name.endswith(".tar.gz"):
                stream = archive.extractfile(member)
                if stream:
                    result[path.name] = stream.read()
    return result


def replace_dtb(archive_data: bytes, dtb: bytes) -> bytes:
    output = io.BytesIO()
    found = 0
    with tarfile.open(fileobj=io.BytesIO(archive_data), mode="r:gz") as source:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as target:
                for member in source.getmembers():
                    path = safe_member_path(member.name)
                    info = tarfile.TarInfo(member.name)
                    info.mode = member.mode
                    info.type = member.type
                    info.linkname = member.linkname
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 0
                    if member.isfile():
                        data = dtb if path.name == "rk3399-fine3399.dtb" else source.extractfile(member).read()
                        found += int(path.name == "rk3399-fine3399.dtb")
                        info.size = len(data)
                        target.addfile(info, io.BytesIO(data))
                    else:
                        target.addfile(info)
    if found != 1:
        raise ImportError(f"expected one Fine3399 DTB in ophub archive, found {found}")
    return output.getvalue()


def validate_aarch64_elf(data: bytes) -> None:
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01":
        raise ImportError("custom LCD module is not a 64-bit little-endian ELF")
    if int.from_bytes(data[18:20], "little") != 183:
        raise ImportError("custom LCD module is not built for AArch64")


def add_module(archive_data: bytes, destination: str, module: bytes) -> bytes:
    output = io.BytesIO()
    found = 0
    with tarfile.open(fileobj=io.BytesIO(archive_data), mode="r:gz") as source:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as target:
                for member in source.getmembers():
                    safe_member_path(member.name)
                    found += int(member.name.lstrip("./") == destination)
                    info = tarfile.TarInfo(member.name)
                    info.mode = member.mode
                    info.type = member.type
                    info.linkname = member.linkname
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 0
                    if member.isfile():
                        data = source.extractfile(member).read()
                        info.size = len(data)
                        target.addfile(info, io.BytesIO(data))
                    else:
                        target.addfile(info)
                if found:
                    raise ImportError(f"custom module destination already exists: {destination}")
                info = tarfile.TarInfo(destination)
                info.mode = 0o644
                info.size = len(module)
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                target.addfile(info, io.BytesIO(module))
    return output.getvalue()


def import_bundle(
    outer: Path,
    dtb_path: Path,
    module_path: Path,
    resolved_path: Path,
    output: Path,
) -> None:
    resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
    expected = resolved["kernel"]["asset"].get("sha256")
    if expected and sha256_file(outer) != expected:
        raise ImportError("ophub kernel asset checksum mismatch")
    archives = nested_archives(outer)
    boot_names = [name for name in archives if name.startswith("boot-")]
    module_names = [name for name in archives if name.startswith("modules-")]
    dtb_names = [name for name in archives if name.startswith("dtb-rockchip-")]
    if not (len(boot_names) == len(module_names) == len(dtb_names) == 1):
        raise ImportError("ophub kernel asset does not contain one Rockchip kernel set")
    boot_name, modules_name, dtb_name = boot_names[0], module_names[0], dtb_names[0]
    release = boot_name.removeprefix("boot-").removesuffix(".tar.gz")

    module = module_path.read_bytes()
    validate_aarch64_elf(module)
    module_destination = f"{release}/kernel/drivers/staging/fbtft/{CUSTOM_MODULE_NAME}"
    archives[modules_name] = add_module(
        archives[modules_name], module_destination, module
    )

    with tarfile.open(fileobj=io.BytesIO(archives[modules_name]), mode="r:gz") as modules:
        names = {
            safe_member_path(member.name).as_posix()
            for member in modules.getmembers()
            if member.isfile()
        }
    required_modules = (*REQUIRED_MODULES, CUSTOM_MODULE_NAME)
    missing = [suffix for suffix in required_modules if not any(name.endswith(suffix) for name in names)]
    if missing:
        raise ImportError(f"ophub kernel is missing required modules: {', '.join(missing)}")

    dtb = dtb_path.read_bytes()
    patched_dtb_archive = replace_dtb(archives[dtb_name], dtb)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".kernel-bundle-", dir=output.parent))
    try:
        (staging / boot_name).write_bytes(archives[boot_name])
        (staging / modules_name).write_bytes(archives[modules_name])
        (staging / dtb_name).write_bytes(patched_dtb_archive)
        manifest = {
            "schema": 3,
            "kernel_release": release,
            "kernel_asset": resolved["kernel"]["asset"],
            "custom_dtb_sha256": sha256_bytes(dtb),
            "custom_module": {
                "path": module_destination,
                "sha256": sha256_bytes(module),
            },
            "required_modules": list(required_modules),
            "archives": {"boot": boot_name, "dtb": dtb_name, "modules": modules_name},
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        names_to_hash = (boot_name, dtb_name, modules_name, "manifest.json")
        (staging / "sha256sums").write_text(
            "".join(f"{sha256_file(staging / name)}  {name}\n" for name in names_to_hash),
            encoding="utf-8",
        )
        if output.exists():
            if not (output / "manifest.json").is_file():
                raise ImportError(f"refusing to replace unmarked output: {output}")
            shutil.rmtree(output)
        staging.rename(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--dtb", type=Path, required=True)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--resolved", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        import_bundle(args.kernel, args.dtb, args.module, args.resolved, args.output)
    except (ImportError, OSError, KeyError, ValueError, json.JSONDecodeError, tarfile.TarError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
