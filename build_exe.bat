@echo off
echo Створення .exe файлу...
echo.

REM Удаляем старые файлы сборки
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del "*.spec"

REM Создаем exe файл
pyinstaller --onefile --windowed --noconsole --add-data "UI_HUD.ui;." --icon=icon.ico --name="DroneControl" main.py

REM Проверяем результат
if exist "dist\DroneControl.exe" (
    echo.
    echo ✅ Успішно створено DroneControl.exe у папці dist\
    echo.
    echo Файли:
    dir dist\
    echo.
    echo Запустіть DroneControl.exe з папки dist\
) else (
    echo.
    echo ❌ Помилка створення .exe файлу
)

echo.
pause