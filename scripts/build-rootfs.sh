#!/usr/bin/env sh
set -eu

[ "$(id -u)" -ne 0 ] || { echo "Do not run ImageBuilder as root." >&2; exit 2; }
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

manifest=${1:-build/resolved-releases.json}
[ -s "$manifest" ] || { echo "Missing resolved release manifest: $manifest" >&2; exit 2; }

imagebuilder_url=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["immortalwrt"]["imagebuilder_url"])' "$manifest")
imagebuilder_sha256=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["immortalwrt"]["imagebuilder_sha256"])' "$manifest")
toolchain_url=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["immortalwrt"]["toolchain_url"])' "$manifest")
toolchain_sha256=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["immortalwrt"]["toolchain_sha256"])' "$manifest")
archive="dl/${imagebuilder_url##*/}"
mkdir -p dl build dist/staging
if [ ! -s "$archive" ]; then
	curl -fL --retry 4 --retry-delay 3 -o "${archive}.part" "$imagebuilder_url"
	mv "${archive}.part" "$archive"
fi
echo "$imagebuilder_sha256  $archive" | sha256sum -c -

toolchain_archive="dl/${toolchain_url##*/}"
if [ ! -s "$toolchain_archive" ]; then
	curl -fL --retry 4 --retry-delay 3 -o "${toolchain_archive}.part" "$toolchain_url"
	mv "${toolchain_archive}.part" "$toolchain_archive"
fi
echo "$toolchain_sha256  $toolchain_archive" | sha256sum -c -

tree=build/imagebuilder
if [ -e "$tree" ]; then
	[ -f "$tree/.fine3399-imagebuilder-tree" ] || { echo "Refusing to replace unmarked $tree" >&2; exit 2; }
	rm -rf "$tree"
fi
mkdir -p "$tree"
tar --zstd -xf "$archive" --strip-components=1 -C "$tree"
touch "$tree/.fine3399-imagebuilder-tree"
# ImmortalWrt 25.12.2's ImageBuilder uses a relative local APK repository
# path. Current apk-tools requires an explicit file:// URI to resolve local
# packages (including the downloaded Argon release assets).
if grep -Fq -- '--repository $(PACKAGE_DIR)/packages.adb' "$tree/Makefile"; then
	sed -i 's|--repository \$(PACKAGE_DIR)/packages.adb|--repository file://$(PACKAGE_DIR)/packages.adb|' "$tree/Makefile"
fi
grep -Fq -- '--repository file://$(PACKAGE_DIR)/packages.adb' "$tree/Makefile" || {
	echo "ImageBuilder local APK repository path is not supported." >&2
	exit 2
}
mkdir -p dl/imagebuilder
rm -rf "$tree/dl"
ln -s "$repo_dir/dl/imagebuilder" "$tree/dl"

# ophub consumes only a tar rootfs. Disable large EFI/ext4/SquashFS/initramfs
# diagnostics that the generic armsr ImageBuilder otherwise creates.
sed -i \
	-e 's/^CONFIG_TARGET_ROOTFS_INITRAMFS=y$/# CONFIG_TARGET_ROOTFS_INITRAMFS is not set/' \
	-e 's/^CONFIG_TARGET_ROOTFS_CPIOGZ=y$/# CONFIG_TARGET_ROOTFS_CPIOGZ is not set/' \
	-e 's/^CONFIG_TARGET_ROOTFS_EXT4FS=y$/# CONFIG_TARGET_ROOTFS_EXT4FS is not set/' \
	-e 's/^CONFIG_TARGET_ROOTFS_SQUASHFS=y$/# CONFIG_TARGET_ROOTFS_SQUASHFS is not set/' \
	-e 's/^CONFIG_TARGET_IMAGES_GZIP=y$/# CONFIG_TARGET_IMAGES_GZIP is not set/' \
	"$tree/.config"
grep -q '^CONFIG_TARGET_ROOTFS_TARGZ=y$' "$tree/.config"
! grep -q '^CONFIG_TARGET_ROOTFS_\(INITRAMFS\|CPIOGZ\|EXT4FS\|SQUASHFS\)=y$' "$tree/.config"

python3 - "$manifest" <<'PY' >build/third-party-assets.txt
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
for component in ("argon", "openclash"):
    for asset in data[component]["assets"]:
        print(asset["name"])
PY
while IFS= read -r asset; do
	[ -s "dl/releases/$asset" ] || { echo "Missing downloaded asset: $asset" >&2; exit 2; }
	cp "dl/releases/$asset" "$tree/packages/"
done <build/third-party-assets.txt

overlay=build/imagebuilder-files
overlay_marker=build/.fine3399-imagebuilder-files
if [ -e "$overlay" ]; then
	[ -f "$overlay_marker" ] || { echo "Refusing to replace unmarked $overlay" >&2; exit 2; }
	rm -rf "$overlay"
fi
mkdir -p "$overlay"
cp -a files/. "$overlay/"
cp "$manifest" "$overlay/etc/fine3399-build.json"
python3 tools/install_nginx_ui_release.py \
	--manifest "$manifest" \
	--downloads dl/releases \
	--root "$overlay"
toolchain_tree=build/toolchain
toolchain_marker=build/.fine3399-toolchain
if [ -e "$toolchain_tree" ]; then
	[ -f "$toolchain_marker" ] || { echo "Refusing to replace unmarked $toolchain_tree" >&2; exit 2; }
	rm -rf "$toolchain_tree"
fi
mkdir -p "$toolchain_tree"
tar --zstd -xf "$toolchain_archive" --strip-components=1 -C "$toolchain_tree"
touch "$toolchain_marker"
cc=$(find "$toolchain_tree" \( -type f -o -type l \) -path '*/bin/*-gcc' | head -n 1)
[ -x "$cc" ] || { echo "ImageBuilder target compiler is unavailable." >&2; exit 2; }
toolchain=$(dirname "$(dirname "$cc")")
mkdir -p "$overlay/usr/bin"
STAGING_DIR="$toolchain" "$cc" -std=c11 -Os -Wall -Wextra -Wformat=2 -fstack-protector-strong \
	-Wl,-z,now -Wl,-z,relro -s \
	-o "$overlay/usr/bin/fine3399-lcd" src/fine3399-lcd.c
touch "$overlay_marker"

packages=$(sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' configs/imagebuilder/packages.txt | tr '\n' ' ')
packages="$packages luci-theme-argon luci-app-argon-config luci-i18n-argon-config-zh-cn luci-app-openclash"
make -C "$tree" image PROFILE=generic PACKAGES="$packages" FILES="$repo_dir/$overlay"

set -- "$tree"/bin/targets/armsr/armv8/*-generic-rootfs.tar.gz
[ "$#" -eq 1 ] && [ -s "$1" ] || {
	echo "Expected exactly one generic ImageBuilder rootfs tarball, found $#" >&2
	exit 2
}
cp "$1" dist/staging/immortalwrt-armsr-armv8-rootfs.tar.gz
