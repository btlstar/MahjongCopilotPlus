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

## 功能边界

友人房同步自身本地角色、皮肤与头像选择，不修改服务器装备；其他玩家资料沿用既有服务器前缀／地铁模式处理。新增角色及语音依赖当前客户端资源，语音覆盖不保证完整。未知消息和服务端错误保留。

上游署名、许可及游戏资源边界见根目录[第三方说明](../THIRD_PARTY_NOTICES.md)。
