# 源码版本发布流程

后续版本只提交和发布源码，用户自行安装依赖后运行 `start.bat`。不再执行 exe 打包，不再上传 exe、`windows-x64.zip` 或其他免安装运行包。已有便携产物是历史记录，不自动删除或改写。

## 本地准备与 GitHub Desktop

1. 固定使用 GitHub Desktop 管理的 `MahjongCopilotPlus` 工作目录，完成改动并查看全部差异。
2. 按影响范围执行检查；文档调整不需要重复完整的游戏／桌面测试。至少运行 `python scripts/check_publication.py`。
3. 功能版本更新 `version`、`CHANGELOG.md` 和发布说明；纯文档调整可记入“未发布”。
4. 每次更新都提供 Summary 和 Description。Summary 概括最终变化，Description 说明行为、验证与实际限制；当前可复制文案在 [COMMIT_MESSAGE.txt](COMMIT_MESSAGE.txt)。
5. Commit 创建本地提交；Push origin 上传源码。不要提交私人配置、证书、模型、虚拟环境、`build/`、`dist/` 或历史 exe。

## GitHub Release

1. 推送后创建 Release，选择与对应源码提交匹配的版本标签。
2. 填写标题与发布说明，明确“源码部署，安装依赖后通过 start.bat 启动”。预览版本勾选 pre-release。
3. 使用 GitHub 按标签提供的 Source code zip／tar.gz 即可，不再准备 Windows 二进制附件。源码标签应对应实际发布的代码。
4. 发布说明列出新增／修复、安装或迁移变化、检查结果与未验证场景。保留源码内原有版权、许可和第三方说明。

## 当前分发方式调整的提交文案

Summary：

```text
切换为源码发布并统一 BAT 开发入口
```

Description：

```text
后续版本仅维护源码，通过 start.bat 启动，不再构建或上传 exe。
更新 README、安装、升级、发布和开发目录说明。
统一使用 GitHub Desktop 管理的工作树，旧下载源码与历史 exe 停止更新。
从运行依赖移除 PyInstaller，保留历史构建来源记录。
```

历史打包脚本保留用于追溯旧产物，不属于后续发布步骤；不执行这些脚本，也不将其产物描述成当前推荐安装方式。
