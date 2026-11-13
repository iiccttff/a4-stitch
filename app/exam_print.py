# -*- coding: utf-8 -*-
"""
试卷照片打印工具：默认 A4 双面后左右拼接，4 页 PDF 真实页码为 1、4、2、3。
先自动校正方向、拆页、读取页脚实际页码，再进行拼版；识别不清时弹窗核对。
原图保留，等比缩放，白底居中，不裁切题目。
依赖：Pillow；自动页码识别使用本机 Windows OCR（read_page_numbers.ps1）。
用法示例：
  python exam_print.py 照片1.jpg 照片2.jpg
  python exam_print.py 某文件夹 --name 第四单元自测卷
  python exam_print.py a.jpg b.jpg --mode straight --rotate ccw
"""

import argparse
import glob
import os
import json
import re
import statistics
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps
from project_paths import ROOT
from desktop import open_path

# ---------------- 定型常量 ----------------
A4_W, A4_H = 2480, 3508          # A4 竖版像素 @300dpi
MARGIN_DEFAULT = 60               # 页面四周留白 px
DARK_GRAY = 180                   # 灰度低于此值视为墨迹
BLANK_RATIO = 0.002              # 一列内深色像素占比低于此值视为空白列
MIN_GAP = 18                      # 分界空白带最小宽度（检测图基准 px）
DETECT_W = 800                   # 分界检测时把图缩放到该宽度，提速

# 旋转方向：PIL 中 ROTATE_90 为逆时针 90°，ROTATE_270 为顺时针 90°
ROT_MAP = {
    "0": None,
    "ccw": Image.ROTATE_90,
    "cw": Image.ROTATE_270,
    "180": Image.ROTATE_180,
}

IMG_EXTS = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.pdf")


def collect_images(paths):
    """收集文件/目录下的图片，按文件名排序去重。"""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for ext in IMG_EXTS:
                files += glob.glob(os.path.join(p, ext))
        elif os.path.exists(p):
            files.append(p)
    files = sorted(set(files), key=lambda s: os.path.basename(s).lower())
    return files


def _orientation_score(im):
    """横排文字得分：行投影方差 / 列投影方差，越大越接近正立横排。
    注意：该比值在顺时针/逆时针 90° 下相同，只能判断“是否需要转 90°”，
    不能区分转向；转向由 auto 默认 ccw，或用 --rotate 手动指定。
    """
    gray = im.convert("L")
    w = DETECT_W
    h = max(1, int(gray.height * w / gray.width))
    gray = gray.resize((w, h))
    px = gray.tobytes()
    row = [0] * h
    col = [0] * w
    for y in range(h):
        base = y * w
        for x in range(w):
            if px[base + x] < DARK_GRAY:
                row[y] += 1
                col[x] += 1
    row_var = statistics.pvariance(row)
    col_var = statistics.pvariance(col)
    return row_var / (col_var + 1e-9)


def correct_orientation(im, mode):
    """返回 (校正后图, 方向标签)。
    auto：先用行列投影判断是否需要转 90°；竖拍默认逆时针(ccw)校正。
    手动：0 / ccw / cw / 180 强制指定。
    """
    if mode != "auto":
        rot = ROT_MAP.get(mode)
        out = im.transpose(rot) if rot is not None else im
        return out, mode
    score0 = _orientation_score(im)
    if im.width >= im.height and score0 >= 1.0:
        return im, "0(自动)"
    score90 = _orientation_score(im.transpose(Image.ROTATE_90))
    if score90 > score0:
        return im.transpose(Image.ROTATE_90), "ccw(自动)"
    return im, "0(自动)"


def _column_dark_ratio(gray):
    """返回每列深色像素占比列表（在已缩小的图上计算）。"""
    gw, gh = gray.size
    px = gray.tobytes()
    col_dark = [0] * gw
    for y in range(gh):
        row = y * gw
        for x in range(gw):
            if px[row + x] < DARK_GRAY:
                col_dark[x] += 1
    return [c / gh for c in col_dark]


