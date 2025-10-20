@echo off
echo Створення .exe файлу DroneControl...
echo.

REM Очищаємо попередні збірки
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del "*.spec"

REM Створюємо .exe файл без консолі
echo Збірка файлу...
pyinstaller --onefile --windowed --add-data "UI_HUD.ui;." --name "DroneControl" main.py

if exist "dist\DroneControl.exe" (
    echo.
    echo ✅ УСПІШНО! Створено DroneControl.exe
    echo.
    echo Розташування: dist\DroneControl.exe
    echo Розмір файлу:
    dir "dist\DroneControl.exe" | findstr DroneControl
    echo.
    echo Щоб запустити додаток, перейдіть до папки dist\ і запустіть DroneControl.exe
    echo Консоль не буде з'являтися при запуску.
) else (
    echo.
    echo ❌ Помилка! Не вдалося створити .exe файл
    echo Перевірте логи вище для деталей.
)

echo.
pause