# Shadowrocket Proxy Rules

面向个人使用的 Shadowrocket 配置：保留上游“全局代理 + 去广告”，并让微信、QQ、哔哩哔哩、DeepSeek 和 Apple 推送服务直连。

## 使用地址

在 Shadowrocket 的“配置”页面添加：

```text
https://raw.githubusercontent.com/CyberWei922/shadowrocket-proxy-rules/main/dist/sr_proxy_banad_custom.conf
```

导入后将全局路由设为“配置”，断开并重新连接一次。

## 流量策略

1. 上游广告规则优先执行并 `REJECT`。
2. 微信、QQ、哔哩哔哩、DeepSeek 和 APNs 使用 `DIRECT`。
3. 微信、QQ 等原生客户端直接连接中国大陆 CDN IP 时，由
   `GEOIP,CN,DIRECT,no-resolve` 兜底直连；`no-resolve` 不会为此额外触发 DNS 查询。
4. 局域网使用 `DIRECT`。
5. 其余请求由 `FINAL,PROXY` 交给 Shadowrocket 当前选择的代理节点。

自定义直连规则位于 [`rules/direct.list`](rules/direct.list)。它们被插入到上游广告规则之后，因此不会覆盖已有广告拦截。

## DNS 策略

- 代理流量：Cloudflare/Google DoH，并显式使用 `#proxy`。
- 直连流量：阿里/腾讯 DoH。
- 禁止回退到系统 DNS。
- 劫持传统 53 端口 DNS 请求。
- 关闭 `bypass-system`，让 APNs 等系统连接进入明确的规则链。
- IPv6 关闭；代理不支持 UDP 时拒绝回退；代理流量禁用 QUIC。

这能减少常见的运营商 DNS 和错误直连回退，但不能拦截所有 App 自带的 DoH/DoQ。直连服务的目标 IP 仍然对本地网络可见。

## 自动更新

GitHub Actions 每天在北京时间 09:30、日本时间 10:30 拉取上游配置，重新注入 DNS 与自定义直连规则，验证后仅在内容变化时提交。也可以在 Actions 页面手动运行。

上游：[`Johnshall/Shadowrocket-ADBlock-Rules-Forever`](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever)，配置文件为 `sr_proxy_banad.conf`。

## 验证建议

更新配置并重新连接后分别验证：

1. 锁屏或把微信切到后台，让另一台设备发送消息并记录通知延迟。
2. 打开 QQ 群公告及其中的图片或附件。
3. 播放哔哩哔哩视频并拖动进度条。
4. 在 Shadowrocket 请求日志中确认相关请求命中 `DIRECT`，普通外部站点命中 `PROXY`。

## 许可与来源

生成的配置衍生自 Johnshall 的规则，按其 Creative Commons Attribution-ShareAlike 4.0 International 许可继续分发。自定义域名参考了 Apple 官方 APNs 网络要求以及社区维护的服务域名集合。
