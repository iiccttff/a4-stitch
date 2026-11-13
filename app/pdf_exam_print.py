"""扫描 PDF 拆页与 A4 双面拼接。pypdf 保留源图像，PDFium 仅用于分析。"""
from copy import copy
from pathlib import Path
import re

from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject
import pypdfium2 as pdfium

import exam_print as app


def scan_image_and_bounds(page, pdfium_page):
    # 手机扫描 PDF 常只有一幅图片及其矩阵。直接分析原图可避免页码因缩小丢失。
    contents = page.get_contents()
    operations = contents.operations if contents is not None else []
    if [operator for _, operator in operations] == [b'q', b'cm', b'Do', b'Q']:
        a, b, c, d, x, y = map(float, operations[1][0])
        if a > 0 and d > 0 and b == c == 0 and len(page.images) == 1:
            return page.images[0].image.convert('RGB'), (x, y, x+a, y+d)
    width, height = pdfium_page.get_size()
    bitmap = pdfium_page.render(scale=3000 / max(width, height))
    try:
        image = bitmap.to_pil().convert('RGB')
    finally:
        bitmap.close()
    box = page.cropbox
    return image, tuple(map(float, (box.left, box.bottom, box.right, box.top)))


def infer_groups(readings):
    """页码重启且前一套已完整时分套；不把八页默认为同一套四页试卷。"""
    groups, current = [], []
    for i, reading in enumerate(readings):
        number = reading[0]
        if number is None:
            raise ValueError('扫描 PDF 有页码未识别，请在预览中确认后再处理。')
        if current and number < readings[current[-1]][0]:
            groups.append(current)
            current = []
        current.append(i)
    if current:
        groups.append(current)
    for group in groups:
        numbers = sorted(readings[i][0] for i in group)
        if len(group) != 4 or numbers != list(range(numbers[0], numbers[0]+4)):
            raise ValueError(f'当前扫描 PDF 分套结果不明确：{numbers}。每套需要4个连续页码。')
        totals = {readings[i][1] for i in group if readings[i][1] is not None}
        if any(total != 4 for total in totals):
            raise ValueError(f'页脚总页数是 {totals}，请检查是否缺页。')
    return groups


def process_pdf(source, outdir, name=None, paper='A4', mode='booklet', margin=60):
    source = Path(source)
    reader = PdfReader(source)
    if reader.is_encrypted:
        raise ValueError('暂不处理加密 PDF，请先解密。')
    doc = pdfium.PdfDocument(str(source))
    parts, pictures = [], []
    try:
        for index, page in enumerate(reader.pages):
            pdfium_page = doc[index]
            try:
                if page.rotation:
                    raise ValueError('此 PDF 带页面旋转标记，请先校正后再处理。')
                image, box = scan_image_and_bounds(page, pdfium_page)
            finally:
                pdfium_page.close()
            x0, y0, x1, y1 = box
            if image.width > image.height * 1.1:
                left, right, cut = app.split_two_pages(image)
                split_x = x0 + (x1-x0) * cut / image.width
                boxes = [(x0, y0, split_x, y1), (split_x, y0, x1, y1)]
                images = [left, right]
            else:
                boxes, images = [box], [image]
            for bounds, picture in zip(boxes, images):
                part = copy(page)
                part.cropbox = RectangleObject(bounds)
                parts.append(part)
                pictures.append(picture)
    finally:
        doc.close()
    readings = app.read_page_numbers(pictures, allow_book_numbers=True)
    groups = infer_groups(readings)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for set_index, group in enumerate(groups, 1):
        group = sorted(group, key=lambda i: readings[i][0])
        actual_numbers = [readings[i][0] for i in group]
        if paper == 'A4':
            order = [0, 3, 1, 2] if mode == 'booklet' else [0, 1, 2, 3]
            layout = [[group[i]] for i in order]
            width, height = 210*72/25.4, 297*72/25.4
        else:
            layout = [[group[3], group[0]], [group[1], group[2]]] if mode == 'booklet' else [group[:2], group[2:]]
            width, height = 420*72/25.4, 297*72/25.4
        writer = PdfWriter()
        for side in layout:
            sheet = writer.add_blank_page(width, height)
            slot_width = width / len(side)
            padding = margin * 72 / 300
            for position, part_index in enumerate(side):
                part = parts[part_index]
                box = part.cropbox
                part_width, part_height = float(box.width), float(box.height)
                scale = min((slot_width-2*padding)/part_width, (height-2*padding)/part_height)
                tx = position*slot_width+(slot_width-part_width*scale)/2-float(box.left)*scale
                ty = (height-part_height*scale)/2-float(box.bottom)*scale
                sheet.merge_transformed_page(part, Transformation((scale, 0, 0, scale, tx, ty)))
        from exam_names import infer_exam_name, safe_name, unique_pdf_path
        stem = safe_name(name) if name else infer_exam_name(pictures[group[0]], readings[group[0]][2], app.read_page_numbers)
        if name and len(groups) > 1:
            stem += f'_第{set_index}套'
        stem += f'_{paper}双面拼接' if paper == 'A4' else '_A3整张'
        output = unique_pdf_path(outdir / f'{stem}.pdf')
        temporary = output.with_suffix('.tmp')
        writer.write(temporary)
        writer.close()
        temporary.replace(output)
        actual_layout = [[readings[i][0] for i in side] for side in layout]
        settings = 'A4 竖向，每张1页，双面长边翻转，适合可打印区域' if paper == 'A4' else 'A3 横向，每张1页，双面短边翻转，适合可打印区域'
        output.with_name(output.stem + '_打印说明.txt').write_text(
            f'原文件：{source.name}\n本套页码：{actual_numbers}\nPDF每面的实际页码：{actual_layout}\n'
            f'打印设置：{settings}\nPDF图像直接保留源文件数据，没有重新编码JPEG。\n', encoding='utf-8-sig')
        print(f'{source.name} 第{set_index}套：{actual_numbers} -> PDF顺序 {actual_layout}')
        print(f'输出 PDF：{output}')
        outputs.append(output)
    return outputs
