"""从试卷内容命名打印文件；不修改原文件名。"""
from datetime import datetime
from pathlib import Path
import re
import unicodedata


def safe_name(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip(' .')[:100]
    if not name or re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]', name, re.I):
        name = '试卷_' + datetime.now().strftime('%Y%m%d')
    return name


def unique_pdf_path(path):
    path = Path(path)
    candidate = path
    number = 2
    while candidate.exists():
        candidate = path.with_name(f'{path.stem} ({number}){path.suffix}')
        number += 1
    return candidate


def infer_exam_name(page, footer_text, read_numbers):
    header = page.crop((0, 0, page.width, max(1, round(page.height*0.35))))
    readings = read_numbers([header], footer_start=0.0)
    text = readings[0][2] if readings else ''
    header_text = re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))
    footer = re.sub(r'\s+', '', unicodedata.normalize('NFKC', footer_text))
    combined = header_text + '\n' + footer
    grade_match = re.search(r'([一二三四五六1-6])年级', combined)
    grade = grade_match[1].translate(str.maketrans('123456','一二三四五六'))+'年级' if grade_match else ''
    subject = next((value for value in ('语文', '数学', '英语', '科学', '道德与法治') if value in combined), '')
    # 教辅页脚“一数上”明确表示一年级数学上册，不凭题目样式判断科目。
    book = re.search(r'([一二三四五六])([数语英])[上下]', footer)
    if book:
        grade = grade or book[1]+'年级'
        subject = subject or {'数':'数学','语':'语文','英':'英语'}[book[2]]
    kind = ''
    if '期中' in header_text:
        kind = '期中测试卷'
    elif '期末' in header_text:
        kind = '期末测试卷'
    elif '学情分析' in header_text:
        kind = '学情分析'
        variant = re.search(r'学情分析([A-H])(?:[^A-Za-z]|$)', header_text)
        if variant:
            kind += variant[1]
    else:
        unit = re.search(r'第?([一二三四五六七八九十\d]+)单元', header_text)
        if unit:
            kind = f'第{unit[1]}单元测试卷'
    if not subject:
        name = '试卷_' + datetime.now().strftime('%Y%m%d')
    else:
        name = grade + subject + '_' + (kind or '试卷')
    name = safe_name(name)
    print(f'自动命名：{name}')
    return name
