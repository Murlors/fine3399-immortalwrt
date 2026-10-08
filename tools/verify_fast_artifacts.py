#!/usr/bin/env python3
"""Verify the ImageBuilder rootfs, checked ophub bundle, and packaged image."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path, PurePosixPath


EXPECTED_PACKAGES = {
    "luci",
    "luci-i18n-base-zh-cn",
    "luci-i18n-adblock-fast-zh-cn",
    "luci-i18n-argon-config-zh-cn",
    "luci-i18n-ddns-go-zh-cn",
    "luci-i18n-diskman-zh-cn",
    "luci-i18n-dockerman-zh-cn",
    "luci-i18n-firewall-zh-cn",
    "luci-i18n-frps-zh-cn",
    "luci-i18n-nlbwmon-zh-cn",
    "luci-i18n-package-manager-zh-cn",
    "luci-i18n-samba4-zh-cn",
    "luci-i18n-sqm-zh-cn",
    "luci-i18n-upnp-zh-cn",
    "luci-theme-argon",
    "luci-app-openclash",
    "ddns-go",
    "luci-app-ddns-go",
    "frps",
    "luci-app-frps",
    "fdisk",
    "lsblk",
    "parted",
    "cypress-firmware-43362-sdio",
    "r8152-firmware",
    "luci-app-diskman",
    "luci-app-upnp",
    "samba4-server",
    "openssh-sftp-server",
    "dockerd",
    "luci-app-dockerman",
    "avahi-dbus-daemon",
    "avahi-utils",
    "adblock-fast",
    "gawk",
    "grep",
    "sed",
    "coreutils-sort",
    "nginx-ssl",
    "nginx-mod-stream",
}
class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_members(archive: tarfile.TarFile):
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or member.isdev():
            raise VerificationError(f"unsafe archive member: {member.name}")
        yield member


def verify_checksums(bundle: Path) -> None:
    lines = (bundle / "sha256sums").read_text(encoding="utf-8").splitlines()
    for line in lines:
        expected, name = line.split(maxsplit=1)
        target = bundle / name.strip()
        if not target.is_file() or sha256(target) != expected:
            raise VerificationError(f"kernel bundle checksum mismatch: {name.strip()}")


def verify_rootfs(rootfs: Path) -> None:
    apk_database = ""
    required_files = {
        "etc/fine3399-build.json",
        "etc/fine3399-nginx-ui-release.json",
        "etc/uci-defaults/90-fine3399-baseline",
        "etc/init.d/lcd_display",
        "etc/init.d/nginx-ui",
        "etc/config/nginx",
        "etc/config/nginx-ui",
        "etc/config/samba4",
        "etc/avahi/avahi-daemon.conf",
        "etc/nginx-ui/app.ini",
        "etc/nginx/nginx.conf",
        "lib/upgrade/keep.d/nginx-ui",
        "usr/share/luci/menu.d/fine3399-nginx-ui.json",
        "www/luci-static/resources/view/fine3399/nginx-ui.js",
        "etc/modules.d/drm-rockchip",
        "etc/modules.d/30-brcmfmac",
        "usr/bin/fine3399-lcd",
        "usr/share/fine3399-lcd/status.rgb565",
        "usr/share/fine3399-lcd/startup.rgb565",
        "usr/share/fine3399-lcd/animation.rgb565",
        "lib/firmware/brcm/brcmfmac43362-sdio.txt",
        "lib/firmware/rtl_nic/rtl8153b-2.fw",
        "usr/bin/frps",
        "usr/bin/nginx-ui",
    }
    found_files: set[str] = set()
    selected_files: dict[str, bytes] = {}
    with tarfile.open(rootfs, "r:gz") as archive:
        for member in safe_members(archive):
            name = member.name.lstrip("./")
            found_files.add(name)
            if name in {
                "etc/fine3399-nginx-ui-release.json",
                "usr/bin/fine3399-lcd",
                "usr/bin/frps",
                "usr/bin/nginx-ui",
            } and member.isfile():
                stream = archive.extractfile(member)
                selected_files[name] = stream.read() if stream else b""
            if name != "lib/apk/db/installed" or not member.isfile():
                continue
            stream = archive.extractfile(member)
            data = stream.read() if stream else b""
            apk_database = data.decode("utf-8", errors="ignore")
    missing_files = sorted(required_files - found_files)
    if missing_files:
        raise VerificationError(f"rootfs is missing overlay files: {', '.join(missing_files)}")
    installed = set(re.findall(r"^P:(.+)$", apk_database, re.MULTILINE))
    missing_packages = sorted(EXPECTED_PACKAGES - installed)
    if missing_packages:
        raise VerificationError(f"rootfs is missing packages: {', '.join(missing_packages)}")
    frps = selected_files["usr/bin/frps"]
    if not frps.startswith(b"\x7fELF"):
        raise VerificationError("rootfs FRPS package payload is not an ELF binary")
    lcd = selected_files["usr/bin/fine3399-lcd"]
    if (
        lcd[:6] != b"\x7fELF\x02\x01"
        or len(lcd) < 20
        or int.from_bytes(lcd[18:20], "little") != 183
    ):
        raise VerificationError("rootfs LCD daemon is not AArch64 ELF64")
    nginx_ui = selected_files["usr/bin/nginx-ui"]
    if (
        nginx_ui[:6] != b"\x7fELF\x02\x01"
        or len(nginx_ui) < 20
        or int.from_bytes(nginx_ui[18:20], "little") != 183
    ):
        raise VerificationError("rootfs Nginx UI override is not AArch64 ELF64")
    marker = json.loads(selected_files["etc/fine3399-nginx-ui-release.json"])
    if marker.get("binary_sha256") != hashlib.sha256(nginx_ui).hexdigest():
        raise VerificationError("rootfs Nginx UI override checksum mismatch")


def verify_bundle(bundle: Path) -> None:
    verify_checksums(bundle)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != 3:
        raise VerificationError("expected kernel bundle schema 3")
    dtb_archive = bundle / manifest["archives"]["dtb"]
    with tarfile.open(dtb_archive, "r:gz") as archive:
        matches = [
            member
            for member in safe_members(archive)
            if member.isfile() and PurePosixPath(member.name).name == "rk3399-fine3399.dtb"
        ]
        if len(matches) != 1:
            raise VerificationError("kernel bundle must contain one Fine3399 DTB")
        data = archive.extractfile(matches[0]).read()
        if hashlib.sha256(data).hexdigest() != manifest["custom_dtb_sha256"]:
            raise VerificationError("custom Fine3399 DTB checksum mismatch")
    module_archive = bundle / manifest["archives"]["modules"]
    module_contract = manifest["custom_module"]
    with tarfile.open(module_archive, "r:gz") as archive:
        matches = [
            member
            for member in safe_members(archive)
            if member.isfile() and member.name.lstrip("./") == module_contract["path"]
        ]
        if len(matches) != 1:
            raise VerificationError("kernel bundle must contain one custom LCD module")
        module = archive.extractfile(matches[0]).read()
        if module[:6] != b"\x7fELF\x02\x01" or int.from_bytes(module[18:20], "little") != 183:
            raise VerificationError("custom LCD module is not AArch64")
        if hashlib.sha256(module).hexdigest() != module_contract["sha256"]:
            raise VerificationError("custom LCD module checksum mismatch")


def verify_image(image: Path) -> None:
    if not image.is_file() or image.stat().st_size < 8 * 1024 * 1024:
        raise VerificationError("packaged image is missing or unexpectedly small")
    total = 0
    with gzip.open(image, "rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            total += len(chunk)
    if total < 1024 * 1024 * 1024:
        raise VerificationError("uncompressed disk image is unexpectedly small")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        verify_rootfs(args.rootfs)
        verify_bundle(args.bundle)
        verify_image(args.image)
    except (VerificationError, OSError, KeyError, ValueError, json.JSONDecodeError, tarfile.TarError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
