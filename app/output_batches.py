"""默认每批一个最新结果目录，上一批转存历史；显式 --out 保持原用法。"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import uuid
import zipfile


def _move_inside(source, destination, output_root):
    source, destination, output_root = source.resolve(), destination.resolve(), output_root.resolve()
    if not source.is_relative_to(output_root) or not destination.is_relative_to(output_root):
        raise ValueError('结果目录超出工程output范围，停止移动。')
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.rename(source, destination)


def _update_archive_log(root, mappings):
    path = root / '已处理' / '归档记录.jsonl'
    if not path.exists():
        return
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    for record in records:
        for old, new in mappings:
            record['outputs'] = [str(new / Path(value).relative_to(old))
                                 if Path(value).is_relative_to(old) else value
                                 for value in record.get('outputs', [])]
    temporary = path.with_suffix('.tmp')
    temporary.write_text(''.join(json.dumps(item,ensure_ascii=False)+'\n' for item in records),encoding='utf-8')
    os.replace(temporary, path)


def package_results(stage, passed):
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    import pypdfium2 as pdfium
    font_path = Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'/'msyh.ttc'
    font = ImageFont.truetype(str(font_path),22) if font_path.exists() else ImageFont.load_default()
    board = Image.new('RGB',(1280,60+520*len(passed)),'#e9e9e6')
    draw = ImageDraw.Draw(board)
    draw.text((12,10),'本次试卷拼接预览（打印请使用PDF）',font=font,fill='black')
    for row,path in enumerate(passed):
        document = pdfium.PdfDocument(str(path))
        pictures = []
        try:
            for index in range(len(document)):
                page = document[index]
                bitmap = page.render(scale=500/page.get_height())
                try:
                    pictures.append(bitmap.to_pil().convert('RGB'))
                finally:
                    bitmap.close()
                    page.close()
        finally:
            document.close()
        y = 60+row*520
        draw.text((12,y),path.stem,font=font,fill='black')
        if len(pictures)==4 and pictures[0].width < pictures[0].height:
            order=[0,2,3,1]
            draw.text((12,y+28),'拼接正面',font=font,fill='black')
            draw.text((652,y+28),'拼接背面',font=font,fill='black')
        else:
            order=list(range(len(pictures)))
        for position,index in enumerate(order):
            thumbnail=ImageOps.contain(pictures[index],(300,440))
            board.paste(thumbnail,(12+position*316,y+60))
    board.save(stage/'本次拼接预览.png')
    with zipfile.ZipFile(stage/'本次打印文件.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in passed:
            archive.write(path,path.name)
            for suffix in ('_打印说明.txt','_核验结果.txt','_核验预览.png'):
                extra=path.with_name(path.stem+suffix)
                if extra.exists():
                    archive.write(extra,extra.name)
        for name in ('本次拼接预览.png','本次结果.txt','批次信息.json'):
            archive.write(stage/name,name)


def publish(stage, root, failed=False):
    output_root = (root / 'output').resolve()
    passed = [path for path in stage.glob('*.pdf')
              if path.with_name(path.stem+'_核验结果.txt').is_file()]
    if not passed:
        if any(stage.iterdir()):
            destination = output_root / '失败记录' / stage.name.removeprefix('.处理中_')
            _move_inside(stage, destination, output_root)
            print(f'没有核验通过的新结果，保留上次“最新结果”。失败记录：{destination}')
        else:
            stage.rmdir()
        return None
    for path in list(stage.glob('*.pdf')):
        if path in passed:
            continue
        for associated in list(stage.glob(path.stem+'*')):
            if associated.is_file():
                _move_inside(associated, stage/'未通过核验_勿打印'/associated.name, output_root)
    info = {'created_at':datetime.now().astimezone().isoformat(),
            'verified_exams':len(passed),'partial_failure':failed,
            'files':[path.name for path in passed]}
    (stage/'批次信息.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    (stage/'本次结果.txt').write_text(
        f'本次核验通过：{len(passed)}套\n'+('部分输入失败，未完成的原文件仍在待处理试卷。\n' if failed else '')+
        '打印：A4竖向、每张1页、双面长边翻转、适合可打印区域。\n'
        '每套PDF旁有打印说明、自动核验结果和核验预览。\n',encoding='utf-8-sig')
    package_results(stage,passed)
    latest = output_root/'最新结果'
    history = None
    mappings = []
    if latest.exists():
        history = output_root/'历史结果'/datetime.now().strftime('%Y-%m-%d_%H%M%S')
        if history.exists():
            history = history.with_name(history.name+'_'+uuid.uuid4().hex[:6])
        _move_inside(latest, history, output_root)
        mappings.append((latest,history))
    try:
        _move_inside(stage, latest, output_root)
    except OSError:
        if history is not None and not latest.exists():
            _move_inside(history, latest, output_root)
        raise
    mappings.append((stage,latest))
    try:
        _update_archive_log(root,mappings)
    except (OSError,ValueError) as exc:
        print(f'结果已保存，归档记录的路径更新未完成：{exc}')
    print(f'本次最新结果：{latest}')
    return latest


def run_default_batch(process, argv, root):
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(add_help=False,allow_abbrev=False)
    parser.add_argument('-o','--out')
    options,_ = parser.parse_known_args(arguments)
    if options.out or '--help' in arguments or '-h' in arguments or '--version' in arguments:
        return process(arguments)
    should_open = '--open' in arguments
    arguments = [value for value in arguments if value != '--open']
    output_root = root/'output'
    output_root.mkdir(exist_ok=True)
    stage = output_root/('.处理中_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    stage.mkdir()
    failed = False
    try:
        result = process(arguments+['--out',str(stage)])
    except BaseException:
        failed = True
        raise
    finally:
        latest = publish(stage,root,failed)
        if should_open:
            destination = latest or output_root/'最新结果'
            if destination.exists():
                try:
                    os.startfile(destination)
                except OSError:
                    pass
    return result
