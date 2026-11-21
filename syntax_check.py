"""Проверка синтаксиса всех Python файлов"""
import py_compile
import sys
from pathlib import Path

files = [
    "reelcutter/__init__.py",
    "reelcutter/core/config.py",
    "reelcutter/core/highlight_detector.py",
    "reelcutter/core/subtitle_generator.py",
    "reelcutter/core/video_composer.py",
    "reelcutter/ui/main_window.py",
    "reelcutter/ui/__init__.py",
    "reelcutter/__main__.py",
]

all_ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"✅ {f}")
    except py_compile.PyCompileError as e:
        print(f"❌ {f}: {e}")
        all_ok = False

if all_ok:
    print("\n✅ All files compiled successfully!")
    sys.exit(0)
else:
    print("\n❌ Some files have syntax errors")
    sys.exit(1)