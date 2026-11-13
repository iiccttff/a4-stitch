# Third-party components

A4Stitch的MIT许可证适用于本仓库原创代码与文档。第三方组件及操作系统组件保留各自的许可证和条款。

| 组件 | 用途 | 上游与许可证信息 |
|---|---|---|
| Pillow | 图片处理、页面画布和预览 | https://github.com/python-pillow/Pillow ，MIT-CMU及其依赖声明 |
| pypdf | PDF裁切、缩放和重排 | https://github.com/py-pdf/pypdf ，BSD-3-Clause |
| pypdfium2 / PDFium | PDF分析和渲染 | https://github.com/pypdfium2-team/pypdfium2 ，包装器及PDFium/依赖各有相应许可证，见发行包 |
| Poppler | 独立渲染复核 | https://poppler.freedesktop.org/ ，GPL-2.0-or-later及各依赖许可证 |
| PyObjC / Vision | macOS原生离线OCR | https://github.com/ronaldoussoren/pyobjc ，PyObjC为MIT；Vision是macOS系统组件 |
| Windows OCR | 本机页码和标题识别 | Windows系统组件，不随本仓库重新分发 |

Windows Poppler发行包上游：https://github.com/oschwartz10612/poppler-windows 。该仓库的打包脚本许可证与Poppler二进制本身的许可证应分别查看。

源码仓库不提交第三方DLL、离线wheel或虚拟环境。本机已有工具来源和版本记录在tools/poppler中。重新下载安装时，安装器记录下载地址、版本和可用的摘要信息。
发布包含第三方二进制的独立安装包时，需要同时保留对应发行包的许可证、声明与来源信息，并遵循其分发条款；本仓库的MIT许可证不替代这些条款。
