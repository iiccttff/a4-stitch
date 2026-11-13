"""工程内Poppler缺失时，从上游GitHub Windows发行包恢复。"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from project_paths import ROOT


def ensure_poppler():
    if sys.platform == 'darwin':
        from desktop import find_poppler
        if find_poppler():
            return
        print('macOS使用原生Vision及PDFium；Poppler为可选补充，需安装时可运行 brew install poppler。')
        return
    if sys.platform != 'win32':
        raise RuntimeError('目前支持Windows和macOS。')
    destination = ROOT/'tools'/'poppler'
    if (destination/'bin'/'pdftoppm.exe').is_file():
        return
    headers = {'User-Agent':'a4-stitch-local-setup','Accept':'application/vnd.github+json'}
    request = urllib.request.Request(
        'https://api.github.com/repos/oschwartz10612/poppler-windows/releases/latest',headers=headers)
    with urllib.request.urlopen(request,timeout=30) as response:
        release = json.load(response)
    asset = next(item for item in release['assets'] if item['name'].lower().endswith('.zip'))
    tools = ROOT/'tools'
    tools.mkdir(exist_ok=True)
    print('正在从上游GitHub下载Windows Poppler：'+asset['name'],flush=True)
    with tempfile.TemporaryDirectory(prefix='poppler-install-',dir=tools) as folder:
        folder = Path(folder).resolve()
        if not folder.is_relative_to(tools.resolve()):
            raise RuntimeError('安装临时目录超出工程范围。')
        archive = folder/'package.zip'
        with urllib.request.urlopen(urllib.request.Request(asset['browser_download_url'],headers={'User-Agent':'a4-stitch-local-setup'}),timeout=30) as response, archive.open('wb') as stream:
            shutil.copyfileobj(response,stream)
        digest = asset.get('digest','') or ''
        if digest.startswith('sha256:') and hashlib.sha256(archive.read_bytes()).hexdigest()!=digest[7:]:
            raise RuntimeError('Poppler安装包校验不一致，停止安装。')
        unpack = folder/'unpacked'
        with zipfile.ZipFile(archive) as package:
            if any(not (unpack/member.filename).resolve().is_relative_to(unpack.resolve()) for member in package.infolist()):
                raise RuntimeError('安装包包含工程外路径，停止解压。')
            package.extractall(unpack)
        executable = next(unpack.rglob('pdftoppm.exe'))
        library = executable.parent.parent
        destination.mkdir(parents=True,exist_ok=True)
        for name in ('bin','etc','share'):
            if (library/name).is_dir():
                shutil.copytree(library/name,destination/name,dirs_exist_ok=True)
        (destination/'download-source.json').write_text(json.dumps(
            {'tag':release['tag_name'],'url':asset['browser_download_url'],'digest':digest},indent=2),encoding='utf-8')
    print('工程内Poppler已准备好。')
