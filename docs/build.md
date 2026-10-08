# 构建与发布

## 推荐：GitHub Actions

在仓库 Actions 中手动运行 **Build Fine3399 firmware**。当前基线为 ImmortalWrt
25.12.2 与当前可获取的 ophub 6.12.112；也可以为测试输入其他精确的 6.12.x 版本。
ophub 内核模块会替换 ImageBuilder 的模块目录；升级后的内核/驱动组合必须先经过硬件验收。
注意：ImmortalWrt 25.12.2 自带的 armsr 内核包版本为 6.12.103，而当前可获取的 ophub
包为 6.12.112。打包时会移除 ImageBuilder 的 `/lib/modules/*` 并换成 ophub 模块；因此不要
从标准软件源单独安装/升级 `kmod-*` 或内核包，除非为实际运行的 ophub 内核重新构建并验证。

普通 `main` 提交只运行测试，不生成版本会漂移的大镜像。手动运行和 `v*` 标签
才执行完整构建，通常只需要下载和重组包、编译单个 DTB，避免数小时源码交叉编译。

产物包含：

- `fine3399-immortalwrt-<版本>-<内核>.img.gz`：可写盘镜像；
- `build-manifest.json`：本次实际解析版本、URL、SHA256；
- `kernel-bundle-manifest.json` 与 `SHA256SUMS`。

rootfs 仍会在 CI 中生成并参与验证，但不再上传。手动构建使用短期 Actions artifact；
`v*` 标签构建成功后会自动创建 GitHub Release，并将以上文件作为独立 assets 发布。

## 本地 Linux

Ubuntu 24.04 非 root 用户可运行：

```sh
make image
```

ImageBuilder 和 DTB 阶段拒绝 root；只有 ophub 挂载和封装磁盘镜像时通过 `sudo`
运行。下载缓存位于 `dl/`。

## 首次启动

软件不在首次启动时下载。自动脚本只会：

- 设置主机名、Asia/Shanghai 与无线国家码 CN；
- 启用 LCD 状态服务；
- 启用仅绑定 `br-lan` 的 Avahi；Samba 预置 Mac 兼容和 SMB1 旧设备兼容，但不创建共享；
- 保持 OpenClash、FRPS、DDNS-Go、UPnP、Docker 等待配置的服务关闭；OpenClash
  预置已审核的策略但不启用；adblock-fast 使用 1Hosts Lite 且关闭强制 DNS 拒绝；
- 为 Dockerd 预置当前网络已实测可用的 `docker.1panel.live` 加速项，可在
  Dockerman 中随时替换或删除；
- 启动 Nginx UI（9000）和没有默认监听端口的 Nginx，不抢占 LuCI 的 80/443。

FRPS 直接使用 ImmortalWrt 软件仓库中的 `frps`、init 脚本和 LuCI 管理界面，不再使用
上游 Release 覆盖软件包管理器维护的二进制。DDNS 使用 ImmortalWrt 原生维护的
`ddns-go`、LuCI 管理界面和简体中文语言包；Cloudflare、DNSPod、阿里云或其他提供商
由用户配置，并未绑定 Cloudflare。

Nginx UI 使用官方 `0xJacky/nginx-ui` 最新稳定 Release 的 ARM64 二进制，作为原生
procd 服务运行。LuCI 顶级菜单可直接嵌入或打开管理界面。配置与数据库默认保留在
`/etc/nginx-ui`；如需迁移到 p4，可将 UCI 的 `nginx-ui.main.config_path` 设置为
`/mnt/mmcblk2p4/nginx-ui/app.ini` 后重启服务；首次切换会复制已有数据，且目标挂载
不存在时服务会拒绝启动，避免误写根分区。基础 Nginx 配置包含 HTTP 与 Stream 管理
目录，但默认没有任何 `listen`，因此启用站点前不会与 uHTTPd 冲突。

固件首次启动时默认将板载 `eth0` 设为 WAN 物理口、USB RTL8152 `eth1` 设为 LAN bridge；首次登录后在 LuCI 中将 WAN 协议设为 PPPoE 并填写账号密码，再分别配置服务。若改变网卡接线或更换 USB 网卡，需重新核对 LAN/WAN 映射。FRPC 未预装。

## 数据分区和 Docker

首次启动后由 ophub 的 `openwrt-tf` 创建并挂载 p3、p4，其中 p4 标记为
`SHARE_DATA`，Docker 数据目录通过 UCI 自动指向 p4。若要改用 NVMe，可在 LuCI
Dockerman 中修改 `data_root`。整盘写入会覆盖目标磁盘已有分区，写盘前必须备份。
镜像和容器配置等小体量运行数据可留在 p4；下载、媒体库和备份等大文件应放 NVMe，
避免占满约 11 GiB 的共享分区。

## 调整预装软件

普通软件增删只需修改 `configs/imagebuilder/packages.txt`。内核、OpenClash 和 Argon
的 Release 来源位于 `configs/releases.json`；ophub 打包器版本位于
`versions.lock.json`。
