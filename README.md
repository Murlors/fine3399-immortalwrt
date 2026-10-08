# Fine3399 ImmortalWrt

[![Build Fine3399 firmware](https://github.com/Murlors/fine3399-immortalwrt/actions/workflows/build-fine3399.yml/badge.svg)](https://github.com/Murlors/fine3399-immortalwrt/actions/workflows/build-fine3399.yml)

面向 Fine3399 的 ImmortalWrt 有线主路由固件。镜像预装路由、代理、远程接入、
NAS、容器和状态屏所需组件，首次启动无需在线安装软件包。

## 主要功能

| 类别 | 预装能力 |
| --- | --- |
| 主路由 | PPPoE、DHCP、IPv6、Firewall4/nftables、SQM、流量统计 |
| 网络服务 | OpenClash、DDNS-Go、FRPS、Nginx UI、Nginx TLS/Stream、UPnP、adblock-fast |
| NAS | Samba（Mac/SMB1 兼容）、Avahi、SFTP、rsync、DiskMan、Btrfs、NVMe/SMART 工具 |
| 容器 | Docker、Docker Compose、LuCI Dockerman |
| 管理 | 中文 LuCI、Argon、SSH、常用诊断工具 |
| 硬件 | 双网口、BCM43362 Wi-Fi、Rockchip HDMI/DRM、0.96 寸 ST7735S 160×80 SPI 屏 |

OpenClash 保持关闭，但预置当前验证过的 redir-host、IPv6、DNS 接管和绕过策略；
只有手动配置代理后才启用。adblock-fast 默认启用 1Hosts Lite，且不拒绝客户端自选 DNS/DoT；
DDNS-Go、FRPS、UPnP、Docker 等需要设备配置或凭据的服务默认不启动。仓库不保存 PPPoE
账号、域名、API Token、FRP 密钥、代理订阅或其他设备配置。

LCD 由原生 C 守护进程驱动，启动时先播放 6 秒遥像素动画，然后轮播网络、系统和
服务状态。服务页显示 OpenClash、DDNS-Go、FRPS 与 Docker 容器汇总，
Docker 使用容器鲸鱼像素图标。背景和动画都在构建时预转换为 RGB565，运行时直接
写入 framebuffer，固件不再预装 Python、Pillow 和 TrueType 字体。

可在 p4 的 `/mnt/mmcblk2p4/lcd/` 放置 `status.rgb565`、`startup.rgb565` 和
`animation.rgb565` 覆盖内置素材。启动动画只播放一次；3.5 秒日常动画每三轮页面播放一次，
前后由 C 程序对真实状态页做 0.6 秒动态交叉淡化。在电脑或 Actions 上使用以下命令转换源图：

```sh
python3 tools/convert_lcd_animation.py status.webp status.rgb565 --raw-frame
python3 tools/convert_lcd_animation.py startup.gif startup.rgb565
python3 tools/convert_lcd_animation.py animation.gif animation.rgb565
```

## 构建方式

构建链只保留一条受支持路径：

1. ImmortalWrt 25.12.2 ImageBuilder 生成预装 rootfs；
2. 获取 Argon、OpenClash、官方 Nginx UI Release 和 ophub 6.12.112 内核包；
3. 编译启用 ST7735S 的 Fine3399 DTB；
4. 使用锁定的 ophub 打包器生成整盘镜像；
5. 验证软件包、覆盖文件、内核模块、DTB、校验和及压缩镜像。

每次构建解析到的实际版本、下载地址和 SHA256 都记录在产物的
`build-manifest.json` 中。

## 下载与构建

在仓库的 [Actions 页面](https://github.com/Murlors/fine3399-immortalwrt/actions/workflows/build-fine3399.yml)
选择 **Run workflow**。内核版本留空时使用当前仍可获取的 ophub 6.12.112；构建会清除
ImageBuilder 自带模块并替换为该内核的完整模块包。ImmortalWrt 25.12.2 的 armsr 包仍按
6.12.103 编译，因此不要从标准源单独升级 `kmod-*` 或内核包。升级后的镜像需先从可移除介质验收。
高级测试也可以手动指定同系列的准确版本。

手动构建完成后下载名为 `fine3399-immortalwrt-<版本>-<内核>` 的 artifact，其中包括：

- `fine3399-immortalwrt-<版本>-<内核>.img.gz`：Fine3399 整盘镜像；
- `build-manifest.json`、`kernel-bundle-manifest.json`：构建来源；
- `SHA256SUMS`：产物校验和。

rootfs 仅作为构建和验证的中间文件，不再放入下载产物。推送正式 `v*` 标签时，
工作流还会创建 GitHub Release，将上述文件作为独立 assets 提供直接下载。

Ubuntu 24.04 也可以在本地运行：

```sh
make image
```

依赖和完整流程见 [构建与发布](docs/build.md)。

## 磁盘布局

默认镜像包含 512 MiB BOOT 和 2 GiB Btrfs ROOTFS。剩余空间不会被自动格式化，
避免在镜像制作阶段误删原有数据。首次启动后由 ophub 的 `openwrt-tf` 创建 p3、p4，
并将 p4 作为 `SHARE_DATA` 挂载；Docker 数据目录随 ophub 的 UCI 配置放到 p4。
如果需要改用 NVMe，可在 LuCI Dockerman 中修改 `data_root`。

## 首次启动

1. 先从可移除介质启动，不要直接覆盖当前可用的 eMMC；
2. 固件默认将板载 `eth0` 设为 WAN 口、USB RTL8152 `eth1` 设为 LAN bridge；先确认接线和网口 MAC；
3. 通过 `192.168.1.1` 登录 LuCI，将 WAN 协议设为 PPPoE 并填写账号，再检查 IPv4、IPv6、DNS 和千兆链路；
4. 按需配置 OpenClash、DDNS-Go、FRPS、Nginx UI、Samba、Docker 等服务；
5. 完成 [硬件验收](docs/hardware-smoke-test.md) 并备份配置后，再写入 eMMC。

> `fine3399.img.gz` 是整盘镜像，不是 LuCI 中使用的 `sysupgrade.bin`。写盘会重建
> 目标设备的分区表并覆盖现有分区，请先确认目标磁盘并保留可启动备份。

## 维护文档

- [构建与发布](docs/build.md)
- [硬件验收](docs/hardware-smoke-test.md)
- [发布检查表](docs/release-checklist.md)
- [内核包格式](docs/kernel-bundle-format.md)
