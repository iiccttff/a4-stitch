"""准备或检查工程内的运行环境；仅首次安装可能需要联网补充缺失安装包。"""
import argparse
import importlib
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys
import venv
from project_paths import ROOT

PYTHON = ROOT / '.venv' / 'Scripts' / 'python.exe'


def run(arguments, **kwargs):
    return subprocess.run([str(value) for value in arguments], check=True, **kwargs)


def install():
    if sys.version_info < (3, 10):
        raise RuntimeError('需要 Python 3.10 或更新版本；本工程离线包适用于Windows x64 Python 3.14。')
    if not PYTHON.is_file():
        print('正在创建工程内的 .venv 环境……', flush=True)
        venv.EnvBuilder(with_pip=True).create(ROOT / '.venv')
    command = [PYTHON, '-m', 'pip', 'install', '-r', ROOT / 'app' / 'requirements.txt']
    wheels = ROOT / 'tools' / 'wheels'
    if list(wheels.glob('*.whl')):
        try:
            run(command + ['--no-index', '--find-links', wheels])
        except subprocess.CalledProcessError:
            print('本地安装包与当前Python不匹配，尝试联网安装对应版本。', flush=True)
            run(command)
    else:
        run(command)
    from install_poppler import ensure_poppler
    ensure_poppler()
    run([PYTHON, __file__, '--check'])


def check():
    if os.name != 'nt':
        raise RuntimeError('此工程使用Windows内置OCR，需要在Windows运行。')
    for module, distribution in [('PIL.Image','Pillow'),('pypdf','pypdf'),('pypdfium2','pypdfium2')]:
        importlib.import_module(module)
        print(f'正常：{distribution} {importlib.metadata.version(distribution)}')
    importlib.import_module('tkinter')
    poppler = ROOT / 'tools' / 'poppler' / 'bin' / 'pdftoppm.exe'
    run([poppler, '-v'], capture_output=True, timeout=20,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('正常：工程内Poppler及其动态依赖')
    code = ('$null=[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime];'
            '$engine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages();'
            'if($null -eq $engine){exit 2};$engine.RecognizerLanguage.LanguageTag')
    result = run(['powershell.exe','-NoProfile','-NonInteractive','-Command',code],
                 capture_output=True, text=True, timeout=30,
                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('正常：Windows本地OCR ' + result.stdout.strip())
    for folder in ('待处理试卷','已处理','output'):
        (ROOT / folder).mkdir(exist_ok=True)
    print('环境检查通过。日常处理不依赖Codex、在线接口或API密钥。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        install() if args.install else check()
    except (OSError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
        print(f'本地环境未就绪：{exc}\n请双击“安装依赖.bat”；缺少OCR时需安装Windows中文OCR语言组件。')
        raise SystemExit(1)
