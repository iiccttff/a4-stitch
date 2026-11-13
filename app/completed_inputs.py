"""核验最终 PDF，成功后归档默认待处理目录中的原文件。"""
import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader
import pypdfium2 as pdfium
from project_paths import ROOT


def snapshot_inputs(files):
    return {str(Path(filename).resolve()): hashlib.sha256(Path(filename).read_bytes()).hexdigest()
            for filename in files}


def verify_output(filename, read_numbers):
    path = Path(filename)
    notes = path.with_name(path.stem + '_打印说明.txt').read_text(encoding='utf-8-sig')
    match = re.search(r'PDF\s*每面的实际页码[：:]\s*(\[.*\])', notes)
    if not match:
        raise ValueError(f'{path.name} 缺少打印页序说明，未归档原文件。')
    layout = ast.literal_eval(match[1])
    if not layout or any(not side or len(side) > 2 for side in layout):
        raise ValueError('打印页序说明无效，未归档原文件。')
    reader = PdfReader(path)
    if len(reader.pages) != len(layout):
        raise ValueError('PDF实际页数与打印说明不一致，未归档原文件。')
    for page, side in zip(reader.pages, layout):
        width = (210 if len(side) == 1 else 420) * 72 / 25.4
        if (abs(float(page.mediabox.width) - width) > 0.01
                or abs(float(page.mediabox.height) - 297*72/25.4) > 0.01
                or page.rotation != 0):
            raise ValueError('PDF纸张尺寸或方向不正确，未归档原文件。')
    expected = [number for side in layout for number in side]
    document = pdfium.PdfDocument(str(path))
    previews, actual = [], [None] * len(expected)
    try:
        for dpi, footer_start in ((300, 0.82), (200, 0.82), (300, 0.90), (200, 0.90)):
            pictures, previews = [], []
            for index, side in enumerate(layout):
                page = document[index]
                bitmap = page.render(scale=dpi/72)
                try:
                    image = bitmap.to_pil().convert('RGB')
                finally:
                    bitmap.close()
                    page.close()
                thumbnail = image.copy()
                thumbnail.thumbnail((400, 500))
                previews.append(thumbnail)
                for position in range(len(side)):
                    pictures.append(image.crop((round(position*image.width/len(side)), 0,
                                                round((position+1)*image.width/len(side)), image.height)))
            missing = [index for index, number in enumerate(actual) if number is None]
            readings = read_numbers([pictures[index] for index in missing],
                                    allow_book_numbers=True, footer_start=footer_start)
            for index, reading in zip(missing, readings):
                actual[index] = reading[0]
            if actual == expected:
                break
            if any(number is not None and number != expected[index] for index, number in enumerate(actual)):
                break
    finally:
        document.close()
    # 部分页脚在PDFium抗锯齿下会被OCR漏读；改用独立渲染器复核，不推测缺失页码。
    local_poppler = ROOT / 'tools' / 'poppler' / 'bin' / 'pdftoppm.exe'
    poppler = str(local_poppler) if local_poppler.is_file() else None
    if actual != expected and poppler and all(number is None or number == expected[index]
                                               for index, number in enumerate(actual)):
        with tempfile.TemporaryDirectory(prefix='exam-pdf-check-') as folder:
            for side_index, side in enumerate(layout):
                offset = sum(len(previous) for previous in layout[:side_index])
                if all(actual[offset+position] is not None for position in range(len(side))):
                    continue
                prefix = Path(folder) / f'page-{side_index}'
                subprocess.run([poppler, '-r', '200', '-f', str(side_index+1), '-l', str(side_index+1),
                                '-singlefile', '-png', str(path), str(prefix)],
                               check=True, capture_output=True, timeout=60,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                with Image.open(prefix.with_suffix('.png')) as rendered:
                    pictures = [rendered.crop((round(position*rendered.width/len(side)), 0,
                                               round((position+1)*rendered.width/len(side)), rendered.height))
                                for position in range(len(side))]
                readings = read_numbers(pictures, allow_book_numbers=True)
                for position, reading in enumerate(readings):
                    if actual[offset+position] is None:
                        actual[offset+position] = reading[0]
    if actual != expected:
        raise ValueError(f'{path.name} 输出页脚核验未通过：应为{expected}，识别为{actual}。原文件保留待处理。')
    preview = Image.new('RGB', (420*len(previews), 540), '#dddddd')
    draw = ImageDraw.Draw(preview)
    for index, thumbnail in enumerate(previews):
        draw.text((index*420+10, 8), f'PDF {index+1}: {layout[index]}', fill='black')
        preview.paste(thumbnail, (index*420+10, 30))
    preview.save(path.with_name(path.stem + '_核验预览.png'))
    path.with_name(path.stem + '_核验结果.txt').write_text(
        f'自动核验通过\nPDF实际页脚顺序：{actual}\n纸张尺寸、方向及页数：通过\n'
        '已从最终PDF渲染画面读取页码；核验预览可用于人工复查切缝和题目完整性。\n'
        '自动检查不等于人工逐页视觉复查，也未进行打印机实物试印。\n', encoding='utf-8-sig')
    print(f'输出核验通过：{path.name}，真实页码 {actual}')


def archive_inputs(files, outputs, snapshot, root):
    root = Path(root).resolve()
    pending = (root / '待处理试卷').resolve()
    archive = (root / '已处理').resolve()
    if archive.parent != root or pending.parent != root:
        raise ValueError('归档目录不在工具目录内，停止归档。')
    sources = list(dict.fromkeys(Path(filename).resolve() for filename in files))
    sources = [source for source in sources if source.parent == pending]
    if not sources:
        return []  # 拖入其他目录的文件只处理，不搬动用户的外部文件。
    for source in sources:
        current_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if current_hash != snapshot.get(str(source)):
            raise ValueError(f'{source.name} 处理期间发生变化，未归档，请重新处理。')
    archive.mkdir(exist_ok=True)
    moved = []
    try:
        for source in sources:
            destination = archive / source.name
            number = 2
            while destination.exists():
                destination = archive / f'{source.stem} ({number}){source.suffix}'
                number += 1
            os.rename(source, destination)  # Windows重名时拒绝覆盖；同盘移动不重新编码原文件。
            moved.append((source, destination))
        record = {'time': datetime.now().astimezone().isoformat(),
                  'inputs': [{'from': str(source), 'to': str(destination),
                              'sha256': snapshot[str(source)]} for source, destination in moved],
                  'outputs': [str(Path(output).resolve()) for output in outputs]}
        with (archive / '归档记录.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception:
        for source, destination in reversed(moved):
            if not source.exists():
                os.rename(destination, source)
        raise
    print('已归档原文件：' + '、'.join(destination.name for _, destination in moved))
    return [destination for _, destination in moved]


def finish_inputs(files, outputs, snapshot, read_numbers, root, keep=False):
    for output in outputs:
        verify_output(output, read_numbers)
    if not keep:
        archive_inputs(files, outputs, snapshot, root)
