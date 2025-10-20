import socket
import threading
import time
from pymavlink import mavutil
from PyQt5.QtCore import QObject, pyqtSignal

class MAVLinkConnection(QObject):
    # Сигналы для обновления UI
    telemetry_updated = pyqtSignal(dict)
    connection_status_changed = pyqtSignal(bool)
    message_received = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.connection = None
        self.connected = False
        self.running = False
        self.thread = None
        
        # Параметры подключения по умолчанию
        self.connection_string = "tcp:192.168.1.118:5760"  # Реальный дрон
        self.protocol = "TCP"  # UDP или TCP
        self.host = "192.168.1.118"
        self.port = 5760
        
        # Данные телеметрии
        self.telemetry_data = {
            'lat': 0.0,
            'lon': 0.0,
            'alt': 0.0,
            'relative_alt': 0.0,
            'heading': 0.0,
            'groundspeed': 0.0,
            'airspeed': 0.0,
            'battery_voltage': 0.0,
            'battery_current': 0.0,
            'battery_remaining': 0,
            'mode': 'UNKNOWN',
            'armed': False,
            'gps_fix': 0,
            'satellites': 0
        }
    
    def set_connection_params(self, protocol, host, port):
        """Установка параметров подключения"""
        self.protocol = protocol
        self.host = host
        self.port = port
        
        if protocol == "UDP":
            self.connection_string = f"udpin:{host}:{port}"
        elif protocol == "TCP":
            self.connection_string = f"tcp:{host}:{port}"
        
        self.message_received.emit(f"Параметри з'єднання: {protocol}://{host}:{port}")
    
    def connect(self):
        """Подключение к дрону"""
        try:
            self.message_received.emit(f"Підключення до {self.connection_string}...")
            
            # Создаем MAVLink соединение
            self.connection = mavutil.mavlink_connection(
                self.connection_string,
                baud=57600,
                source_system=255,
                source_component=0
            )
            
            # Ждем первое heartbeat сообщение
            self.message_received.emit("Очікування heartbeat...")
            
            # Запускаем поток для получения данных
            self.running = True
            self.thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.thread.start()
            
            # Ждем подключения (максимум 10 секунд)
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < 10:
                time.sleep(0.1)
            
            if self.connected:
                self.message_received.emit("✅ Підключення встановлено!")
                self.connection_status_changed.emit(True)
                
                # Запрашиваем поток данных
                self._request_data_stream()
                return True
            else:
                self.message_received.emit("❌ Таймаут підключення")
                self.disconnect()
                return False
                
        except Exception as e:
            self.message_received.emit(f"❌ Помилка підключення: {str(e)}")
            self.disconnect()
            return False
    
    def disconnect(self):
        """Отключение от дрона"""
        self.running = False
        self.connected = False
        
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            self.connection = None
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        
        self.connection_status_changed.emit(False)
        self.message_received.emit("📡 Відключено від дрона")
    
    def _receive_loop(self):
        """Основной цикл получения данных"""
        while self.running and self.connection:
            try:
                # Получаем сообщение с таймаутом
                msg = self.connection.recv_match(blocking=True, timeout=1)
                
                if msg is None:
                    continue
                
                # Обрабатываем heartbeat
                if msg.get_type() == 'HEARTBEAT':
                    if not self.connected:
                        self.connected = True
                        # Устанавливаем target_system и target_component из heartbeat
                        if hasattr(self.connection, 'target_system') and self.connection.target_system is None:
                            self.connection.target_system = msg.get_srcSystem()
                            self.connection.target_component = msg.get_srcComponent()
                        
                        self.message_received.emit(f"💓 Heartbeat від system={msg.get_srcSystem()}, component={msg.get_srcComponent()}")
                        self.message_received.emit(f"🎯 Target встановлено: system={self.connection.target_system}, component={self.connection.target_component}")
                    
                    # Обновляем режим и статус вооружения
                    self.telemetry_data['mode'] = mavutil.mode_string_v10(msg)
                    self.telemetry_data['armed'] = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                
                # Обрабатываем GPS данные
                elif msg.get_type() == 'GLOBAL_POSITION_INT':
                    self.telemetry_data['lat'] = msg.lat / 1e7
                    self.telemetry_data['lon'] = msg.lon / 1e7
                    self.telemetry_data['alt'] = msg.alt / 1000.0
                    self.telemetry_data['relative_alt'] = msg.relative_alt / 1000.0
                    self.telemetry_data['heading'] = msg.hdg / 100.0
                    
                # Обрабатываем данные скорости
                elif msg.get_type() == 'VFR_HUD':
                    self.telemetry_data['groundspeed'] = msg.groundspeed
                    self.telemetry_data['airspeed'] = msg.airspeed
                    self.telemetry_data['heading'] = msg.heading
                
                # Обрабатываем данные батареи
                elif msg.get_type() == 'SYS_STATUS':
                    self.telemetry_data['battery_voltage'] = msg.voltage_battery / 1000.0
                    self.telemetry_data['battery_current'] = msg.current_battery / 100.0
                    self.telemetry_data['battery_remaining'] = msg.battery_remaining
                
                # Обрабатываем GPS статус
                elif msg.get_type() == 'GPS_RAW_INT':
                    self.telemetry_data['gps_fix'] = msg.fix_type
                    self.telemetry_data['satellites'] = msg.satellites_visible
                
                # Отправляем обновленные данные в UI
                self.telemetry_updated.emit(self.telemetry_data.copy())
                
            except Exception as e:
                if self.running:
                    self.message_received.emit(f"Помилка отримання даних: {str(e)}")
                break
    
    def _request_data_stream(self):
        """Запрос потока данных от дрона"""
        if not self.connection:
            return
        
        # Ждем немного чтобы target_system был установлен
        time.sleep(0.5)
        
        try:
            # Проверяем что target_system установлен
            if not hasattr(self.connection, 'target_system') or self.connection.target_system is None:
                self.message_received.emit("⚠️ target_system не встановлено, використовуємо 1")
                self.connection.target_system = 1
                self.connection.target_component = 1
            
            self.message_received.emit(f"📊 Запитуємо потік даних від system={self.connection.target_system}")
            
            # Запрашиваем различные потоки данных
            data_streams = [
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                mavutil.mavlink.MAV_DATA_STREAM_POSITION,
                mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS,
                mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
            ]
            
            for stream in data_streams:
                self.connection.mav.request_data_stream_send(
                    self.connection.target_system,
                    self.connection.target_component,
                    stream,
                    1,  # Частота 1 Hz
                    1   # Включить
                )
            
            self.message_received.emit("✅ Потік телеметрії запитано")
            
        except Exception as e:
            self.message_received.emit(f"Помилка запиту даних: {str(e)}")
    
    def send_command(self, command, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0):
        """Отправка команды дрону"""
        if not self.connected or not self.connection:
            self.message_received.emit("❌ Немає з'єднання для відправки команд")
            return False
        
        try:
            # Получаем имя команды для логирования
            command_name = mavutil.mavlink.enums['MAV_CMD'][command].name if command in mavutil.mavlink.enums['MAV_CMD'] else f"CMD_{command}"
            self.message_received.emit(f"📤 Відправляємо {command_name} з параметрами: {param1}, {param2}, {param3}...")
            
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                command,
                0,  # confirmation
                param1, param2, param3, param4, param5, param6, param7
            )
            
            self.message_received.emit(f"✅ {command_name} відправлена на target_system={self.connection.target_system}")
            return True
            
        except Exception as e:
            self.message_received.emit(f"❌ Помилка відправки команди: {str(e)}")
            return False
    
    def arm_disarm(self, arm=True):
        """Вооружение/разоружение дрона"""
        if not self.connected or not self.connection:
            self.message_received.emit("❌ Немає з'єднання для ARM/DISARM")
            return False
            
        param1 = 1 if arm else 0
        action = "вооружение" if arm else "разоружение"
        
        self.message_received.emit(f"🔫 Команда {action}...")
        
        try:
            # Отправляем команду ARM/DISARM с правильными параметрами
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,  # confirmation
                param1,  # arm/disarm (1/0)
                0,      # param2 - не используется
                0,      # param3 - не используется  
                0,      # param4 - не используется
                0,      # param5 - не используется
                0,      # param6 - не используется
                0       # param7 - не используется
            )
            
            self.message_received.emit(f"📤 ARM/DISARM команда відправлена: {param1}")
            
            # Ждем подтверждения от автопилота
            start_time = time.time()
            timeout = 3.0  # 3 секунды на ответ
            
            while time.time() - start_time < timeout:
                msg = self.connection.recv_match(type='COMMAND_ACK', blocking=False, timeout=0.1)
                if msg and msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                    if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                        self.message_received.emit(f"✅ ARM/DISARM команда прийнята автопілотом")
                        return True
                    else:
                        result_name = mavutil.mavlink.enums['MAV_RESULT'].get(msg.result, {}).get('name', f"RESULT_{msg.result}")
                        self.message_received.emit(f"❌ ARM/DISARM команда відхилена: {result_name}")
                        return False
                        
                time.sleep(0.1)
            
            self.message_received.emit(f"⚠️ Немає відповіді на ARM/DISARM команду (timeout)")
            return False
            
        except Exception as e:
            self.message_received.emit(f"❌ Помилка ARM/DISARM: {str(e)}")
            return False
    
    def takeoff(self, altitude=10):
        """Команда взлета"""
        self.message_received.emit(f"🚁 Команда зльоту на висоту {altitude}м...")
        return self.send_command(
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            param7=altitude
        )
    
    def land(self):
        """Команда посадки"""
        self.message_received.emit("🛬 Команда посадки...")
        return self.send_command(mavutil.mavlink.MAV_CMD_NAV_LAND)
    
    def set_mode(self, mode_name):
        """Установка режима полета"""
        try:
            mode_id = self.connection.mode_mapping()[mode_name.upper()]
            self.connection.set_mode(mode_id)
            self.message_received.emit(f"✈️ Зміна режиму на: {mode_name}")
            return True
        except Exception as e:
            self.message_received.emit(f"❌ Помилка зміни режиму: {str(e)}")
            return False
    
    def get_telemetry(self):
        """Получение текущих данных телеметрии"""
        return self.telemetry_data.copy()