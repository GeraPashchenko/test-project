# Створення іконки для .exe файлу
from PIL import Image, ImageDraw
import os

def create_icon():
    # Создаем простую иконку 64x64
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Рисуем дрон (простая схема)
    # Корпус
    draw.ellipse([20, 28, 44, 36], fill=(70, 130, 180, 255))
    
    # Пропеллеры
    draw.ellipse([10, 10, 22, 22], fill=(100, 100, 100, 255))
    draw.ellipse([42, 10, 54, 22], fill=(100, 100, 100, 255))
    draw.ellipse([10, 42, 22, 54], fill=(100, 100, 100, 255))
    draw.ellipse([42, 42, 54, 54], fill=(100, 100, 100, 255))
    
    # Соединительные линии
    draw.line([32, 16, 32, 32], fill=(150, 150, 150, 255), width=2)
    draw.line([32, 32, 32, 48], fill=(150, 150, 150, 255), width=2)
    draw.line([16, 32, 32, 32], fill=(150, 150, 150, 255), width=2)
    draw.line([32, 32, 48, 32], fill=(150, 150, 150, 255), width=2)
    
    # Сохраняем как .ico
    img.save('icon.ico', format='ICO')
    print("✅ Іконка створена: icon.ico")

if __name__ == "__main__":
    try:
        create_icon()
    except ImportError:
        print("❌ Для створення іконки потрібно встановити Pillow:")
        print("pip install Pillow")
    except Exception as e:
        print(f"❌ Помилка: {e}")
        # Создаем пустой ico файл если не получается
        with open('icon.ico', 'wb') as f:
            f.write(b'')
        print("✅ Створено порожню іконку")