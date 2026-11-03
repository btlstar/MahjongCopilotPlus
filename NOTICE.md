# 项目来源与修改声明

MahjongCopilotPlus 由 btlstar 维护，是在以下开源项目基础上继续开发的派生项目，并非这些项目或游戏平台的官方版本。

## 上游

- MahjongCopilot — Copyright (C) 2024 Latorc；保留 `main.py` 中原有声明和根目录 GPL v3 许可证。
- 当前 Git 历史来自 `latorc/MahjongCopilot`，本次迁移前基线为提交 `31be3de`。没有重写或清空上游历史。
- MahjongCopilot-max — jiboyingg 维护的整合版本，是本项目 Copilot／MajsoulMax 整合方向的参考来源。
- MajsoulMax — Avenshy；本次集成参考 `v2026.07.07` 的模块逻辑，并使用 MajsoulData 资源与协议快照。

## Plus 的主要修改

2026-11-03 整理的修改包括：

- 将桌面从 Tk 界面改为 Qt 深色界面，重排导航、设置、连接配置、诊断与帮助。
- 新增统一的麻将牌呈现、游戏内提示拖动和位置保存，以及两键预设老板键；后续简化为单一游戏内提示开关。
- 改进窗口适配、手动模式下的显示缩放提示和大文件转发。
- 更新装扮模块及动态协议适配、消息处理和资源更新校验。
- 增加离线回归与原生窗口检查，整理安装、发布和贡献文档。
- 发布目录剔除个人运行数据与原生二进制，使用无凭据示例配置，调整打包逻辑以避免嵌入用户设置。

详细行为与边界见 [CHANGELOG.md](CHANGELOG.md)。变更文件中保留原有版权文字；修改标记不表示 Plus 对上游内容享有独占版权。

## 名称与资产

MahjongCopilotPlus 仅表示本派生项目。游戏名称、角色、美术、音频、协议所涉及的权利及第三方标识仍属于相应权利人。本项目的代码许可不授予这些素材或标识的额外使用权。

第三方具体范围与许可证见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
