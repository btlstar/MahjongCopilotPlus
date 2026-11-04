# 后续发布方式：仅源码

从本次调整起，后续更新只发布源码，不再构建或上传 exe／Windows 便携包。使用者自行安装 Python、依赖和 Chromium，通过源码根目录 `start.bat` 启动。安装与迁移见 [INSTALL.md](INSTALL.md)、[UPGRADING.md](UPGRADING.md)。

固定使用同一个 Git 工作目录，历史 exe 不会随源码更新。每次版本更新均附 Summary 和 Description，发布流程见 [PUBLISHING.md](PUBLISHING.md)。本次仅调整分发与开发目录约定，没有新增游戏或 AI 行为。

---

以下为历史 preview.2 记录，不代表当前或后续版本仍提供便携包。

# MahjongCopilotPlus v0.1.0-preview.2

本次更新加入 Akagi v3 模型选择，保留原有深色 Qt 界面、雀魂对局提示及 MajsoulMax 集成。

## 主要变化

- 在“设置 → AI 连接 → AkagiOT”选择“Akagi v3 · 可选模型”。
- 四麻预设 `4p-akg-v8b-preview`，三麻预设 `3p-akg-v9`，可编辑 ID 或获取密钥获准使用的模型列表。
- 推理请求明确发送模型 ID；指定模型不可用时报错，不自动改用其他模型。留空才使用服务端默认。
- 连接检查与实际推理分开显示；服务端回报 `model` 后显示实际模型，回报不同 ID 则拒绝该建议。
- 旧版 OT 地址与密钥独立保留，不跨服务自动复用。v3 密钥与旧版 OT 不保证通用。
- Akagi v3 直接发送 MJAI 事件，三麻不需要本地 `libriichi3p`。

## 下载与升级

下载 `MahjongCopilotPlus-0.1.0-preview.2-windows-x64.zip`，完整解压到新目录，运行 `MahjongCopilotPlus.exe`。保留 `_internal` 等配套文件，不要只复制 exe。无需安装 Python，Chromium 已包含。

先关闭旧版和游戏浏览器，再按 [升级说明](UPGRADING.md) 保留配置。不要将新版示例配置覆盖旧版私人配置。旧配置仍使用原来的 OT 接口，需要手动切换到 v3、填写对应密钥并保存。

本包不包含模型权重、API 账户、本地三麻扩展或外部客户端注入组件；自动操作默认关闭。本地模型及旧版 OT 的三麻仍需额外扩展。

## 验证范围

52 项源码自动化测试覆盖真实本机 HTTP 协议、两种模型参数、雀魂消息到 AI 建议的离线流程、立直后续出牌、配置保留和其他既有功能。另执行 Qt／Chromium 交互、原生引擎检查、冻结 exe 自检及中文空格路径解压启动；具体结果见附件 `VALIDATION.json`。

打包自检使用模拟服务，没有使用真实服务密钥或账号验证线上推理。实际可用模型由服务端与套餐决定，预设 ID 不代表永久最新或最强。

## 源码与许可

应用源码归档、原生引擎对应源码、许可与 `SHA256SUMS.txt` 一并提供；便携包包含依赖声明与许可证。详见 `THIRD_PARTY_NOTICES.md` 和 `SOURCE_PROVENANCE.md`。
