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
        self.connection_string = "udpin:0.0.0.0:14550"  # QGroundControl стандарт
        self.protocol = "UDP"  # UDP или TCP
        self.host = "127.0.0.1"
        self.port = 14550
        
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
                        self.message_received.emit("💓 Heartbeat отримано")
                    
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
        
        try:
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
            
            self.message_received.emit("📊 Запитано потік телеметрії")
            
        except Exception as e:
            self.message_received.emit(f"Помилка запиту даних: {str(e)}")
    
    def send_command(self, command, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0):
        """Отправка команды дрону"""
        if not self.connected or not self.connection:
            self.message_received.emit("❌ Немає з'єднання для відправки команд")
            return False
        
        try:
            self.connection.mav.command_long_send(
                self.connection.target_system,
                self.connection.target_component,
                command,
                0,  # confirmation
                param1, param2, param3, param4, param5, param6, param7
            )
            
            command_name = mavutil.mavlink.enums['MAV_CMD'][command].name if command in mavutil.mavlink.enums['MAV_CMD'] else f"CMD_{command}"
            self.message_received.emit(f"📤 Команда відправлена: {command_name}")
            return True
            
        except Exception as e:
            self.message_received.emit(f"❌ Помилка відправки команди: {str(e)}")
            return False
    
    def arm_disarm(self, arm=True):
        """Вооружение/разоружение дрона"""
        param1 = 1 if arm else 0
        action = "вооружение" if arm else "разоружение"
        
        self.message_received.emit(f"🔫 Команда {action}...")
        return self.send_command(
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            param1=param1
        )
    
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