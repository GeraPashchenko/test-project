import sys
import os
from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QProgressBar, QTextEdit, QPlainTextEdit, QDialog, QLineEdit, QComboBox, QPushButton, QSpinBox
from PyQt5.QtCore import QTimer, pyqtSignal
import random
import datetime
from mavlink_connection import MAVLinkConnection

class DroneControlApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Загружаем UI файл
        ui_file = os.path.join(os.path.dirname(__file__), 'UI_HUD.ui')
        uic.loadUi(ui_file, self)
        
        # Скрываем проблемный statusLabel с черным текстом
        if hasattr(self, 'statusLabel'):
            self.statusLabel.hide()
        
        # Інициализация переменных
        self.connected = False
        self.drones_list = []
        self.connected_drones = []  # Список підключених дронів
        self.selected_drone = None  # Выбранный дрон из списка
        self.simulated_armed = False  # Статус вооружения в режиме симуляции
        self.current_status = "Готовий"
        self.battery_display_mode = "percent"  # "percent" або "voltage"
        
        # Инициализация MAVLink соединения
        self.mavlink = MAVLinkConnection()
        self.setup_mavlink_signals()
        
        # Реальные данные телеметрии
        self.real_telemetry = False  # Флаг использования реальных данных
        
        # Настройка соединений сигналов
        self.setup_connections()
        
        # Настройка интерфейса
        self.setup_interface()
        
        # Таймер для обновления телеметрии
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_telemetry)
        
        # Обновление статуса
        self.update_status("Готовий до роботи")
        
        # Инициализация индикатора подключения
        self.update_connection_indicator(False)
        
        # Инициализация состояния кнопок ARM/DISARM (разоружен по умолчанию)
        QtCore.QTimer.singleShot(500, self.initialize_ui_state)
    
    def initialize_ui_state(self):
        """Инициализация состояния UI после полной загрузки"""
        # Проверяем доступность кнопок ARM/DISARM
        if hasattr(self, 'armButton') and hasattr(self, 'disarmButton'):
            self.add_log("🔧 Кнопки ARM/DISARM знайдено та ініціалізовано")
            
            # Устанавливаем базовые стили кнопок
            self.setup_button_styles()
            
            # Инициализируем в неактивном состоянии (нет выбранного дрона)
            self.enable_arm_disarm_buttons(False)
        else:
            self.add_log("❌ ПОМИЛКА: Кнопки ARM/DISARM не знайдено!")
    
    def setup_button_styles(self):
        """Настройка базовых стилей кнопок"""
        # Стиль активной кнопки ARM (зеленая)
        self.arm_active_style = """
            QPushButton {
                background-color: #2e7d32 !important;
                color: white !important;
                border: none !important;
                border-radius: 8px !important;
                padding: 8px 16px !important;
                font-size: 12pt !important;
                font-weight: bold !important;
            }
            QPushButton:hover {
                background-color: #388e3c !important;
            }
            QPushButton:pressed {
                background-color: #1b5e20 !important;
            }
        """
        
        # Стиль активной кнопки DISARM (красная)
        self.disarm_active_style = """
            QPushButton {
                background-color: #d32f2f !important;
                color: white !important;
                border: none !important;
                border-radius: 8px !important;
                padding: 8px 16px !important;
                font-size: 12pt !important;
                font-weight: bold !important;
            }
            QPushButton:hover {
                background-color: #f44336 !important;
            }
            QPushButton:pressed {
                background-color: #b71c1c !important;
            }
        """
        
        # Стиль неактивной кнопки (серая)
        self.inactive_style = """
            QPushButton {
                background-color: #424242 !important;
                color: #9e9e9e !important;
                border: none !important;
                border-radius: 8px !important;
                padding: 8px 16px !important;
                font-size: 12pt !important;
                font-weight: bold !important;
            }
        """
            
    def setup_mavlink_signals(self):
        """Настройка сигналов MAVLink"""
        self.mavlink.telemetry_updated.connect(self.update_real_telemetry)
        self.mavlink.connection_status_changed.connect(self.on_mavlink_connection_changed)
        self.mavlink.message_received.connect(self.add_log)
        
    def setup_connections(self):
        """Настройка соединений кнопок с функциями"""
        # Кнопки управления (исправляем имена кнопок согласно UI)
        self.stopButton.clicked.connect(self.connect_drone)  # "Підключити"
        self.connectButton.clicked.connect(self.disconnect_drone)  # "Відключити" 
        self.startButton.clicked.connect(self.quick_connect_drone)  # "🚁 Швидке підключення"
        
        # Кнопки ARM/DISARM
        self.armButton.clicked.connect(self.arm_drone)  # "ARM"
        self.disarmButton.clicked.connect(self.disarm_drone)  # "DISARM"
        
        # Кнопка настроек
        self.settingsButton.clicked.connect(self.open_settings)
        
    def setup_interface(self):
        """Настройка дополнительных элементов интерфейса"""
        
        # Добавляем виджеты в левую панель (Телеметрия)
        self.setup_telemetry_panel()
        
        # Добавляем виджеты в центральную панель (Список дронов)
        self.setup_drones_panel()
        
        # Добавляем виджеты в правую панель (Настройки)
        self.setup_settings_panel()
        
    def setup_telemetry_panel(self):
        """Настройка панели телеметрии"""
        # Создаем виджеты для отображения телеметрии
        self.telemetry_layout = QVBoxLayout()
        
        # Индикатор подключения
        self.connection_status_button = QtWidgets.QPushButton("● ВІДКЛЮЧЕНО")
        self.connection_status_button.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
                font-size: 14pt;
                font-weight: bold;
                margin: 5px;
                max-width: 180px;
                min-width: 140px;
            }
        """)
        self.connection_status_button.setEnabled(False)  # Делаем кнопку неактивной (только индикатор)
        
        # Координаты
        self.coord_label = QLabel("Координати: Н/Д")
        self.coord_label.setStyleSheet("color: #dbe7f3; font-size: 12pt; margin: 5px;")
        
        # Высота
        self.altitude_label = QLabel("Висота: Н/Д")
        self.altitude_label.setStyleSheet("color: #dbe7f3; font-size: 12pt; margin: 5px;")
        
        # Скорость
        self.speed_label = QLabel("Швидкість: Н/Д")
        self.speed_label.setStyleSheet("color: #dbe7f3; font-size: 12pt; margin: 5px;")
        
        # Батарея
        self.battery_label = QLabel("Батарея:")
        self.battery_label.setStyleSheet("color: #dbe7f3; font-size: 12pt; margin: 5px;")
        
        # Кнопка переключения режима батареи
        self.battery_mode_button = QtWidgets.QPushButton("% → V")
        self.battery_mode_button.setStyleSheet("""
            QPushButton {
                background-color: #1e2a30;
                color: #dbe7f3;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 10pt;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #26343d;
            }
        """)
        self.battery_mode_button.clicked.connect(self.toggle_battery_mode)
        
        self.battery_progress = QProgressBar()
        self.battery_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid rgba(255,255,255,0.1);
                border-radius: 5px;
                background-color: rgba(20,28,33,0.7);
                text-align: center;
                color: #dbe7f3;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        
        # Добавляем в контейнер
        telemetry_container = QtWidgets.QWidget()
        telemetry_container.setGeometry(12, 50, 350, 450)
        telemetry_container.setParent(self.leftPanel)
        
        # Контейнер для батареи
        battery_container = QtWidgets.QWidget()
        battery_layout = QHBoxLayout(battery_container)
        battery_layout.setContentsMargins(0, 0, 0, 0)
        battery_layout.addWidget(self.battery_label)
        battery_layout.addWidget(self.battery_mode_button)
        battery_layout.addStretch()
        
        # Контейнер для кнопки подключения (центрируем)
        connection_container = QtWidgets.QWidget()
        connection_layout = QHBoxLayout(connection_container)
        connection_layout.setContentsMargins(0, 0, 0, 0)
        connection_layout.addStretch()
        connection_layout.addWidget(self.connection_status_button)
        connection_layout.addStretch()
        
        layout = QVBoxLayout(telemetry_container)
        layout.addWidget(connection_container)
        layout.addWidget(self.coord_label)
        layout.addWidget(self.altitude_label)
        layout.addWidget(self.speed_label)
        layout.addWidget(battery_container)
        layout.addWidget(self.battery_progress)
        layout.addStretch()
        
    def setup_drones_panel(self):
        """Настройка панели списка дронов"""
        # Список дронов
        self.drones_list_widget = QListWidget()
        self.drones_list_widget.setGeometry(12, 50, 350, 400)
        self.drones_list_widget.setParent(self.centerPanel)
        self.drones_list_widget.setStyleSheet("""
            QListWidget {
                background-color: rgba(30,42,48,0.7);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                color: #dbe7f3;
                font-size: 12pt;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
            QListWidget::item:selected {
                background-color: rgba(70,130,180,0.3);
            }
        """)
        
        # Додаємо інформаційний текст замість тестових дронів
        self.update_drones_list()
        
        # Подключаем обработчик выбора дрона
        self.drones_list_widget.itemSelectionChanged.connect(self.on_drone_selected)
        
    def setup_settings_panel(self):
        """Настройка панели настроек"""
        # Теперь логи встроены в UI через logsTextEdit - просто добавляем начальное сообщение
        self.add_log("Система ініціалізована")
        
    def update_drones_list(self):
        """Оновлення списку підключених дронів"""
        self.drones_list_widget.clear()
        
        if not self.connected_drones:
            # Якщо немає підключених дронів
            info_item = QtWidgets.QListWidgetItem("🔍 Немає підключених дронів")
            info_item.setFlags(info_item.flags() & ~QtCore.Qt.ItemIsSelectable)
            self.drones_list_widget.addItem(info_item)
            
            help_item = QtWidgets.QListWidgetItem("💡 Підключіться до дрона для перегляду")
            help_item.setFlags(help_item.flags() & ~QtCore.Qt.ItemIsSelectable)
            self.drones_list_widget.addItem(help_item)
        else:
            # Додаємо підключені дрони
            for drone in self.connected_drones:
                self.drones_list_widget.addItem(drone)
                
    def add_connected_drone(self, drone_info):
        """Додавання підключеного дрона до списку"""
        if drone_info not in self.connected_drones:
            self.connected_drones.append(drone_info)
            self.update_drones_list()
            self.add_log(f"✅ Дрон додано до списку: {drone_info}")
            
            # Автоматически выбираем подключенный дрон
            self.selected_drone = drone_info
            self.add_log(f"🎯 Автоматично вибрано дрон: {drone_info}")
            
            # Выделяем дрон в списке
            for i in range(self.drones_list_widget.count()):
                item = self.drones_list_widget.item(i)
                if item.text() == drone_info:
                    self.drones_list_widget.setCurrentItem(item)
                    break
            
            # Активируем кнопки ARM/DISARM для подключенного дрона
            self.enable_arm_disarm_buttons(True)
            
    def remove_connected_drone(self, drone_info):
        """Видалення дрона зі списку"""
        if drone_info in self.connected_drones:
            self.connected_drones.remove(drone_info)
            self.update_drones_list()
            self.add_log(f"❌ Дрон видалено зі списку: {drone_info}")
            
    def on_drone_selected(self):
        """Обробка вибору дрона"""
        selected_items = self.drones_list_widget.selectedItems()
        if selected_items:
            drone_name = selected_items[0].text()
            
            # Перевіряємо чи це реальний дрон (не інформаційне повідомлення)
            if drone_name.startswith("🚁"):
                self.add_log(f"✅ Вибрано дрон: {drone_name}")
                self.selected_drone = drone_name
                
                # Активируем кнопки ARM/DISARM для выбранного дрона
                self.add_log("🔧 Активуємо кнопки ARM/DISARM...")
                self.enable_arm_disarm_buttons(True)
                
                if self.connected:
                    self.add_log(f"✅ Активний дрон з MAVLink: {drone_name}")
                    # Если есть реальное подключение, обновляем согласно телеметрии
                    telemetry = self.mavlink.get_telemetry()
                    self.update_arm_buttons_state(telemetry.get('armed', False))
                else:
                    self.add_log(f"📱 Дрон вибрано (симуляція): {drone_name}")
                    # Если нет реального подключения, используем состояние симуляции
                    self.update_arm_buttons_state(self.simulated_armed)
            else:
                # Інформаційні повідомлення не обробляємо
                self.selected_drone = None
                self.enable_arm_disarm_buttons(False)
        else:
            # Ничего не выбрано
            self.selected_drone = None
            self.enable_arm_disarm_buttons(False)
                
    def toggle_battery_mode(self):
        """Переключение режима отображения батареи"""
        if self.battery_display_mode == "percent":
            self.battery_display_mode = "voltage"
            self.battery_mode_button.setText("V → %")
            self.add_log("Режим відображення батареї: Вольти")
        else:
            self.battery_display_mode = "percent"
            self.battery_mode_button.setText("% → V")
            self.add_log("Режим відображення батареї: Проценти")
    
    def quick_connect_drone(self):
        """Быстрое подключение к дрону с дефолтными настройками"""
        if not self.connected:
            # Используем дефолтные настройки: TCP 192.168.1.118:5760
            protocol, host, port = "TCP", "192.168.1.118", 5760
            
            self.mavlink.set_connection_params(protocol, host, port)
            self.update_status("Підключення до дрона...")
            self.add_log(f"🚁 Швидке підключення до дрона {host}:{port}...")
            
            # Пытаемся подключиться
            if self.mavlink.connect():
                self.connected = True
                self.real_telemetry = True
                
                # Обновляем индикатор подключения ПОСЛЕ установки connected
                self.update_connection_indicator(True)
                # Таймер для реальных данных не нужен
                self.timer.stop()
                self.update_status("Підключено до дрона")
                self.add_log("✅ Швидке підключення встановлено!")
                
                # Инициализируем состояние кнопок ARM/DISARM (по умолчанию разоружен)
                self.update_arm_buttons_state(False)
                
                # Додаємо дрон до списку підключених
                drone_name = f"🚁 Дрон ({protocol}://{host}:{port})"
                self.add_connected_drone(drone_name)
            else:
                self.connected = False
                self.real_telemetry = False
                self.update_connection_indicator(False)
                self.update_status("❌ Помилка підключення")
                self.add_log("❌ Не вдалося підключитися до дрона")
        else:
            self.add_log("⚠️ Дрон уже підключено!")
            
    def connect_drone(self):
        """Підключення до дрона"""
        if not self.connected:
            # Показываем диалог настройки подключения
            connection_dialog = ConnectionDialog(self)
            if connection_dialog.exec_() == QDialog.Accepted:
                protocol, host, port = connection_dialog.get_connection_params()
                
                self.mavlink.set_connection_params(protocol, host, port)
                self.update_status("Підключення...")
                self.add_log("Спроба підключення до дрона...")
                
                # Пытаемся подключиться
                if self.mavlink.connect():
                    self.connected = True
                    self.real_telemetry = True
                    
                    # Обновляем индикатор подключения ПОСЛЕ установки connected
                    self.update_connection_indicator(True)
                    # Таймер для реальных данных не нужен
                    self.timer.stop()
                    self.update_status("Підключено")
                    self.add_log("Підключення встановлено")
                    
                    # Инициализируем состояние кнопок ARM/DISARM (по умолчанию разоружен)
                    self.update_arm_buttons_state(False)
                    
                    # Додаємо дрон до списку підключених
                    drone_name = f"🚁 Дрон ({protocol}://{host}:{port})"
                    self.add_connected_drone(drone_name)
                else:
                    self.connected = False
                    self.real_telemetry = False
                    self.update_connection_indicator(False)
                    self.update_status("Помилка підключення")
        else:
            self.add_log("Вже підключено!")
            
    def disconnect_drone(self):
        """Відключення від дрона"""
        if self.connected:
            self.connected = False
            self.real_telemetry = False
            
            # Отключаемся от MAVLink
            self.mavlink.disconnect()
            
            # Видаляємо всі дрони зі списку при відключенні
            self.connected_drones.clear()
            self.selected_drone = None  # Сбрасываем выбранный дрон
            self.update_drones_list()
            
            # Деактивируем кнопки ARM/DISARM
            self.enable_arm_disarm_buttons(False)
            
            self.update_status("Відключено")
            self.add_log("Відключено від системи")
            
            # Обновляем индикатор подключения
            self.update_connection_indicator(False)
            
            # Возвращаемся к демонстрационным данным
            self.timer.start(1000)
            
            # Сброс телеметрии
            self.coord_label.setText("Координати: Н/Д")
            self.altitude_label.setText("Висота: Н/Д")
            self.speed_label.setText("Швидкість: Н/Д")
            self.battery_progress.setValue(0)
            
    def check_system(self):
        """Перевірка системи"""
        self.update_status("Перевірка системи...")
        self.add_log("Запуск діагностики системи...")
        
        # Имитация проверки
        QtCore.QTimer.singleShot(3000, self.system_check_complete)
        
    def system_check_complete(self):
        """Завершення перевірки системи"""
        status = "Система в нормі" if random.choice([True, False, True]) else "Виявлено проблеми"
        self.update_status(status)
        self.add_log(f"Діагностика завершена: {status}")
        
    def arm_drone(self):
        """Вооружение дрона (ARM)"""
        if not self.selected_drone:
            self.add_log("❌ Не вибрано дрон")
            QMessageBox.warning(self, "Помилка", "Спочатку виберіть дрон зі списку!")
            return
        
        # Подтверждение действия
        drone_info = self.selected_drone.replace("🚁 ", "")
        reply = QMessageBox.question(self, "Підтвердження", 
                                   f"Ви впевнені, що хочете вооружити дрон?\n\n{drone_info}", 
                                   QMessageBox.Yes | QMessageBox.No, 
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.update_status("Вооружаємо дрон...")
            
            if self.connected:
                # Реальное подключение - отправляем MAVLink команду
                self.add_log(f"🔫 Реальна команда ARM для {drone_info}...")
                
                # Проверяем текущий статус вооружения
                telemetry = self.mavlink.get_telemetry()
                if telemetry.get('armed', False):
                    self.add_log("⚠️ Дрон уже вооружен!")
                    QMessageBox.information(self, "Увага", "Дрон уже вооружений!")
                    return
                
                if self.mavlink.arm_disarm(arm=True):
                    self.add_log("✅ Реальна команда ARM відправлена успішно")
                else:
                    self.add_log("❌ Помилка відправки реальної команди ARM")
                    QMessageBox.critical(self, "Помилка", "Не вдалося відправити команду ARM!")
            else:
                # Режим симуляции
                if self.simulated_armed:
                    self.add_log("⚠️ Дрон уже вооружен (симуляція)!")
                    QMessageBox.information(self, "Увага", "Дрон уже вооружений!")
                    return
                
                self.add_log(f"🔫 Симуляція ARM для {drone_info}...")
                self.simulated_armed = True
                self.add_log("✅ Дрон вооружен (симуляція)")
                self.update_arm_buttons_state(True)  # Обновляем кнопки на "вооружен"
                QMessageBox.information(self, "Успіх", f"Дрон {drone_info} вооружений!")
                self.update_status("Дрон вооружений (симуляція)")
        
    def disarm_drone(self):
        """Разоружение дрона (DISARM)"""
        if not self.selected_drone:
            self.add_log("❌ Не вибрано дрон")
            QMessageBox.warning(self, "Помилка", "Спочатку виберіть дрон зі списку!")
            return
        
        # Подтверждение действия
        drone_info = self.selected_drone.replace("🚁 ", "")
        reply = QMessageBox.question(self, "Підтвердження", 
                                   f"Ви впевнені, що хочете розброїти дрон?\n\n{drone_info}", 
                                   QMessageBox.Yes | QMessageBox.No, 
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.update_status("Розброюємо дрон...")
            
            if self.connected:
                # Реальное подключение - отправляем MAVLink команду
                self.add_log(f"🛡️ Реальна команда DISARM для {drone_info}...")
                
                # Проверяем текущий статус вооружения
                telemetry = self.mavlink.get_telemetry()
                if not telemetry.get('armed', True):
                    self.add_log("⚠️ Дрон уже розброєний!")
                    QMessageBox.information(self, "Увага", "Дрон уже розброєний!")
                    return
                
                if self.mavlink.arm_disarm(arm=False):
                    self.add_log("✅ Реальна команда DISARM відправлена успішно")
                else:
                    self.add_log("❌ Помилка відправки реальної команди DISARM")
                    QMessageBox.critical(self, "Помилка", "Не вдалося відправити команду DISARM!")
            else:
                # Режим симуляции
                if not self.simulated_armed:
                    self.add_log("⚠️ Дрон уже розброєний (симуляція)!")
                    QMessageBox.information(self, "Увага", "Дрон уже розброєний!")
                    return
                
                self.add_log(f"🛡️ Симуляція DISARM для {drone_info}...")
                self.simulated_armed = False
                self.add_log("✅ Дрон розброєний (симуляція)")
                self.update_arm_buttons_state(False)  # Обновляем кнопки на "разоружен"
                QMessageBox.information(self, "Успіх", f"Дрон {drone_info} розброєний!")
                self.update_status("Дрон розброєний (симуляція)")
        
    def open_settings(self):
        """Відкриття вікна налаштувань"""
        QMessageBox.information(self, "Налаштування", "Вікно налаштувань (в розробці)")
        self.add_log("Відкрито вікно налаштувань")
        
    def update_telemetry(self):
        """Оновлення телеметрії"""
        if self.connected and not self.real_telemetry:
            # Генерируем случайные данные для демонстрации (когда нет реального подключения)
            lat = round(random.uniform(49.0, 51.0), 6)
            lon = round(random.uniform(30.0, 35.0), 6)
            altitude = round(random.uniform(10, 500), 1)
            speed = round(random.uniform(0, 80), 1)
            
            self.coord_label.setText(f"Координати: {lat}°, {lon}°")
            self.altitude_label.setText(f"Висота: {altitude} м")
            self.speed_label.setText(f"Швидкість: {speed} км/год")
            
            # Обновление батареи в зависимости от режима
            if self.battery_display_mode == "percent":
                battery_percent = random.randint(20, 100)
                self.battery_progress.setValue(battery_percent)
                self.battery_label.setText(f"Батарея: {battery_percent}%")
            else:
                # Режим напряжения (обычно 11.1V - 16.8V для Li-Po батарей)
                voltage = round(random.uniform(11.1, 16.8), 1)
                battery_percent = int(((voltage - 11.1) / (16.8 - 11.1)) * 100)
                self.battery_progress.setValue(battery_percent)
                self.battery_label.setText(f"Батарея: {voltage}V")
                
    def update_real_telemetry(self, telemetry_data):
        """Обновление реальных данных телеметрии от MAVLink"""
        if not self.real_telemetry:
            return
            
        # Обновляем координаты
        lat = telemetry_data.get('lat', 0)
        lon = telemetry_data.get('lon', 0)
        if lat != 0 and lon != 0:
            self.coord_label.setText(f"Координати: {lat:.6f}°, {lon:.6f}°")
        else:
            self.coord_label.setText("Координати: GPS недоступний")
        
        # Обновляем высоту
        altitude = telemetry_data.get('relative_alt', 0)
        self.altitude_label.setText(f"Висота: {altitude:.1f} м")
        
        # Обновляем скорость
        speed = telemetry_data.get('groundspeed', 0)
        self.speed_label.setText(f"Швидкість: {speed:.1f} км/год")
        
        # Обновляем батарею
        if self.battery_display_mode == "percent":
            battery_percent = telemetry_data.get('battery_remaining', 0)
            if battery_percent > 0:
                self.battery_progress.setValue(battery_percent)
                self.battery_label.setText(f"Батарея: {battery_percent}%")
            else:
                self.battery_progress.setValue(0)
                self.battery_label.setText("Батарея: Н/Д")
        else:
            voltage = telemetry_data.get('battery_voltage', 0)
            if voltage > 0:
                # Преобразуем напряжение в проценты для прогресс-бара
                battery_percent = min(100, max(0, int(((voltage - 11.1) / (16.8 - 11.1)) * 100)))
                self.battery_progress.setValue(battery_percent)
                self.battery_label.setText(f"Батарея: {voltage:.1f}V")
            else:
                self.battery_progress.setValue(0)
                self.battery_label.setText("Батарея: Н/Д")
                
        # Дополнительная информация в логи
        mode = telemetry_data.get('mode', 'UNKNOWN')
        armed = telemetry_data.get('armed', False)
        gps_sats = telemetry_data.get('satellites', 0)
        
        status_info = f"Режим: {mode} | Озброєний: {'Так' if armed else 'Ні'} | GPS сат: {gps_sats}"
        
        # Обновляем статус только если есть изменения
        if hasattr(self, 'last_status_info') and self.last_status_info != status_info:
            self.add_log(f"📊 {status_info}")
        self.last_status_info = status_info
        
        # Обновляем состояние кнопок ARM/DISARM в зависимости от статуса вооружения
        self.update_arm_buttons_state(armed)
        
    def on_mavlink_connection_changed(self, connected):
        """Обработка изменения состояния MAVLink подключения"""
        if not connected and self.connected:
            # Соединение потеряно
            self.connected = False
            self.real_telemetry = False
            self.update_connection_indicator(False)
            self.update_status("З'єднання втрачено")
            self.add_log("❌ З'єднання з дроном втрачено")
            
            # Очищаємо список дронів
            self.connected_drones.clear()
            self.update_drones_list()
            
            # Возвращаемся к демонстрационным данным
            self.timer.start(1000)
            
    def update_status(self, status):
        """Обновление статуса"""
        # statusLabel скрыт, поэтому добавляем статус в логи
        self.add_log(f"Статус: {status}")
        
    def update_connection_indicator(self, connected):
        """Обновление индикатора подключения"""
        if connected:
            self.connection_status_button.setText("● ПІДКЛЮЧЕНО")
            self.connection_status_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 15px;
                    font-size: 14pt;
                    font-weight: bold;
                    margin: 5px;
                    max-width: 180px;
                    min-width: 140px;
                }
            """)
        else:
            self.connection_status_button.setText("● ВІДКЛЮЧЕНО")
            self.connection_status_button.setStyleSheet("""
                QPushButton {
                    background-color: #d32f2f;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 15px;
                    font-size: 14pt;
                    font-weight: bold;
                    margin: 5px;
                    max-width: 180px;
                    min-width: 140px;
                }
            """)
        
        # Кнопки ARM/DISARM теперь управляются отдельно через выбор дрона
    
    def enable_arm_disarm_buttons(self, enabled):
        """Включение/отключение кнопок ARM/DISARM"""
        if hasattr(self, 'armButton') and hasattr(self, 'disarmButton') and hasattr(self, 'arm_active_style'):
            self.add_log(f"🔧 Оновлення кнопок ARM/DISARM: enabled={enabled}")
            
            if enabled:
                # Кнопки доступны, но состояние зависит от статуса вооружения
                # По умолчанию дрон разоружен, поэтому ARM активна, DISARM неактивна
                self.armButton.setEnabled(True)
                self.disarmButton.setEnabled(False)
                
                # Используем предопределенные стили с !important
                self.armButton.setStyleSheet(self.arm_active_style)
                self.disarmButton.setStyleSheet(self.inactive_style)
                
                self.add_log("✅ ARM активна (зелена), DISARM неактивна (сіра)")
                
            else:
                # Кнопки недоступны
                self.armButton.setEnabled(False)
                self.disarmButton.setEnabled(False)
                
                # Обе кнопки неактивны
                self.armButton.setStyleSheet(self.inactive_style)
                self.disarmButton.setStyleSheet(self.inactive_style)
        else:
            self.add_log("❌ ПОМИЛКА: Кнопки ARM/DISARM або стилі не знайдено!")
    
    def update_arm_buttons_state(self, armed):
        """Обновление состояния кнопок ARM/DISARM в зависимости от статуса вооружения"""
        if not hasattr(self, 'armButton') or not hasattr(self, 'disarmButton'):
            return
        
        # Если есть реальное подключение ИЛИ выбран дрон, кнопки должны быть активны
        if not self.connected and not self.selected_drone:
            self.add_log("⚠️ Кнопки деактивовані: немає підключення та не вибрано дрон")
            self.armButton.setEnabled(False)
            self.disarmButton.setEnabled(False)
            return
            
        if armed:
            # Дрон вооружен - ARM неактивна, DISARM активна
            self.armButton.setEnabled(False)
            self.disarmButton.setEnabled(True)
            
            # Визуальная индикация
            self.armButton.setText("🔫 ВООРУЖЕНО")
            self.disarmButton.setText("🛡️ DISARM")
            
            # Используем предопределенные стили
            self.armButton.setStyleSheet(self.inactive_style)
            self.disarmButton.setStyleSheet(self.disarm_active_style)
        else:
            # Дрон разоружен - ARM активна, DISARM неактивна
            self.armButton.setEnabled(True)
            self.disarmButton.setEnabled(False)
            
            # Визуальная индикация
            self.armButton.setText("🔫 ARM")
            self.disarmButton.setText("🛡️ РОЗБРОЄНО")
            
            # Используем предопределенные стили с !important
            self.armButton.setStyleSheet(self.arm_active_style)
            self.disarmButton.setStyleSheet(self.inactive_style)
            
        # Принудительное обновление интерфейса
        self.armButton.update()
        self.disarmButton.update()
        
    def add_log(self, message):
        """Добавление сообщения в лог"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        # Используем новый QPlainTextEdit из UI
        if hasattr(self, 'logsTextEdit'):
            self.logsTextEdit.appendPlainText(log_entry)
            
            # Прокрутка вниз
            scrollbar = self.logsTextEdit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        else:
            print(f"Log: {log_entry}")  # Fallback в консоль если виджет не найден

class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Налаштування підключення до дрона")
        self.setFixedSize(500, 450)  # Збільшено з 400x300 до 500x450
        self.setStyleSheet("""
            QDialog {
                background-color: #0f1619;
                color: #dbe7f3;
                font-family: "Inter", "Roboto", "Segoe UI", sans-serif;
            }
            QLabel {
                color: #dbe7f3;
                font-size: 12pt;
                margin: 5px;
            }
            QComboBox, QLineEdit, QSpinBox {
                background-color: #1e2a30;
                color: #dbe7f3;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
                padding: 8px;
                font-size: 12pt;
                min-height: 30px;
            }
            QPushButton {
                background-color: #1e2a30;
                color: #dbe7f3;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #26343d;
            }
            QPushButton:pressed {
                background-color: #1a2429;
            }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)  # Збільшено відступи
        layout.setContentsMargins(25, 25, 25, 25)  # Збільшено поля
        
        # Заголовок
        title = QLabel("🔗 Параметри з'єднання MAVLink")
        title.setStyleSheet("font-size: 18pt; font-weight: bold; color: #e6f0fa; margin-bottom: 15px;")
        layout.addWidget(title)
        
        # Протокол
        protocol_layout = QHBoxLayout()
        protocol_layout.addWidget(QLabel("Протокол:"))
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["UDP", "TCP"])
        self.protocol_combo.setCurrentText("TCP")  # Дефолт TCP
        protocol_layout.addWidget(self.protocol_combo)
        layout.addLayout(protocol_layout)
        
        # Хост
        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("IP адреса:"))
        self.host_input = QLineEdit("192.168.1.118")  # Дефолт IP дрона
        self.host_input.setPlaceholderText("Введіть IP адресу дрона")
        host_layout.addWidget(self.host_input)
        layout.addLayout(host_layout)
        
        # Порт
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Порт:"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(5760)  # Дефолт порт дрона
        port_layout.addWidget(self.port_input)
        layout.addLayout(port_layout)
        
        # Предустановки
        presets_layout = QVBoxLayout()
        presets_label = QLabel("📋 Готові налаштування:")
        presets_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        presets_layout.addWidget(presets_label)
        
        preset_buttons_layout = QHBoxLayout()
        preset_buttons_layout.setSpacing(10)
        
        mission_button = QPushButton("Mission Planner")
        mission_button.setStyleSheet("min-height: 35px; font-size: 11pt; padding: 8px;")
        mission_button.setToolTip("UDP 127.0.0.1:14551")
        mission_button.clicked.connect(lambda: self.set_preset("127.0.0.1", 14551, "UDP"))
        
        sitl_button = QPushButton("SITL")
        sitl_button.setStyleSheet("min-height: 35px; font-size: 11pt; padding: 8px;")
        sitl_button.setToolTip("TCP 127.0.0.1:5760")
        sitl_button.clicked.connect(lambda: self.set_preset("127.0.0.1", 5760, "TCP"))
        
        preset_buttons_layout.addWidget(mission_button)
        preset_buttons_layout.addWidget(sitl_button)
        
        presets_layout.addLayout(preset_buttons_layout)
        layout.addLayout(presets_layout)
        
        # Информация
        info_label = QLabel("""
ℹ️ Інформація:
• UDP 14550 - стандартний порт QGroundControl
• UDP 14551 - Mission Planner
• TCP 5760 - SITL симулятор
• Для реального дрона використовуйте його IP""")
        info_label.setStyleSheet("font-size: 10pt; color: #a0a0a0; margin: 10px 0;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)  # Відступ між кнопками
        
        connect_button = QPushButton("🔗 Підключитися")
        connect_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; 
                font-weight: bold;
                font-size: 14pt;
                padding: 12px 20px;
                min-height: 45px;
            }
        """)
        connect_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("❌ Скасувати")
        cancel_button.setStyleSheet("""
            QPushButton {
                font-size: 14pt;
                padding: 12px 20px;
                min-height: 45px;
            }
        """)
        cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addWidget(connect_button)
        layout.addLayout(buttons_layout)
        
    def set_preset(self, host, port, protocol):
        """Установка предустановленных значений"""
        self.host_input.setText(host)
        self.port_input.setValue(port)
        self.protocol_combo.setCurrentText(protocol)
        
    def get_connection_params(self):
        """Получение параметров подключения"""
        return (
            self.protocol_combo.currentText(),
            self.host_input.text().strip(),
            self.port_input.value()
        )

def main():
    app = QApplication(sys.argv)
    
    # Устанавливаем стиль приложения
    app.setStyle('Fusion')
    
    # Создаем и показываем окно
    window = DroneControlApp()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()