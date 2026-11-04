# 源码更新与配置迁移

## 日常更新

1. 关闭程序及它启动的游戏浏览器，在 GitHub Desktop 中选择固定的 `MahjongCopilotPlus` 工作目录。
2. 保存自己的源码修改，然后 Fetch／Pull 更新；不要用另一份下载目录代替当前工作树。
3. 查看更新记录。如果依赖有变化，用同一个虚拟环境执行 `python -m pip install -r requirements.txt` 和 `python -m pip check`；若 Playwright 或浏览器版本有变化，再安装匹配的 Chromium。
4. 从该工作目录的 `start.bat` 重新启动。BAT 运行的是当前源码，历史 exe 不会更新。

`settings.json`、装扮私人配置、权重、浏览器资料和证书都被 Git 忽略；正常 Pull 不替换这些文件。更新前仍可自行备份。不要把无凭据示例覆盖到自己的配置上。

## 从旧 exe／另一份源码迁移

先完成主工作目录的 Python 环境安装，关闭旧程序，再按需复制这些本机文件：

- 根目录 `settings.json`：AI 连接、窗口、老板键等设置。
- `mjmax/config/settings.yaml`、`mjmax/config/settings.mod.yaml`：实际存在的装扮配置。
- `browser_data/`、`mitm_config/`：如需保留登录资料和本机代理证书，仅在本机复制。
- 自备的模型权重及兼容的可选三麻扩展；迁移后核对模型路径。

不要复制整个旧 `_internal/`、exe 或虚拟环境来覆盖新源码。旧版 OT 的地址与密钥继续保留原接口；使用 Akagi v3 时手动选择 v3 并填写该服务对应的密钥。配置不会在多个目录之间自动同步。

本机如果临时通过 `venv/` 目录联接复用旧环境，原环境仍需保留；这是依赖复用，不表示旧目录源码继续维护，详见[开发目录说明](WORKSPACE.md)。

历史 preview.1／preview.2 的便携包仅作为旧构建留存，后续 GitHub 不再提供更新的 exe 或 `windows-x64.zip`。
