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

## 本次发布：v0.1.0-preview.3

- Tag：`v0.1.0-preview.3`，对应根目录 `version` 中的 `0.1.0-preview.3`。
- Release 标题：`MahjongCopilotPlus v0.1.0-preview.3 · AI 连接与浏览器恢复`。
- GitHub Desktop 的 Summary／Description：复制 [COMMIT_MESSAGE.txt](COMMIT_MESSAGE.txt) 中对应内容，不复制字段标签。
- Release 正文：复制 [RELEASE_NOTES.md](RELEASE_NOTES.md)，勾选 **Set as a pre-release**，不上传二进制附件。

GitHub Desktop 中先审阅 Changes，再填写 Summary 和 Description 并 Commit；Commit 只记录到本地。随后点击 Push origin。到 GitHub Releases 创建新发布，在 Create new tag 中填写上述 tag，确认 Target 是刚推送的源码提交，再发布。

不要把 tag 指向旧提交或仅存在于本地的未提交修改。GitHub 自动生成的源码压缩包只包含该 tag 的 Git 内容，不会包含被忽略的本机设置和环境；若误将私人文件加入暂存区，应先取消并排除，不能仅依赖 .gitignore 隐藏已跟踪文件。

当前发布说明已使用本次 tag 的仓库绝对链接，可直接粘贴为 GitHub Release 正文；这些链接在对应 tag 推送后生效。

历史打包脚本保留用于追溯旧产物，不属于后续发布步骤；不执行这些脚本，也不将其产物描述成当前推荐安装方式。
