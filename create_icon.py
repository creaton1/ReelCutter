"""Создание простой иконки для приложения"""
from PIL import Image, ImageDraw, ImageFont
import os

# Создаем иконку 256x256
size = 256
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Фон - градиентный круг
for i in range(size // 2):
    alpha = int(255 * (1 - i / (size // 2)))
    color = (30, 144, 255, alpha)  # DodgerBlue
    draw.ellipse([i, i, size - i, size - i], fill=color)

# Символ ножниц/клипа
# Рисуем простой символ "клип"
center = size // 2
# Верхняя лезвие
draw.polygon([
    (center - 30, center - 40),
    (center + 10, center - 10),
    (center - 10, center - 10),
    (center - 30, center - 20),
], fill='white')
# Нижняя лезвие
draw.polygon([
    (center + 30, center + 40),
    (center - 10, center + 10),
    (center + 10, center + 10),
    (center + 30, center + 20),
], fill='white')
# Крепление
draw.ellipse([center - 8, center - 8, center + 8, center + 8], fill='white')
draw.ellipse([center - 4, center - 4, center + 4, center + 4], fill=(30, 144, 255))

# Сохраняем как ICO
os.makedirs('reelcutter/assets', exist_ok=True)
img.save('reelcutter/assets/icon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
print("Icon created: reelcutter/assets/icon.ico")