"""Windows/macOS本地桌面和PDF工具入口。"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from project_paths import ROOT


def open_path(path):
    if sys.platform == 'win32':
        os.startfile(str(path))
    elif sys.platform == 'darwin':
        subprocess.Popen(['open',str(path)])
    else:
        raise OSError('目前仅支持Windows和macOS。')


def find_poppler():
    name = 'pdftoppm.exe' if sys.platform == 'win32' else 'pdftoppm'
    local = ROOT/'tools'/'poppler'/'bin'/name
    if local.is_file():
        return str(local)
    if sys.platform == 'darwin':
        return (shutil.which(name) or next((str(path) for path in
                [Path('/opt/homebrew/bin/pdftoppm'),Path('/usr/local/bin/pdftoppm')]
                if path.is_file()),None))
    return None


def chinese_font():
    if sys.platform == 'darwin':
        candidates = [Path('/System/Library/Fonts/PingFang.ttc')]
        candidates.extend(Path('/System/Library/AssetsV2').glob(
            'com_apple_MobileAsset_Font*/*/AssetData/PingFang.ttc'))
        candidates.append(Path('/System/Library/Fonts/STHeiti Medium.ttc'))
    else:
        candidates = [Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'/'msyh.ttc']
    return next((path for path in candidates if path.is_file()),None)
