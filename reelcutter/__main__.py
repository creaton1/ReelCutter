"""Точка входа ReelCutter"""
import sys
import os

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reelcutter.ui.main_window import main

if __name__ == "__main__":
    main()