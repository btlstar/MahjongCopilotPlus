# 安装与排错

## 分发方式

后续仅维护源码，通过 `start.bat` 启动，不再构建或上传 exe／Windows 便携包。历史 exe 为固定快照，不会随源码更新。使用者需要自行安装 Python、依赖和浏览器；BAT 不会代为安装这些组件。

建议通过 GitHub Desktop Clone 后在同一个工作目录持续更新。旧版用户先阅读[升级说明](UPGRADING.md)，避免继续打开旧 exe 或另一份源码。

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

在“设置 → AI 连接”选择来源。MJAI 使用已有用户名／账户密钥。AkagiOT 的两种接口分别保存地址与密钥：

- **Akagi v3 · 可选模型**：默认服务根地址为 `https://mjapi.shinkuan.me`，使用对应的 v3 API Key。新配置不预置型号；先点击“获取可用模型”，在上方四麻／三麻下拉框选择密钥获准使用的型号，再点击“保存配置”。至少选择一个玩法的模型，另一个留空则不启用该玩法；不会自动采用服务端默认。也可手动填写有效 ID。指定 ID 不可用时会报错，不会偷偷降级。
- **旧版 OT · 服务端默认**：兼容原有 `/check`、`/react_batch`、`/react_batch_3p` 接口。该适配没有模型选择参数；授权通过不能确认实际模型，也不能据此判断其强弱。客户端会读取推理 JSON 的 `model`／`model_id`／`model_name` 或模型响应头 `X-Model`／`X-Model-ID`／`X-Model-Name`；只有服务端明确回报且无冲突才显示具体模型。没有回报时保持未确认，不根据观测维度或客户端版本推断。原配置升级后仍保留此接口，不自动迁移到新服务。

密钥输入框右侧的眼睛图标可显示／隐藏内容；默认隐藏，切换来源、接口或离开 AI 设置时恢复隐藏，不改变已输入的值。

