@echo off
echo Установка зависимостей...
pip install -r ./requirements.txt

echo.
echo Запуск приложения...
python ./main.py

pause