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

## 更新

默认关闭启动时自动更新，使用随源码提供的快照。需要时先退出程序，再运行：

```powershell
.\venv\Scripts\python.exe -m mjmax.plugin.data_update
```

更新器配套取得 `max_data.yaml` 与 `liqi.desc`，校验结构、描述池和可用摘要后安装，失败则保留本地数据。`--force` 可重新下载。

需要自动更新时，在私人 `config/settings.yaml` 中配置 `liqi.auto_update: true`。可选 GitHub Token 只能放在私人文件中，不要改动公开模板。

## 适配改动

- 动态协议描述池及与 Copilot 所需接口的适配，避免新旧 protobuf 冲突。
- 每个 WebSocket 独立跟踪请求编号，关闭时清理。
- Copilot 先读取原始对局消息，再处理本地装扮修改。
- 保留服务端错误与未知消息，避免装扮适配中断正常捕获。
- 处理新角色、额外表情、牌谱换肤、地铁模式等兼容情况。

## 验证与边界

离线回归使用当前协议生成消息，覆盖登录、角色／皮肤、换肤、多连接、对局／牌谱、用户设置迁移、资源校验与更新回滚。真实游戏版本及新资源加载仍需相应验证，不作账号安全或持续兼容承诺。

上游署名、许可及游戏资产边界见根目录 [第三方说明](../THIRD_PARTY_NOTICES.md)。