Akagi 新旧接口的连接测试、模型列表和推理不再自动使用系统／环境代理；游戏“上游代理”是另一条独立配置。TUN 仍可能接管 AI 连接，需要在 Mihomo 等客户端为 AI 域名添加 DIRECT 规则，详见[网络说明](NETWORK.md#akagiotakagi-v3-始终选择直连出站)。

v3 支持同源 HTTP 重定向，推理 POST 仅跟随保留方法的 307／308；不会自动向其他域名、端口或较低安全协议转发密钥。跨源跳转时会显示目标站点供核对。若显示 HTML 网页／网络防护错误，说明没有收到正常 API JSON，不能直接当作密钥授权失败。原版 Copilot 的代理启动、证书或本地模型缺失错误与 API 重定向是不同问题。

“获取可用模型”只更新下拉列表，并提示选择、保存，不会自动选中第一个型号。“测试连接”检查授权与所选型号，只显示检查结果；测试未保存的表单不会切换正在运行的 AI。

底部状态栏显示当前已加载的型号，窗口较窄时可悬停查看完整名称。最近一次服务端推理回报与相关错误放在“诊断”中，不在配置表单重复显示。连接测试不执行推理；真实牌局收到服务端 `model` 回报后才确认实际模型，回报与指定 ID 不符时拒绝该建议。尚无模型 ID 仅表示未收到明确回报，不等于加载失败。

已有保存的型号在升级后保留，但不代表最新或最强。服务新增型号后，重新获取列表并手动选择、保存；实际可用模型由密钥套餐与服务端决定。

接口依据上游 [v3 API 实现](https://github.com/shinkuan/Akagi/blob/v3/src/bot/api.rs) 与 [默认配置](https://github.com/shinkuan/Akagi/blob/v3/src/config/bot.rs) 适配；旧版和 v3 的密钥不保证通用。不要把任意同名软件的服务地址视为兼容接口，也不要在聊天或 Issue 中公开密钥。

本地模型需要兼容当前 Mortal 结构的权重。四麻与三麻分别设置，可只配置一个模式。通过“浏览…”选择文件后点击“验证模型”；仅改名并不能解决模型结构或原生库不兼容。

配置表单与正在运行的 AI 分开管理。保存后会显示加载成功或具体失败原因；正在对局时提示对局结束后加载，完成后自动更新结果。不要仅凭下拉框已切换就判断新 AI 已经生效。

## 四麻原生库

本源码工作树不再分发从上游 Git 历史继承的 `libriichi.pyd`。程序会在本地扩展不可用时使用通过依赖安装的 `riichi`。依赖文件保留了 [Akagi 的 riichi 0.1.1 发布源](https://github.com/shinkuan/Akagi/releases/tag/v0.1.1-libriichi)。

如包源没有匹配的 wheel，可从该发布页取得与你的 Python 版本、操作系统与架构对应的 `riichi` wheel，再用虚拟环境中的 `python -m pip install <文件路径>` 安装。不要安装来源不明的二进制。

## 三麻原生库

本地模型与旧版 OT 的三麻需要独立的 `libriichi3p` 扩展，以构造状态／观测。**Akagi v3 直接发送 MJAI 事件，不需要此三麻扩展**；服务端与密钥仍须支持三麻。

Windows x64、Python 3.11 对应的预期路径是：

```text
libriichi3p/libriichi3p-3.11-x86_64-pc-windows-msvc.pyd
```

本仓库不附带此文件，也不自动从非公开渠道获取。请按上游 [MahjongCopilot 帮助](https://mjcopilot.com/help) 和 [Akagi](https://github.com/shinkuan/Akagi) 的说明取得兼容、允许使用的版本，并查阅其实际分发条款。不要把其他名字／模块导出的 `.pyd` 简单改名；模块名或 ABI 不一致仍会加载失败。

没有这个扩展时，可使用四麻或已授权的 Akagi v3 三麻。模型权重和三麻原生库的获取权限、商业条件及再分发授权不由本项目授予。

## 代理证书与外部客户端

网页版连接使用程序启动的 Chromium 和本地代理。初次运行可能需要建立／信任代理证书；若系统提示安装失败，参考程序诊断信息处理，仅信任你自己在本机生成的证书。不要分享 `mitm_config` 下的私钥。

默认代理端口为 `10999`。端口占用、上游代理、浏览器地址等在“设置 → 高级 → 连接与代理”调整；保存后重新打开游戏连接。配置页内的“浏览器与客户端设置”可展开更多选项。

仅需 Copilot 捕获游戏流量时，关闭“使用上游代理”并保存，游戏经本地 `10999` 拦截后直连；此操作会清空旧的上游地址，不会更改系统代理或 TUN。详细路径和最近连接失败见“诊断”，排查步骤见[网络说明](NETWORK.md)。

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
- **连接测试成功但没有游戏内建议**：确认底栏已加载的来源与型号、顶栏提示开关和对局状态。连接测试不执行推理；若底栏显示“建议异常”，打开诊断查看推理错误。Akagi v3 已兼容三麻 `kita` 拔北响应；旧版 OT 三麻仍需要本地 `libriichi3p`，切回 v3 并保存后不需要此扩展。网页刷新后提示层会自动重建，不需要重复获取模型。
- **三麻导入失败**：核对 Python 版本、x64 架构、文件名、模块导出与实际支持的模型版本。
- **Chromium 找不到**：使用同一个虚拟环境执行 `python -m playwright install chromium`。
- **浏览器启动信息条**：默认启用 Chromium 沙箱，并使用自动化测试启动标记跳过 Google API 密钥等启动信息条；不再传入 `--no-sandbox`。Google API 密钥与 AI 服务密钥无关，无需为雀魂或 AI 补填 Google Key。普通模式和加载扩展模式使用相同的启动策略，重启游戏浏览器后生效。
- **窗口改变后提示缩放**：手动模式不会将 Windows 缩放当成阻断错误；自动打牌／自动加入可能受显示比例影响，应在合适场景验证。
- **老板键不工作**：系统可能已注册该组合。设置中更换预设或自定义键，诊断页可查看注册状态。
- **资源下载慢**：按[资源下载与直连排查](NETWORK.md)比较同一资源、缓存条件和 TUN 分流；流式转发减少缓冲等待，不能保证修复线路吞吐。
- **网页打开失败／502**：可在原浏览器中刷新重试。程序会等待导航恢复，刷新时临时销毁 JS 环境不会再导致主动关窗；诊断可查看网页加载错误和转发路径。若浏览器进程本身被系统或外部软件终止，仍需重新打开。

## 运行数据

`settings.json`、`mjmax/config/settings*.yaml` 的私人文件、`browser_data/`、`mitm_config/`、`log/`、模型与下载的原生库属于本地数据。共享配置时使用示例文件，先清空凭据和个人信息。
