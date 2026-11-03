# 资源下载与直连排查

## 代码中的下载路径

程序启动的 Chromium 使用本地 mitmproxy，以捕获对局 WebSocket 并应用 MajsoulMax 修改。

```text
Chromium → 本地 mitmproxy → 上游代理（如有）→ 游戏服务器／资源 CDN
```

“设置 → 高级 → 连接与代理”中的上游代理留空时，mitmproxy 自行建立连接。程序没有额外的带宽限速、资源逐个下载队列或固定 140 KB/s 限制。浏览器使用持久化资料目录，代码没有禁用 HTTP 缓存，也没有安装会关闭缓存的 Playwright 请求路由。

本地捕获代理仍有连接、TLS 与处理开销，不能等同于浏览器完全不经过代理的路径。

## 这次的改动

以前仅设置 `stream_large_bodies='256k'`，小响应仍可能先完整缓冲。现在在收到普通 HTTP 响应头时即启用流式转发，包括小文件和未知正文长度的分块响应。此项目只修改 WebSocket 消息，普通 HTTP 正文无需保留。

HTTP 101 协议升级保留原处理方式，捕获、AI 消息与本地装扮修改继续工作。不增加磁盘缓存，不改动 CDN 地址、内容编码或资源版本。实现依据见 [mitmproxy Streaming](https://docs.mitmproxy.org/stable/overview/features/#streaming)。

离线测试使用实际本地 HTTP 服务器和 mitmproxy：源站发出前 4 字节后暂停，验证浏览器侧可先收到数据，再继续完成响应。覆盖小于原阈值的固定长度响应及未知大小的分块响应。这证明缓冲等待已移除，**不证明真实 CDN 的下载带宽会提高**。

## Clash／Mihomo TUN

TUN 可以在网络层接管应用流量；程序上游代理留空并不能绕过 TUN。是否走机场取决于规则模式、命中的出站策略及 DNS 配置。即使命中 DIRECT，也可能经过 TUN 的处理与 DNS。参考 [TUN](https://wiki.metacubex.one/config/inbound/tun/)、[路由规则](https://wiki.metacubex.one/config/rules/) 和 [DNS 配置](https://wiki.metacubex.one/config/dns/)。

如果希望资源直连，可在规则模式下将已确认的域名加入优先级足够高的 DIRECT 规则，例如：

```yaml
rules:
  - DOMAIN,game.maj-soul.com,DIRECT
  # 其余规则保持自己的配置
```

这是插入现有规则列表的示例，不是完整配置。若下载跳转到其他 CDN 域名，需在连接面板核对实际命中规则；单独这一条不能保证所有资源直连。本文不修改你的 Clash 配置。

## 如何比较

1. 在程序中将上游代理留空。若刚改动连接设置，先关闭并重新打开游戏浏览器。
2. 选择**同一个实际资源 URL**，分别比较 TUN 关闭、TUN 开启且命中 DIRECT，以及确有必要时的代理节点。域名首页的加载速度不能代表皮肤资源的下载吞吐。
3. 在 Clash 连接面板确认最终域名与出站链，比较 DNS／CDN IP、首字节耗时和持续传输速度。使用浏览器开发者工具测试时统一缓存条件；正常游玩时保留缓存。
4. 使用相同资源、缓存条件和线路，再比较程序浏览器与普通浏览器。这样可以判断慢在 CDN／网络路径，还是本地捕获代理。

如果关闭 TUN 的同资源测试也只有约 140 KB/s，仅凭该数值无法归因给 TUN；本次代码修改也无法突破源站或运营商路径的瓶颈。
