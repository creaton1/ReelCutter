# PyInstaller spec для ReelCutter
import os
import sys
from pathlib import Path

# Пути
ROOT = Path(__file__).parent
SRC = ROOT / "reelcutter"
ASSETS = ROOT / "reelcutter" / "assets"

# Скрытые импорты
hiddenimports = [
    "customtkinter",
    "cv2",
    "numpy",
    "librosa",
    "scipy",
    "moviepy",
    "ffmpeg",
    "faster_whisper",
    "ctranslate2",
    "vosk",
    "pysrt",
    "ass",
    "tqdm",
    "psutil",
    "requests",
    "dotenv",
    "PIL",
    "PIL._tkinter_finder",
]

# Данные для включения
datas = [
    (str(SRC / "assets"), "reelcutter/assets"),
    (str(ROOT / "config.json"), "."),
]

# Исключения (уменьшаем размер)
excludes = [
    "tkinter.test",
    "unittest",
    "pdb",
    "doctest",
    "argparse",
    "html",
    "xml",
    "email",
    "http",
    "urllib",
    "json",
    "csv",
    "sqlite3",
    "multiprocessing",
    "threading",
    "logging",
]

a = Analysis(
    ["reelcutter/__main__.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Фильтруем ненужные бинарники
a.binaries = [b for b in a.binaries if not any(x in b[0] for x in [
    "api-ms-win", "KERNEL32", "msvcrt", "ucrtbase", "VCRUNTIME",
    "libiomp5md", "mkl_", "libopenblas", "libgomp"
])]

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ReelCutter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Без консоли
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS / "icon.ico") if (ASSETS / "icon.ico").exists() else None,
)