def find_split_x(im):
    """定位左右两页之间的空白分界带，返回原图坐标切缝 x；找不到退回正中。"""
    w, h = im.size
    gray = im.convert("L")
    scale = DETECT_W / w
    gw = DETECT_W
    gh = max(1, int(h * scale))
    gs = gray.resize((gw, gh))
    ratio = _column_dark_ratio(gs)

    mid = gw // 2
    lo, hi = int(gw * 0.35), int(gw * 0.65)

    blank = [x for x in range(lo, hi) if ratio[x] < BLANK_RATIO]
    segs = []
    if blank:
        start = prev = blank[0]
        for x in blank[1:]:
            if x == prev + 1:
                prev = x
            else:
                segs.append((start, prev))
                start = prev = x
        segs.append((start, prev))
    segs = [g for g in segs if g[1] - g[0] >= MIN_GAP]

    if not segs:
        return w // 2

    # 取最靠近中线的那条空白带，切缝放带内中点
    segs.sort(key=lambda g: abs((g[0] + g[1]) // 2 - mid))
    gap_mid = (segs[0][0] + segs[0][1]) // 2
    return int(gap_mid / scale)


def split_two_pages(im):
    """左右切成两页，返回 (左页, 右页, 切缝x)。"""
    cut = find_split_x(im)
    w, h = im.size
    left = im.crop((0, 0, cut, h))
    right = im.crop((cut, 0, w, h))
    return left, right, cut


def parse_page_footer(text, allow_book_numbers=False):
    compact = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))
    number = re.search(r"第(\d{1,3})[页頁]", compact)
    total = re.search(r"共(\d{1,3})[页頁]", compact)
    if number is None and total:
        number = re.search(r"(\d{1,3})[页頁][(（]共\d", compact)
        if number is None:
            number = re.search(r"第(\d{1,3})[(（]共\d", compact)
    if number is None and allow_book_numbers:
        number = re.search(r"[-—一－ー−–](\d{1,3})[-—一－ー−–][。．.]*$", compact)
    return (int(number[1]) if number else None,
            int(total[1]) if total else None, text)


def read_page_numbers(pages, allow_book_numbers=False, footer_start=0.82):
    """用本机 Windows OCR 或 macOS Vision 读取页脚；不上传图片，不凭文件名猜页码。"""
    helper = Path(__file__).with_name("read_page_numbers.ps1")
    with tempfile.TemporaryDirectory(prefix="exam-pages-") as tmp:
        paths = []
        for i, page in enumerate(pages):
            footer = page.crop((0, int(page.height * footer_start), page.width, page.height))
            if footer.width > 2400:
                footer = footer.resize((2400, round(footer.height * 2400 / footer.width)))
            path = Path(tmp) / f"footer-{i}.png"
            footer.save(path)
            paths.append(str(path))
        manifest = Path(tmp) / "input.json"
        manifest.write_text(json.dumps(paths), encoding="utf-8")
        try:
            if sys.platform == 'darwin':
                command = [sys.executable, str(Path(__file__).with_name('mac_ocr.py')), str(manifest)]
            elif sys.platform == 'win32':
                command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(helper),
                           "-Manifest", str(manifest)]
            else:
                raise RuntimeError('目前仅支持Windows和macOS。')
            result = subprocess.run(
                command, capture_output=True, encoding="utf-8",
                timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or "本地 OCR 未启动")
            records = json.loads(result.stdout.lstrip("\ufeff"))
            texts = {record["path"]: record["text"] for record in records}
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"页码自动识别不可用，将请你核对页序：{str(exc)[:180]}")
            return [(None, None, "") for _ in pages]
        readings = []
        for path in paths:
            text = texts.get(path, "")
            readings.append(parse_page_footer(text, allow_book_numbers))
        return readings


def load_exam_pages(files, rotate):
    pages, report = [], []
    for filename in files:
        with Image.open(filename) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        image, label = correct_orientation(image, rotate)
        left, right, cut = split_two_pages(image)
        pages.extend([left, right])
        report.append([os.path.basename(filename), image.size, cut, label, image])
    readings = read_page_numbers(pages)
    # 投影不能判断正反方向；只有页脚识别到连续页码时才采纳备用方向。
    if rotate == "auto":
        for i, record in enumerate(report):
            first, second = readings[2*i:2*i+2]
            if first[0] is not None and second[0] == first[0] + 1:
                continue
            candidates, metadata = [], []
            for turn in (Image.Transpose.ROTATE_180, Image.Transpose.ROTATE_90,
                         Image.Transpose.ROTATE_270):
                candidate = record[4].transpose(turn)
                left, right, cut = split_two_pages(candidate)
                candidates.extend([left, right])
                metadata.append((candidate.size, cut, turn))
            results = read_page_numbers(candidates)
            matches = [j for j in range(3) if results[2*j][0] is not None
                       and results[2*j+1][0] == results[2*j][0] + 1]
            if len(matches) == 1:
                j = matches[0]
                pages[2*i:2*i+2] = candidates[2*j:2*j+2]
                readings[2*i:2*i+2] = results[2*j:2*j+2]
                record[1:4] = [metadata[j][0], metadata[j][1],
                               f"{record[3]} + {metadata[j][2].name}(页码校正)"]
    return pages, readings, [record[:4] for record in report]


