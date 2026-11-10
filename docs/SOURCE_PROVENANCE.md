# 历史便携包的依赖来源

> 本文保留 preview.1／preview.2 的构建来源记录。后续版本仅分发源码，不再更新或上传便携包；当前安装方式见[安装说明](INSTALL.md)。

应用源码与相应 Windows 便携包应以同一 Release 提供。`BUILD_INFO.json` 记录版本与构建环境，`DEPENDENCIES.json` 记录构建环境的软件包版本与随附许可位置；该清单包括部分仅供构建的工具，不表示全部都在运行时加载。

应用的 GPL 原文、Mortal 派生代码的 AGPL 原文、Qt LGPL 原文及收集到的依赖声明位于 `LICENSES/`。各文件原有条款继续适用，不能按主程序名称统一替换许可。

## 四麻原生扩展

历史 Windows 便携包使用 [shinkuan/Mortal_v4 的 libriichi_2025.02.26](https://github.com/shinkuan/Mortal_v4/releases/tag/libriichi_2025.02.26)，对应上游提交 `2bae7d1`，许可为 AGPL v3。

- 文件：`libriichi-3.11-x86_64-pc-windows-msvc.pyd`。
- SHA256：`fed91677f6d0d03380b6ef62bb2b19e23be83a556fcef4e05ba206c9e11b65cb`。
- 同一标签的源码归档随包放在 `SOURCES/libriichi_2025.02.26-source.zip`。
- 源码归档 SHA256：`965e044cc7c34f2d6dc452a69c379dbc46b8f7896208e34d87b96464d545e2f1`。

历史构建中的引擎位置为 `_internal/libriichi/libriichi.pyd`。

旧 `riichi==0.1.1` 仍为源码安装的 pip 回退依赖。其关联的 Akagi tag 未提供完整 Rust 源码，因此它的原生二进制**不随上述历史便携包分发**。构建后移除 PyInstaller 自动收集的旧 wheel 原生文件，以以上固定版本替代。实际版本与摘要记录在 `ENGINE_PROVENANCE.json`；`scripts/fetch_engine.py` 会校验二进制和源码摘要。

## Qt for Python 6.10.3

PySide6-Essentials 与 Shiboken6 的包元数据允许 LGPL v3 等开源许可。这里使用动态库，未静态链接或修改 Qt。用户可检查源码和替换兼容的动态库，不得用项目条款禁止许可证允许的调试与修改行为。

- [Qt 6.10.3 完整源码](https://download.qt.io/archive/qt/6.10/6.10.3/single/)
- [PySide／Shiboken 源码仓库](https://code.qt.io/cgit/pyside/pyside-setup.git/)
- [Qt for Python 许可说明](https://doc.qt.io/qtforpython-6/licenses.html)

## Chromium、Python 与其他组件

Chromium 的第三方声明保留在 Playwright 浏览器目录内。Python、PyTorch、NumPy、mitmproxy 等的随附声明收集到 `LICENSES/dependencies/`；构建工具及传递依赖各自遵循其具体条款。不能以本清单替代原组件附带的说明。

## 未包含的内容

历史便携构建默认不包含三麻 `libriichi3p` 原生库、proxinject exe／DLL、模型权重、API 账户或使用者运行数据。它们不能从已有个人运行目录直接加入公开包，应按实际取得版本的条款分别处理。
