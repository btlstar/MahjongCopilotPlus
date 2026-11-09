# 一番街协议桥接来源

日期：2026-11-05。参考 [Akagi v3 src/bridge/riichi_city](https://github.com/shinkuan/Akagi/tree/v3/src/bridge/riichi_city)，版权为 2026 Shinkuan，Apache 2.0。上游分支会变动，以下 SHA256 记录本次读取的原始参考文件，避免把“v3”误当作固定提交或最新兼容保证。原始文件未整份复制进入本仓库。

| 上游文件 | 本次参考内容的 SHA256 |
| --- | --- |
| `mod.rs` | `2b2863e18cff138d5e5f58dc4580ad95815ca485b8b76af913def3bf3dbd9c8a` |
| `packet.rs` | `20ff8c0f701bb0437973a1beeb5bbda042774ee942b7c9c9be07fb7307163eb7` |
| `consts.rs` | `e7eeb9180615a5e06b53d52fa937cda440c0d051bb32ead5e72584ea2e3fc327` |
| `state.rs` | `cdc811bf50d3e50b374295f5cf33d03f14e4fd8963d4a847e6236622085a2fae` |
| `README.md` | `0a8cb5d1488237b67000320e925fd190f942d2a954dc29cd2a4e35b7d094fdfc` |

Plus 将帧格式、牌编码及通知→MJAI 行为改写为 Python，并添加客户端方向校验、不猜测身份／暗杠赤牌、重复通知抑制、服务端决策窗口、错误冻结与模型核验衔接。新的捕获适配和本地外部进程管理由 Plus 实现。许可见 [Apache 2.0](../../LICENSES/Apache-2.0.txt) 和[上游 NOTICE](../../LICENSES/Akagi-NOTICE.txt)。

外部工具资料：[RiichiCityUnlock](https://github.com/Avenshy/RiichiCityUnlock)、[proxinject](https://github.com/PragmaTwice/proxinject)。前者仅通过现有 HTTP 入口运行，未反编译或复制源码；后者使用公开命令行启动本程序所属的游戏，不纳入二进制分发。独立游戏客户端不随仓库分发。
