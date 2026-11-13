# A4Stitch

**Turn exam photos and scanned PDFs into A4 duplex printouts that join into an A3 spread.**

[中文](README.md)

Designed primarily for Chinese four-page school exam papers on Windows. Output pages are ordered **1, 4, 2, 3**:

| A4 sheet | Front | Back |
|---|---|---|
| 1 | Page 1 | Page 4 |
| 2 | Page 2 | Page 3 |

Place sheets side by side with pages 1 and 2 facing up. The reverse side forms pages 3 and 4.
Print in A4 portrait, one PDF page per sheet side, duplex long-edge binding, fit to printable area.

## Quick start

Requires Windows x64, Python 3.10+, Windows PowerShell, and a working Chinese Windows OCR language component. Windows x64 / Python 3.14 has been tested locally.

1. Run `安装依赖.bat` to create the project-local virtual environment and install dependencies.
2. Run `检查环境.bat` to check Python dependencies, local Poppler, and Windows OCR.
3. Put images or scanned PDFs in `待处理试卷`.
4. Double-click `处理试卷.bat`.
5. Open the generated PDFs in `output/最新结果`.

A single set of photos needs no renaming. For multiple sets, use prefixes such as `a1.jpg`, `a2.jpg`, `b1.jpg`, `b2.jpg`. PDF files are processed independently.

The tool identifies printed page numbers before imposing pages, infers output names from document content, verifies rendered PDF footers and dimensions, creates previews and a ZIP, and moves successful source files to `已处理`. Failed inputs remain pending. Previous output batches move to `output/历史结果`.

Runtime processing is local and works offline after setup. Initial setup may download Python packages and the upstream Windows Poppler release; generated environments and binaries are not committed.

## Limitations

The main workflow assumes four-page exams. Arbitrary mixed documents, severe perspective distortion, curved pages and PDF rotation metadata are not fully supported. Automatic checks cover page order, count, size and orientation; inspect previews for clipped questions and scan quality. Physical printer duplex settings still need a local test print.

See the [Chinese guide](README.md), [contributing guide](CONTRIBUTING.md), and [third-party notices](THIRD_PARTY_NOTICES.md).

MIT license for original repository code and documentation. Third-party components retain their own licenses.
