# 第三方来源与许可说明

根目录 [LICENSE](LICENSE) 沿用 MahjongCopilot 的 GNU GPL v3 文本。它不是对仓库中所有第三方内容、外部模型或服务的统一重新授权。各文件原有版权和许可声明继续适用。

## 集成与派生代码

| 项目 | 在本项目中的用途 | 许可／处理方式 |
| --- | --- | --- |
| [MahjongCopilot](https://github.com/latorc/MahjongCopilot) | 上游程序与 Git 历史；`bot/`、捕获、自动操作等基础 | 保留原 GPL v3 文本和 Latorc 的版权声明；`main.py` 的原始声明允许 v3 或后续版本 |
| [MahjongCopilot-max](https://github.com/jiboyingg/MahjongCopilot-max) | Copilot／MajsoulMax 整合参考 | 该仓库声明 GPL v3；在 README 和 NOTICE 中明确注明来源 |
| [MajsoulMax](https://github.com/Avenshy/MajsoulMax) | `mjmax/plugin/mod.py` 等装扮逻辑的来源 | 上游 GPL v3；保留 Avenshy 署名，集成改动见 `mjmax/INTEGRATION.md` |
| [Mortal](https://github.com/Equim-chan/Mortal) | 上游继承的 `bot/local/model.py`、相关模型结构与 libriichi 接口 | 上游为 AGPL v3；相应代码保持其适用许可，另附 [AGPL 原文](LICENSES/AGPL-3.0.txt)；不声称单靠 GPL 即覆盖这些部分 |
| [Akagi](https://github.com/shinkuan/Akagi) | 一番街协议转换与状态行为改编；引擎／模型适配参考及外部原生依赖来源 | 一番街 v3 桥接参考部分为 Apache 2.0，保留[原文](LICENSES/Apache-2.0.txt)、[上游 NOTICE](LICENSES/Akagi-NOTICE.txt)与[来源摘要](game/riichicity/PROVENANCE.md)；外部模型／原生库仍依其具体版本条款 |
| [RiichiCityUnlock](https://github.com/Avenshy/RiichiCityUnlock) | 可选外部 HTTP 代理进程组合 | 本仓库不含其源码、exe、DLL 或私人配置，不修改其免费／捐赠模式；用户自行取得并遵循其分发条款 |
| [proxinject](https://github.com/PragmaTwice/proxinject) | Windows 客户端代理注入接口 | 保留 [Apache 2.0 文本](proxinject/LICENSE)；当前工作树不分发其 exe／DLL |
| [MajsoulData](https://github.com/Avenshy/MajsoulData) | `mjmax/config/max_data.yaml`、描述符及协议快照 | 来源版本与 SHA256 保存在 `data_version.json`；数据／生成协议不代表游戏素材获得授权 |

`libriichi/libriichi.pyd` 和 `proxinject/` 下的二进制来自原 Git 历史，已从本次工作树移除；没有改写历史。新增的 `libriichi3p`、模型权重和下载缓存不纳入源码分发。

### 原生库和模型的边界

三麻原生库与部分模型的历史分发可能含有额外条件。应查阅**实际取得版本**的原始条款，不能把其他项目 README 的说明视为重新分发授权。本项目不捆绑、重新上传或代为授予这些文件的许可。

源码运行的四麻回退依赖 `riichi` 按 `requirements.txt` 安装；历史 Windows 便携包曾改用有对应源码的 Mortal_v4 `libriichi_2025.02.26`，不捆绑旧 wheel 原生文件，准确来源见 [依赖来源](docs/SOURCE_PROVENANCE.md)。外部原生库的源码、许可证和版本对应关系由相应分发提供。发布含原生库的 exe 前，应取得并保留准确来源和对应条款。

对于 GPL 与 AGPL 部分的组合分发，应同时保留其适用条款，并考虑 GPL v3 第 13 节与 AGPL v3 的要求；不要删除 AGPL 声明或将对应部分改称纯 GPL。[GNU 许可 FAQ](https://www.gnu.org/licenses/gpl-faq.en.html#v3Compatibility) 提供相关解释。

## 通过包管理器安装的主要依赖

以下是主要项目及其许可入口，不是打包后所有传递依赖的完整清单。准确条款以所安装版本的随附文件为准。

| 依赖 | 主要用途 | 许可入口 |
| --- | --- | --- |
| [Qt for Python / PySide6](https://doc.qt.io/qtforpython-6/licenses.html) | 桌面界面 | LGPL v3／GPL 等，取决于组件和分发方式 |
| [Playwright](https://github.com/microsoft/playwright-python/blob/main/LICENSE) | Chromium 控制 | Apache 2.0；Chromium 另有第三方许可 |
| [mitmproxy](https://github.com/mitmproxy/mitmproxy/blob/main/LICENSE) | 本地代理 | MIT |
| [PyTorch](https://github.com/pytorch/pytorch/blob/main/LICENSE) | 本地模型推理 | BSD 风格及附带第三方声明 |
| [NumPy](https://github.com/numpy/numpy/blob/main/LICENSE.txt) | 数值处理 | BSD 3-Clause 及附带第三方声明 |
| [Pillow](https://github.com/python-pillow/Pillow/blob/main/LICENSE) | 图像处理 | HPND／历史许可文本 |
| [Requests](https://github.com/psf/requests/blob/main/LICENSE) | HTTP 请求 | Apache 2.0 |
| [Protocol Buffers](https://github.com/protocolbuffers/protobuf/blob/main/LICENSE) | 协议解析 | BSD 风格 |
| [ruamel.yaml](https://pypi.org/project/ruamel.yaml/) | 配置处理 | MIT |
| [PyInstaller](https://pyinstaller.org/en/stable/license.html) | 历史打包工具，已从运行依赖移除 | GPL 及其 bootloader 例外；不改变应用本身的许可 |

源码安装不包含上述包的完整运行库副本。若发布便携二进制，应按实际构建结果保留各组件的许可证、第三方声明和必要源码提供方式；本文件不能替代这些随附材料。

## 协议、素材与服务

游戏中的角色、图片、动画、语音、名称和商标不属于 Plus 的原创内容。内置 ID／协议快照及客户端修改能力不等同于取得这些素材的分发权，也不会改变账号服务器端的物品所有权。

AI 服务及模型权重依其提供者条款使用。本仓库不提供服务账户、API Key 或模型的再授权。
