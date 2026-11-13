# GitHub发布说明

## 项目信息

- 展示名称：**A4Stitch · A4 拼卷**
- 推荐仓库名：**a4-stitch**
- 中文介绍：把试卷整理成A4双面打印文件，拼出A3展开效果。
- 英文Description：Local Windows tool for turning exam photos and scanned PDFs into A4 duplex printouts that join into an A3 spread.
- 建议Topics：`pdf` `printing` `duplex-printing` `a4` `a3` `ocr` `exam-paper` `windows` `python`
- 初始版本：0.1.0
- 原创代码许可证：MIT；第三方依赖见THIRD_PARTY_NOTICES.md。

## 创建与推送

远程仓库：`git@github.com:iiccttff/a4-stitch.git`
网页：https://github.com/iiccttff/a4-stitch

本地main分支已配置origin。后续修改后提交并推送：

```powershell
git status
git add --all
git commit -m "Describe the change"
git push
```

## 已准备的内容

中英文README、打印示意图、MIT许可证、第三方说明、贡献指南、安全说明、更新记录、Issue模板、PR模板和Windows回归测试工作流。
原始试卷、已处理原件、输出、虚拟环境、DLL和离线包已加入Git忽略规则。

## 首次发布

1. 在GitHub查看README示意图与链接。
2. 查看Actions结果；当前CI不覆盖中文OCR及实物打印。
3. Release可使用标签v0.1.0，标题“A4Stitch 0.1.0”。
4. 发布源码包时可直接使用GitHub自动生成的Source code附件。
5. 若另做包含Python或Poppler等二进制的便携包，需额外整理对应许可证和来源；当前提供的是可安装的源码工程。

### Release正文

A4Stitch首个版本：把试卷照片和扫描PDF整理为A4双面打印文件，左右拼接获得A3展开效果。

默认页序1、4、2、3。支持页码识别、自动命名、输出核验、拼接预览、结果打包、原文件归档与历史批次保存。

需要Windows x64、Python 3.10+及Windows中文OCR组件。安装依赖后可本地离线处理。
当前主要针对四页中文试卷；明显透视、弯曲和PDF旋转标记尚未完整自动校正。自动核验后仍需查看题目边缘和清晰度。
