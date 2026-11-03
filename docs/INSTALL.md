# 安装与排错

## Windows 便携预览包

在 Releases 下载 `MahjongCopilotPlus-0.1.0-preview.1-windows-x64.zip`，完整解压到可写目录，运行 `MahjongCopilotPlus.exe`。不需要另装 Python，保留 `_internal` 与其他文件。首次运行请自行配置 AI 服务或权重。

本包包含固定版本的四麻原生引擎及对应源码，见 [依赖来源](SOURCE_PROVENANCE.md)。三麻扩展、客户端注入程序、模型与账号不在包中。下面的 Python 安装步骤仅适用于源码运行。

## 推荐环境

当前主要验证环境为 Windows x64、Python 3.11。请使用 64 位 Python，并让虚拟环境、原生库和模型版本互相匹配。Qt 桌面与全局老板键的其他系统支持尚未验证。

从项目根目录运行：

```powershell
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m playwright install chromium
.\venv\Scripts\python.exe -m pip check
.\venv\Scripts\python.exe desktop_entry.py
```

之后可以使用 `start.bat`。如果启动失败，先从终端执行最后一条命令，查看 `log/desktop-startup-error.log`。BAT 本身不会安装 Python、依赖或浏览器。

## AI 配置

在“设置 → AI 连接”选择来源。AkagiOT 需要 `/check` 等接口与当前适配兼容的服务和 API Key；MJAI 使用已有用户名／账户密钥。不要把某个同名软件的任意服务地址直接视为兼容接口。

本地模型需要兼容当前 Mortal 结构的权重。四麻与三麻分别设置，可只配置一个模式。通过“浏览…”选择文件后点击“验证模型”；仅改名并不能解决模型结构或原生库不兼容。

配置表单与正在运行的 AI 分开管理。正在对局时保存的新配置会延后加载；不要仅凭下拉框已切换就判断新 AI 已经生效。

## 四麻原生库

本源码工作树不再分发从上游 Git 历史继承的 `libriichi.pyd`。程序会在本地扩展不可用时使用通过依赖安装的 `riichi`。依赖文件保留了 [Akagi 的 riichi 0.1.1 发布源](https://github.com/shinkuan/Akagi/releases/tag/v0.1.1-libriichi)。

如包源没有匹配的 wheel，可从该发布页取得与你的 Python 版本、操作系统与架构对应的 `riichi` wheel，再用虚拟环境中的 `python -m pip install <文件路径>` 安装。不要安装来源不明的二进制。

## 三麻原生库

三麻还需要独立的 `libriichi3p` 扩展，适用于使用它构造状态／观测的 AI 路径，并不只限于本地权重。

Windows x64、Python 3.11 对应的预期路径是：

```text
libriichi3p/libriichi3p-3.11-x86_64-pc-windows-msvc.pyd
```

本仓库不附带此文件，也不自动从非公开渠道获取。请按上游 [MahjongCopilot 帮助](https://mjcopilot.com/help) 和 [Akagi](https://github.com/shinkuan/Akagi) 的说明取得兼容、允许使用的版本，并查阅其实际分发条款。不要把其他名字／模块导出的 `.pyd` 简单改名；模块名或 ABI 不一致仍会加载失败。

没有这个扩展时，可先使用四麻。模型权重和三麻原生库的获取权限、商业条件及再分发授权不由本项目授予。

## 代理证书与外部客户端

网页版连接使用程序启动的 Chromium 和本地代理。初次运行可能需要建立／信任代理证书；若系统提示安装失败，参考程序诊断信息处理，仅信任你自己在本机生成的证书。不要分享 `mitm_config` 下的私钥。

默认代理端口为 `10999`。端口占用、上游代理、浏览器地址等在“设置 → 高级 → 连接与代理”调整；保存后重新打开游戏连接。配置页内的“浏览器与客户端设置”可展开更多选项。

Windows 外部客户端注入是可选能力。使用前需单独安装 [proxinject](https://github.com/PragmaTwice/proxinject) 对应版本，将其 CLI 及依赖放入 `proxinject/`，保留其原许可。源码不附带该程序；网页版不需要它。外部客户端的具体游戏版本仍需单独验证。

## 装扮配置与更新

默认模板在 `mjmax/config/settings.example.yaml`。私人覆盖文件为同目录的 `settings.yaml`；程序内扩展开关会写入它。游戏内装备选择保存到 `settings.mod.yaml`。

默认使用随源码附带的协议／资源快照，避免启动时强制联网更新。手动更新命令：

```powershell
.\venv\Scripts\python.exe -m mjmax.plugin.data_update
```

更新器校验结构与协议，失败时保留已验证的本地数据。使用 GitHub Token 时，只写入被 Git 忽略的私人 `settings.yaml`。

## 常见问题

- **界面能启动但 AI 未加载**：先准备有效服务凭据或模型；程序不附送账户或权重。
- **三麻导入失败**：核对 Python 版本、x64 架构、文件名、模块导出与实际支持的模型版本。
- **Chromium 找不到**：使用同一个虚拟环境执行 `python -m playwright install chromium`。
- **窗口改变后提示缩放**：手动模式不会将 Windows 缩放当成阻断错误；自动打牌／自动加入可能受显示比例影响，应在合适场景验证。
- **老板键不工作**：系统可能已注册该组合。设置中更换预设或自定义键，诊断页可查看注册状态。
- **资源下载慢**：按[资源下载与直连排查](NETWORK.md)比较同一资源、缓存条件和 TUN 分流；流式转发减少缓冲等待，不能保证修复线路吞吐。

## 运行数据

`settings.json`、`mjmax/config/settings*.yaml` 的私人文件、`browser_data/`、`mitm_config/`、`log/`、模型与下载的原生库属于本地数据。共享配置时使用示例文件，先清空凭据和个人信息。
