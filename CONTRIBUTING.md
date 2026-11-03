# 贡献指南

欢迎提交可复现的错误、界面改进和平台适配。请先阅读 [README](readme.md)、[更新记录](CHANGELOG.md) 和[第三方许可说明](THIRD_PARTY_NOTICES.md)。

## 开发环境

当前以 Windows x64、Python 3.11 为主要环境。按[安装说明](docs/INSTALL.md)建立虚拟环境并安装依赖，先用临时配置或离线预览验证修改。

```powershell
.\venv\Scripts\python.exe tests/desktop_preview.py
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe tests/desktop_smoke.py
.\venv\Scripts\python.exe tests/native_desktop_smoke.py
.\venv\Scripts\python.exe scripts/check_publication.py
```

原生检查需要 Windows 桌面会话和已安装的 Chromium；不需要游戏账户。修改影响协议、保存、热键或退出时，应运行相关检查；文档小改无需重复整个桌面测试。

## 提交修改

- 保持单个 PR 聚焦，说明触发问题、修改后的行为及实际验证范围。
- UI 改动可附离线示例截图；不要暴露游戏账号、API Key、Token、证书或个人目录。
- 保持 AI、游戏捕获与界面分层，不在 UI 线程执行模型加载或网络请求。
- 保留上游版权及许可，不把规划中的功能写为已经支持。
- 引入第三方内容时，记录确切来源、版本、许可与分发要求。

提交的原创修改应可依本项目适用的开源许可分发；带入的第三方内容仍按其原始许可处理。无需签署额外的版权转让协议。
