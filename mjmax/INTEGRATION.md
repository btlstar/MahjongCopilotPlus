# MajsoulMax 集成说明

本模块是 MahjongCopilotPlus 中的 MajsoulMax 适配层，不是独立的官方 MajsoulMax 发布。

## 来源与快照

- 模块逻辑基于 [Avenshy/MajsoulMax](https://github.com/Avenshy/MajsoulMax) 的 `v2026.07.07` 集成。
- 协议和资源来自 [MajsoulData 0.16.289-4.0.51](https://github.com/Avenshy/MajsoulData/releases/tag/0.16.289-4.0.51)。
- 内置表记录 125 个角色、516 套皮肤、166 个称号、519 项装扮、286 张加载插图及 166 个传记结局；记录数量不等同于账号拥有数量，也不保证所有记录均为当前正式可获取物品。
- 精确来源、数量和 SHA256 见 [config/data_version.json](config/data_version.json)。

## 私人设置

源码只包含无凭据的 `config/settings.example.yaml`。未创建私人文件时按该模板读取；本地覆盖为 `config/settings.yaml`。

游戏内选择写入 `config/settings.mod.yaml`，未创建时生成默认配置。角色、皮肤、称号、星标、加载图、装扮页与随机角色选择均为用户本地数据，不随仓库发布。

装扮页的扩展开关会保存启用配置。关闭游戏浏览器后，后台重新建立代理时加载变化。GUI 的搭配参考不提供批量应用；不会为用户改写现有装扮页。

## 更新资源与协议

默认关闭启动时自动更新，使用随源码提供的快照。需要时先退出程序，再运行：

```powershell
.\venv\Scripts\python.exe -m mjmax.plugin.data_update
```

更新器配套取得 `max_data.yaml` 与 `liqi.desc`，校验结构、描述池和可用摘要后安装，失败则保留本地数据。`--force` 可重新下载。

需要自动更新时，在私人 `config/settings.yaml` 中配置 `liqi.auto_update: true`。可选 GitHub Token 只能放在私人文件中，不要改动公开模板。

## 同步上游逻辑

上面的更新命令只更新 MajsoulData 的资源表与协议，不会下载或替换 `plugin/mod.py`。语音选择、消息处理等适配属于代码；单独更新资源不能自动获得上游逻辑修复。

维护者同步上游 MajsoulMax 时：

1. 记录目标 tag／commit，并与当前 `v2026.07.07` 基线比较 `plugin/mod.py`、`addons.py` 和协议处理的变化，逐项合入适配层。
2. 保留 Plus 的导入路径、动态协议类、逐连接请求编号、Copilot 先读原始消息、错误与未知消息透传等改动。不能直接整目录覆盖 `mjmax/`，也不能复制上游私人配置。
3. 若新逻辑依赖新协议字段，再配套更新资源与协议，核对 `data_version.json` 的摘要、数量及来源；记录实际已合入的上游版本，不把数据版本当作代码版本。
4. 运行 `python -m unittest discover -s tests -p test_mjmax_integration.py` 及受影响的捕获／界面检查；友人房至少验证创建、主动加入、重连、其他玩家变化和准备／取消准备。
5. 上游修复与本地补丁重叠时，先比较行为并让回归通过，再合并为一种实现。提交对应源码、变更记录和 Summary／Description；不替换个人 `settings*.yaml`。

普通用户在维护者完成合入后，关闭程序与游戏浏览器，在同一仓库 Pull，然后用 `start.bat` 启动；仅在依赖变化时更新依赖。不需要再维护一份独立 Max 安装目录。

## 本地友人房适配

友人房资料原先存在两个缺口：`NotifyRoomPlayerUpdate` 仅替换头像，仍保留服务器返回的角色 ID／皮肤；`joinRoom` 的返回没有换肤处理。当前统一创建、主动加入、获取房间与玩家更新的处理，使自己的 `avatar_id`、`character.charid` 和 `character.skin` 保持一致。

`NotifyRoomPlayerReady` 只有账号、准备状态等数据，不携带角色；补丁更新房间中可供客户端复用的角色资料，不伪造准备消息，也不改服务器上的装备。只影响自己的本地呈现；其他玩家资料除既有服务器前缀／地铁模式外保持不变，未知 protobuf 字段保留。

离线回归确认了身份一致、准备通知原样通过、未知字段保留及失败响应透传。新增语音实际是否使用这些字段、特定角色是否有对应语音资源，仍需当前游戏版本中试听确认；本次没有登录真实账号验证播放结果。

## 适配改动

- 动态协议描述池及与 Copilot 所需接口的适配，避免新旧 protobuf 冲突。
- 每个 WebSocket 独立跟踪请求编号，关闭时清理。
- Copilot 先读取原始对局消息，再处理本地装扮修改。
- 保留服务端错误与未知消息，避免装扮适配中断正常捕获。
- 处理新角色、额外表情、牌谱换肤、地铁模式等兼容情况。

## 验证与边界

离线回归使用当前协议生成消息，覆盖登录、角色／皮肤、换肤、多连接、对局／牌谱、用户设置迁移、资源校验与更新回滚。真实游戏版本及新资源加载仍需相应验证，不作账号安全或持续兼容承诺。

上游署名、许可及游戏资产边界见根目录 [第三方说明](../THIRD_PARTY_NOTICES.md)。
