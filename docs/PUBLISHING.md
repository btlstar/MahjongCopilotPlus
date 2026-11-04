# v0.1.0-preview.2 发布步骤

本地已准备 Windows x64 便携预览包。Commit、Push 与 Release 是三个不同动作；本次整理不会代你执行这些动作。

## GitHub Desktop

1. 选择 `MahjongCopilotPlus` 仓库，确认当前分支是 `main`。
2. 查看 Changes，保留 Akagi v3 模型选择及本次发布文件的全部改动。个人配置、模型、证书、缓存与 `dist/` 不应出现在待提交列表。
3. 执行 `python scripts/check_publication.py`，确认检查通过。
4. 填写下面的 Summary，Description 可选，然后点击 **Commit to main**。这只在本地创建提交，不会上传 GitHub。
5. 点击 **Push origin**，将源码提交推送到 `btlstar/MahjongCopilotPlus`。不要推送到上游 Copilot。

Summary：

```text
发布 MahjongCopilotPlus v0.1.0-preview.2
```

Description：

```text
新增 Akagi v3 接口，分别指定四麻和三麻模型。
预设 4p-akg-v8b-preview 与 3p-akg-v9，支持获取授权模型列表。
区分连接检查与实际模型回报，保留旧版 OT 配置。
更新便携包、升级说明与离线打包验收。
```

## GitHub Release

1. 推送完成后打开仓库网页 → Releases → Draft a new release。
2. 新建 tag：`v0.1.0-preview.2`，Target 选择刚推送的 `main`，确认提交包含本次所有改动。
3. 标题：`MahjongCopilotPlus v0.1.0-preview.2`。正文复制 [RELEASE_NOTES.md](RELEASE_NOTES.md) 的内容。
4. 上传 `dist/release-0.1.0-preview.2/` 下准备的 Windows zip、应用源码 zip、引擎源码 zip、`SHA256SUMS.txt` 和验收记录。不上传整个开发目录，不将便携包加入 Git 提交。
5. 勾选 **This is a pre-release**。检查附件、许可和正文后，先 Save draft 或直接 Publish release。

运行包必须完整解压。一个主程序入口不代表可以只分发孤立 exe；Chromium 等组件会保留自己的辅助进程文件。模型、API 账户、本地三麻扩展和外部客户端注入组件不随此包分发；Akagi v3 三麻不依赖该本地扩展。

## 后续重建

使用 Python 3.11 x64 与 `requirements.txt`，然后：

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = '0'
.\venv\Scripts\python.exe -m playwright install chromium
.\venv\Scripts\python.exe scripts/fetch_engine.py
.\venv\Scripts\python.exe scripts/build_desktop.py
.\venv\Scripts\python.exe scripts/assemble_release.py
```

默认输出 `dist/MahjongCopilotPlus/`，现有目录不会被覆盖。引擎和对应源码使用固定 SHA256；校验失败应核对上游，不能直接换成未经确认的文件。

每次重建都要在新的解压目录运行 exe 自检并重新生成校验值，不要沿用前一版本的测试记录。本轮检查未登录真实游戏或使用个人 AI 服务凭据。

GitHub 官方说明：[Desktop 提交与推送](https://docs.github.com/en/desktop/making-changes-in-a-branch/committing-and-reviewing-changes-to-your-project-in-github-desktop)、[创建 Release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)。