def ask_page_order(pages, readings):
    """识别不完整时让用户看图填写实际页码，避免静默生成错误结果。"""
    import tkinter as tk
    from tkinter import messagebox, ttk
    from PIL import ImageTk

    root = tk.Tk()
    root.title("核对试卷页码")
    root.geometry("1000x720")
    ttk.Label(root, text="页码没有完整识别。请看每页图片，在下面填实际页码，再生成 PDF。",
              padding=12).pack()
    canvas = tk.Canvas(root)
    scroll = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    scroll.pack(side="right", fill="y")
    canvas.pack(fill="both", expand=True)
    canvas.configure(yscrollcommand=scroll.set)
    body = ttk.Frame(canvas)
    canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
    entries, thumbnails, answer = [], [], []
    for i, page in enumerate(pages):
        panel = ttk.Frame(body, padding=8)
        panel.grid(row=i // 4, column=i % 4)
        thumbnail = ImageTk.PhotoImage(ImageOps.contain(page, (220, 420)))
        thumbnails.append(thumbnail)
        ttk.Label(panel, image=thumbnail).pack()
        ttk.Label(panel, text=f"输入图片 {i // 2 + 1} · {'左页' if i % 2 == 0 else '右页'}").pack()
        variable = tk.StringVar(value=str(readings[i][0]) if readings[i][0] else "")
        entries.append(variable)
        ttk.Entry(panel, textvariable=variable, width=8, justify="center").pack()
    def confirm():
        try:
            numbers = [int(entry.get()) for entry in entries]
            if sorted(numbers) != list(range(1, len(pages) + 1)):
                raise ValueError
        except ValueError:
            messagebox.showerror("页码不完整", f"请填写 1 到 {len(pages)}，不能重复或遗漏。", parent=root)
            return
        answer.extend(numbers)
        root.destroy()
    ttk.Button(root, text="确认页码，生成打印 PDF", command=confirm).pack(pady=10)
    root.mainloop()
    if not answer:
        raise SystemExit("已取消，没有生成 PDF。")
    return answer


def order_by_page_number(pages, readings, manual=None):
    numbers = [reading[0] for reading in readings]
    if manual:
        numbers = [int(value.strip()) for value in manual.split(",")]
        if len(numbers) != len(pages) or sorted(numbers) != list(range(1, len(pages)+1)):
            raise ValueError("--page-order 必须列出每个拆分页的实际页码，不重复不遗漏。")
    else:
        totals = {reading[1] for reading in readings if reading[1] is not None}
        if any(total != len(pages) for total in totals):
            raise ValueError(f"试卷标注共 {sorted(totals)} 页，但目前拆出 {len(pages)} 页。请检查缺页或混入其他试卷。")
        if any(number is None for number in numbers) or sorted(numbers) != list(range(1, len(pages)+1)):
            numbers = ask_page_order(pages, readings)
    print(f"原始图片拆页的真实页码：{numbers}")
    indexes = sorted(range(len(pages)), key=lambda i: numbers[i])
    return [pages[i] for i in indexes], numbers


def make_a4_page(im, margin=MARGIN_DEFAULT):
    """把单页等比缩放到 A4 竖版画布，白底居中。"""
    w, h = im.size
    avail_w = A4_W - 2 * margin
    avail_h = A4_H - 2 * margin
    scale = min(avail_w / w, avail_h / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    im2 = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (A4_W, A4_H), "white")
    canvas.paste(im2, ((A4_W - nw) // 2, (A4_H - nh) // 2))
    return canvas


def booklet_order(n):
    """A4 双面后拼接的页序（1 基页码），不用于 A3 骑马钉拼版。
    4 页：纸1 正面页1 / 背面页4，纸2 正面页2 / 背面页3 -> [1,4,2,3]。
    2 页：直排 [1,2]；其余页数暂回退直排。
    """
    if n == 4:
        return [1, 4, 2, 3]
    if n == 2:
        return [1, 2]
    return list(range(1, n + 1))


def process_main(argv=None):
    ap = argparse.ArgumentParser(
        description="试卷拍照排版：识别真实页码，A4 双面后拼接（默认）或 A3 整张打印"
    )
    ap.add_argument("--version", action="version", version="A4Stitch " + (ROOT / "VERSION").read_text(encoding="utf-8").strip())
    ap.add_argument("images", nargs="*", help="试卷照片文件或文件夹；不传时读取脚本目录下的待处理试卷")
    ap.add_argument("-o", "--out", default=None, help="输出目录（默认脚本目录 output）")
    ap.add_argument("--name", default=None, help="PDF 文件名（不含扩展名）")
    ap.add_argument("--mode", choices=["booklet", "straight"], default="booklet",
                    help="A4: booklet=双面拼接页序1,4,2,3（默认）；straight=正常页序")
    ap.add_argument("--paper", choices=["A4", "A3"], default="A4",
                    help="默认 A4 双面后拼接；A3 整张请同时使用 --mode straight")
    ap.add_argument("--page-order", help="手动指定拆分页的真实页码，如3,4,1,2；通常由OCR自动读取")
    ap.add_argument("--open", action="store_true", help="成功后自动打开 PDF")
    ap.add_argument("--keep-inputs", action="store_true", help="核验输出，但本次不自动归档待处理目录中的原文件")
    ap.add_argument("--rotate", choices=["auto", "0", "ccw", "cw", "180"], default="auto",
                    help="方向校正：auto 自动；ccw 逆时针90；cw 顺时针90；0 不转")
    ap.add_argument("--margin", type=int, default=MARGIN_DEFAULT, help="页边距 px")
    ap.add_argument("--save-pages", action="store_true", help="同时导出切好的单页 PNG 供核对")
    args = ap.parse_args(argv)

    input_paths = args.images
    if not input_paths:
        default_input = os.path.join(str(ROOT), "待处理试卷")
        os.makedirs(default_input, exist_ok=True)
        input_paths = [default_input]
        print(f"默认读取目录：{default_input}")

    files = collect_images(input_paths)
    if not files:
        print("没有待处理的照片或PDF。处理完成的原文件在“已处理”，打印文件在 output。")
        if args.images:
            raise SystemExit(1)
        if args.open:
            os.makedirs(args.out or str((ROOT / 'output')), exist_ok=True)
            open_path(args.out or str((ROOT / 'output')))
        return

    # 有 a1/a2、b1/b2 这类名称时按字母前缀分套；每个PDF作为独立来源。
    # 普通文件名仍按一套处理，重复/缺失页码必须核对，不能直接混排。
    pdf_files = [filename for filename in files if Path(filename).suffix.lower() == '.pdf']
    image_files = [filename for filename in files if filename not in pdf_files]
    image_groups = {}
    for filename in image_files:
        match = re.fullmatch(r'([A-Za-z]+)[_-]?\d+', Path(filename).stem)
        key = match[1].lower() if match else '试卷'
        image_groups.setdefault(key, []).append(filename)
    if pdf_files or len(image_groups) > 1:
        if args.page_order:
            ap.error('多套批处理不使用统一的 --page-order，请单独指定一套。')
        outdir = args.out or str((ROOT / 'output'))
        failures = []
        for key, group in image_groups.items():
            arguments = group + ['--out', outdir, '--paper', args.paper, '--mode', args.mode,
                                 '--rotate', args.rotate, '--margin', str(args.margin)]
            if args.name:
                arguments += ['--name', f'{args.name}_{key}' if len(image_groups) > 1 else args.name]
            if args.save_pages:
                arguments += ['--save-pages']
            if args.keep_inputs:
                arguments += ['--keep-inputs']
            try:
                process_main(arguments)
            except (SystemExit, OSError, ValueError, subprocess.SubprocessError) as exc:
                failures.append(f'{key}: {exc}')
        if pdf_files:
            from pdf_exam_print import process_pdf
            for filename in pdf_files:
                try:
                    from completed_inputs import snapshot_inputs, finish_inputs
                    snapshot = snapshot_inputs([filename])
                    outputs = process_pdf(filename, outdir, args.name if len(pdf_files) == 1 else None,
                                          args.paper, args.mode, args.margin)
                    finish_inputs([filename], outputs, snapshot, read_page_numbers,
                                  ROOT, args.keep_inputs)
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    failures.append(f'{Path(filename).name}: {exc}')
        if failures:
            print('以下试卷未完成：\n' + '\n'.join(failures))
            raise SystemExit(1)
        print(f'全部处理完成，结果保存在：{outdir}')
        if args.open:
            try:
                open_path(outdir)
            except OSError:
                pass
        return

    if not 0 <= args.margin < min(A4_W, A4_H) // 2:
        ap.error("页边距超出有效范围。")
    from completed_inputs import snapshot_inputs, finish_inputs
    snapshot = snapshot_inputs(files)
    pages, readings, report = load_exam_pages(files, args.rotate)
    try:
        pages, source_numbers = order_by_page_number(pages, readings, args.page_order)
    except ValueError as exc:
        ap.error(str(exc))

    n = len(pages)
    order = booklet_order(n) if args.mode == "booklet" else list(range(1, n + 1))

    outdir = args.out or os.path.join(str(ROOT), "output")
    os.makedirs(outdir, exist_ok=True)
    from exam_names import infer_exam_name, safe_name, unique_pdf_path
    first_footer = readings[source_numbers.index(1)][2] if 1 in source_numbers else ''
    name = safe_name(args.name) if args.name else infer_exam_name(pages[0], first_footer, read_page_numbers)
    suffix = "打印版" if args.paper == "A4" else "A3整张打印版"
    pdf_path = str(unique_pdf_path(Path(outdir) / f"{name}_{suffix}.pdf"))

    a4_pages = [make_a4_page(p, args.margin) for p in pages]
    if args.paper == "A4":
        ordered = [a4_pages[i - 1] for i in order]
        dpi = (A4_W * 25.4 / 210, A4_H * 25.4 / 297)
        layout = [[number] for number in order]
        print_settings = "A4、竖向、每张1页、双面长边翻转、适合可打印区域。不要再用小册子或每张2页。"
    else:
        if args.mode == "booklet":
            count = ((n + 3) // 4) * 4
            layout = []
            for i in range(count // 4):
                layout.extend([[count - 2*i, 1 + 2*i], [2 + 2*i, count - 1 - 2*i]])
        else:
            layout = [[i, i+1] for i in range(1, n+1, 2)]
        ordered = []
        for pair in layout:
            sheet = Image.new("RGB", (4961, A4_H), "white")
            for side, number in enumerate(pair):
                if number <= n:
                    sheet.paste(a4_pages[number-1], (side * A4_W, 0))
            ordered.append(sheet)
        dpi = (4961 * 25.4 / 420, A4_H * 25.4 / 297)
        print_settings = "A3、横向、每张1页、双面短边翻转、适合可打印区域。先试印一张核对翻面方向。"
    temporary_pdf = pdf_path + ".tmp"
    ordered[0].save(temporary_pdf, format="PDF", save_all=True, append_images=ordered[1:],
                    dpi=dpi, quality=95, subsampling=0)
    os.replace(temporary_pdf, pdf_path)

    notes = [f"纸张：{args.paper}", f"输入照片：{len(files)} 张；试卷内容：{n} 页",
             f"原照片左右拆页的真实页码：{source_numbers}", f"PDF 每面的实际页码：{layout}",
             f"打印设置：{print_settings}"]
    notes.extend(f"{fn}：方向={rot}，尺寸={size}，切缝={cut}" for fn, size, cut, rot in report)
    Path(pdf_path).with_name(Path(pdf_path).stem + '_打印说明.txt').write_text("\n".join(notes), encoding="utf-8-sig")

    if args.save_pages:
        page_dir = os.path.join(outdir, f"{name}_pages")
        os.makedirs(page_dir, exist_ok=True)
        for i, p in enumerate(pages, 1):
            p.save(os.path.join(page_dir, f"page{i}.png"))

    print(f"共 {len(files)} 张照片 -> {n} 个页面")
    for fn, size, cut, rot_label in report:
        print(f"  {fn}  方向={rot_label}  尺寸{size}  切缝 x={cut}")
    print(f"纸张={args.paper}  PDF 每面实际页码={layout}")
    print(f"打印设置：{print_settings}")
    print(f"输出 PDF：{pdf_path}")
    if n not in (2, 4) and args.mode == "booklet":
        print("提示：A4 拼接模式目前针对一套4页试卷；其他页数请核对拼接方式。")
    finish_inputs(files, [pdf_path], snapshot, read_page_numbers,
                  ROOT, args.keep_inputs)
    if args.open:
        try:
            open_path(pdf_path)
        except OSError as exc:
            print(f"PDF 已生成，但自动打开失败：{exc}")


def main(argv=None):
    from output_batches import run_default_batch
    return run_default_batch(process_main, argv, ROOT)


if __name__ == "__main__":
    main()
