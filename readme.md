# MahjongCopilotPlus

**简洁的麻将 AI 桌面工具：实时建议、统一提示窗与可选装扮扩展。**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20x64-0078D4)
![License](https://img.shields.io/badge/License-GPLv3-blue)
![Status](https://img.shields.io/badge/Status-Preview-orange)

MahjongCopilotPlus 在 [MahjongCopilot](https://github.com/latorc/MahjongCopilot) 的基础上持续开发，参考 [MahjongCopilot-max](https://github.com/jiboyingg/MahjongCopilot-max) 的整合思路，接入 [MajsoulMax](https://github.com/Avenshy/MajsoulMax)，并重构桌面界面、设置和提示体验。

当前支持 **雀魂三麻／四麻**。Akagi v3 三麻无需本地三麻扩展；本地模型与旧版 OT 的原生库要求见下文。天凤、一番街、天月麻将、掌心麻将仍在规划中，尚未实现。本项目与各游戏平台及上游项目没有官方隶属关系。

> **源码部署，通过 `start.bat` 启动。** 请先安装 Python 3.11 x64、依赖与 Chromium；不提供 exe／免安装运行包。更新与问题反馈请使用[本仓库](https://github.com/btlstar/MahjongCopilotPlus)。

![对局页：AI 建议、当前手牌及底部已加载型号](assets/screenshots/game.png)

截图基于 `v0.1.0-preview.3` 的实际界面，以离线演示数据生成；`4p-demo-model`／`3p-demo-model` 为虚构示例，不是可用型号、默认型号或最新型号推荐。

## 当前版本

`v0.1.0-preview.3`：完善 AI 连接与模型状态，修复刷新后的游戏内提示恢复及网络异常时程序误关浏览器的问题。详见[本次发布说明](docs/RELEASE_NOTES.md)与[更新记录](CHANGELOG.md)。

## 特性

- **深色桌面界面**：Qt 紧凑顶栏，“对局／装扮／设置”三个主页面，设置、帮助、诊断和连接配置均在程序内显示。
- **统一麻将牌样式**：万、筒、索分别用红、蓝、绿区分，赤五有额外标记；主界面与游戏内提示一致。
- **简洁提示**：只保留游戏内卡片，可拖动并记住位置；顶栏与设置页开关即时同步，关闭后仍可在主界面查看建议。
- **两键老板键**：默认推荐 `Alt+Q`，另有 `Alt+Z`、`Alt+X` 和自定义选项，隐藏／恢复程序及它启动的游戏浏览器。
- **多种 AI 来源**：AkagiOT、MJAI、兼容的本地 Mortal 模型；根据来源显示对应设置，本地模型可浏览选择文件。Akagi v3 支持获取授权列表后手动选择四麻／三麻型号；底栏显示已加载型号，推理回报可在诊断中查看。
- **可选装扮扩展**：MajsoulMax 集成、资源和协议更新，以及搭配参考；当前不提供从 GUI 批量应用或对局中即时换装。
- **窗口适配**：游戏窗口可调整大小；手动操作模式不再因 Windows 显示缩放反复弹出 100% 缩放错误。
- **自动操作保留**：自动打牌、自动加入和定时停止归入高级设置，默认关闭。

<details>
<summary>更多界面截图</summary>

AI 连接设置：密钥显隐、按玩法选择型号、获取列表与测试连接。

![AI 连接设置，使用虚构型号与隐藏的演示密钥](assets/screenshots/ai.png)

游戏内提示卡片（局部截图）：与主界面共享麻将牌样式，整张卡片可拖动，不另开独立窗口。

![实际游戏内 HTML 提示卡片，离线渲染](assets/screenshots/overlay.png)

程序内连接配置：本地端口与上游代理分开设置，图中为关闭上游代理。

![连接与代理](assets/screenshots/proxy.png)

装扮搭配参考：在游戏内逐项装备，不支持 GUI 一键应用。

![装扮页](assets/screenshots/wardrobe.png)

截图不包含个人账号、真实密钥或私人对局，也不表示已连接线上服务。

</details>

## 快速开始

### 运行环境

- Windows x64，建议使用 **Python 3.11 x64**。当前桌面和老板键验证以 Windows 为主。
- 可访问 Python 包源及 Playwright Chromium 下载源。
- 至少一种可用 AI 来源；本仓库不附带 API Key、账户或模型权重。

### 获取源码

推荐通过 GitHub Desktop Clone 本仓库，后续在同一目录 Pull 更新。也可下载 Release 的 `Source code (zip)` 后安装依赖；该文件仅包含源码。

更新及旧版配置迁移见[升级说明](docs/UPGRADING.md)；参与开发请参阅[工作目录约定](docs/WORKSPACE.md)。

### 源码安装与启动

在 PowerShell 中执行：

```powershell
git clone https://github.com/btlstar/MahjongCopilotPlus.git
cd MahjongCopilotPlus
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m playwright install chromium
.\venv\Scripts\python.exe desktop_entry.py
```

完成安装后，可双击根目录 **`start.bat`**。它使用项目内的 `venv`，不是免安装启动器。

首次启动会生成本地 `settings.json`。以 Akagi v3 为例：

1. 打开“设置 → AI 连接”，选择 `AkagiOT` 和 `Akagi v3 · 可选模型`，填写对应 API Key。
2. 点击“获取可用模型”，在四麻／三麻下拉框选择所需型号；至少选择一种玩法，留空的玩法不启用。
3. 测试连接后保存，等待底部状态栏显示就绪及已加载型号。测试通过只代表连接与授权检查通过。
4. 点击“打开游戏”，在程序启动的浏览器中进入对局。顶栏“游戏内提示”控制游戏内卡片；没有建议时可从右下角“诊断”查看原因。

如果显示代理证书安装错误，按[安装与排错说明](docs/INSTALL.md)处理。不要将程序生成的证书私钥、浏览器资料或含凭据的设置文件提交到 GitHub。

### AI 与原生库

| 来源 | 需要准备 |
| --- | --- |
| Akagi v3（AkagiOT 来源） | 对应服务的 API Key；获取授权列表后手动选择四麻／三麻型号；三麻无需本地扩展 |
| 旧版 OT（AkagiOT 来源） | 兼容旧接口的地址与密钥；使用服务端默认型号，三麻需要额外原生库 |
| MJAI | 服务地址、已有账户的用户名和密钥，以及可用模型 |
| 本地 Mortal | 与当前引擎兼容的权重；四麻与三麻分别选择文件 |

本地模型和旧版 OT 的四麻原生依赖通过 `requirements.txt` 中的 `riichi` 安装；其三麻还需单独取得匹配 Python 版本、系统和架构的 `libriichi3p`，它不随本源码仓库分发。**Akagi v3 使用服务端推理，三麻无需该本地扩展。**具体文件名和注意事项见[安装说明](docs/INSTALL.md#三麻原生库)。模型权重和外部原生库始终遵循其原始分发条款。

不同来源与新旧 Akagi 接口分别保存配置，密钥不保证通用。切换来源只切换表单；保存后的新模型在非对局状态加载，对局中更改延后至当前对局结束。详见[AI 配置说明](docs/INSTALL.md#ai-配置)。

## 装扮扩展

内置集成基于 MajsoulMax `v2026.07.07`，资源／协议快照为 MajsoulData `0.16.289-4.0.51`。准确版本、来源和校验值见 [data_version.json](mjmax/config/data_version.json)，更新方式见[集成说明](mjmax/INTEGRATION.md)。这不是“永久支持所有最新皮肤”的保证。

装扮在游戏内选择，个人选择写入被 Git 忽略的本地配置。GUI 中的搭配为参考，不会自动替换你的装备。修改效果属于本地客户端显示，不会给账号增加服务器端拥有的物品。

## 功能范围与使用提示

| 平台 | 当前状态 |
| --- | --- |
| 雀魂 | 已接入；模型、原生库和游戏协议版本需匹配 |
| 天凤、一番街 | 规划中 |
| 天月麻将、掌心麻将 | 规划中 |

这是学习、研究与个人实验项目。请遵守游戏平台规则，避免破坏公平对局；AI 实时辅助、自动操作或客户端修改可能导致账号处罚。项目不保证规避检测，不提供账号安全或胜率保证。

程序按许可证规定以“现状”提供。游戏素材、商标、模型权重及第三方服务不因本项目开源而获得额外授权。

## 文档与开发

- [安装与排错](docs/INSTALL.md)
- [开发目录与启动入口](docs/WORKSPACE.md)
- [升级与配置迁移](docs/UPGRADING.md)
- [资源下载与 TUN／直连排查](docs/NETWORK.md)
- [桌面使用说明](DESKTOP.md)
- [MajsoulMax 集成与数据更新](mjmax/INTEGRATION.md)
- [贡献指南](CONTRIBUTING.md)
- [更新记录](CHANGELOG.md)
- [当前版本发布说明](docs/RELEASE_NOTES.md)
- [源码发布流程](docs/PUBLISHING.md)
- [第三方来源与许可](THIRD_PARTY_NOTICES.md)

离线检查：

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe tests/desktop_smoke.py
.\venv\Scripts\python.exe tests/native_desktop_smoke.py
.\venv\Scripts\python.exe scripts/check_publication.py
```

重新生成 README 截图：`python scripts/capture_readme.py`。该工具使用临时配置和虚构型号渲染真实 Qt／HTML 组件，不启动真实游戏、代理或 AI 后端，不注册老板键，也不读取个人设置。

桌面检查会打开临时的离线测试窗口，不登录真实游戏。源码预览通过离线检查不代表所有游戏版本、服务接口或自动点击场景均经过实战验证。

## 鸣谢

- [latorc/MahjongCopilot](https://github.com/latorc/MahjongCopilot)：上游程序、AI 接口、捕获与自动操作基础。
- [jiboyingg/MahjongCopilot-max](https://github.com/jiboyingg/MahjongCopilot-max)：Copilot 与 MajsoulMax 的整合参考。
- [Avenshy/MajsoulMax](https://github.com/Avenshy/MajsoulMax)、[MajsoulData](https://github.com/Avenshy/MajsoulData)：装扮模块、协议和资源快照。
- [Equim-chan/Mortal](https://github.com/Equim-chan/Mortal)、[shinkuan/Akagi](https://github.com/shinkuan/Akagi)：模型结构、引擎与相关工作。
- [MahjongRepository/mahjong_soul_api](https://github.com/MahjongRepository/mahjong_soul_api)、[747929791/majsoul_wrapper](https://github.com/747929791/majsoul_wrapper)、[MJAI](https://mjai.app/)：协议和实现参考。
- [PragmaTwice/proxinject](https://github.com/PragmaTwice/proxinject)、Qt for Python、Playwright、mitmproxy 及其他依赖的贡献者。

## 许可证

项目沿用上游的 **GNU GPL v3**，原文见 [LICENSE](LICENSE)，原作者版权声明予以保留。Mortal 派生部分及外部原生库、Qt、代理组件等另有适用条款，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；主许可证不会替它们重新授权。

本项目不附加“禁止商用”或“下载后 24 小时内删除”等限制。复制、修改、再分发时应遵守实际适用的许可证，并保留相应源码、署名和许可说明。

---

**English:** MahjongCopilotPlus is a community-maintained MahjongCopilot derivative with a redesigned dark Qt desktop, consistent tile rendering, draggable advice overlays, configurable global hotkeys, and optional MajsoulMax integration. Mahjong Soul is currently supported; other platforms are planned. Model weights, credentials and optional three-player/client-injection dependencies are not bundled. Distributed as source only; install Python, dependencies and Chromium, then launch with start.bat. See the license and third-party notices before redistribution.
