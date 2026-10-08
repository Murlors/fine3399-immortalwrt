# Fine3399 硬件验收

1. 从可移除介质启动，确认串口、LuCI `192.168.1.1` 和 SSH 可达。
2. 固件默认将板载 GMAC `eth0` 配为 WAN 物理口，USB RTL8152 `eth1` 配为 LAN bridge；确认接线、MAC 和链路速率符合预期。
3. 将 WAN 协议设为 PPPoE 并填写账号后，验证 IPv4、IPv6 和 LAN 客户端连通性。
4. PPPoE 连通后测速并检查 nftables、IPv6 和千兆链路。
5. 验证路由器及 LAN 客户端的 DNS；adblock-fast 应报告 1Hosts Lite 正常加载，LAN 防火墙
   不应有拒绝客户端外部 UDP/TCP 53 或 853 的规则。
6. `iw reg get` 显示 `country CN`，板载 Wi-Fi 可扫描；主无线仍交给独立 AP。
7. `lsmod`/`modinfo` 检查 tun、nft_fullcone、nft_tproxy、veth、br_netfilter、brcmfmac 和 rockchipdrm。
8. ST7735S 亮屏，`/dev/fb0` 存在，LCD 显示 IP、温度和流量。
9. 确认 ophub 已创建并挂载 p3、p4，Docker 的 `data_root` 指向预期的 p4 或 NVMe。
10. 在 LuCI 中逐项配置并启动 OpenClash、DDNS-Go、FRPS、Samba/SFTP、Docker；
    验证 FRPS 端口范围和防火墙规则仅按实际需求开放。
11. 备份 `/etc/config`、OpenClash 配置和服务密钥，再考虑写入 eMMC。
