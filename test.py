import threading
import time
import queue
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException

class ModbusRTUClient:
    def __init__(self, port, baudrate, bytesize, parity, stopbits, timeout=1):
        self.client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=timeout
        )
        self.is_connected = False
        self.read_interval = 0.1  # 读取周期，可调整
        self.data_queue = queue.Queue()
        self.write_queue = queue.Queue()
        self.running = threading.Event()
        self.running.set()  # 默认运行
        self.reader_thread = None
        self.writer_thread = None
    
    def connect(self):
        try:
            self.client.connect()
            self.is_connected = True
            print("Modbus connected successfully.")
            return True
        except Exception as e:
            print(f"Modbus connection failed: {e}")
            return False

    def disconnect(self):
        if self.is_connected:
            self.client.close()
            self.is_connected = False
            print("Modbus disconnected.")

    def start_reading(self):
        if not self.is_connected:
            print("Not connected to Modbus, cannot start reading.")
            return
        if self.reader_thread is None or not self.reader_thread.is_alive():
            self.reader_thread = threading.Thread(target=self._read_registers_loop, daemon=True)
            self.reader_thread.start()
            print("Modbus reading started.")
        else:
            print("Modbus reading is already running.")
        if self.writer_thread is None or not self.writer_thread.is_alive():
            self.writer_thread = threading.Thread(target=self._write_registers_loop, daemon=True)
            self.writer_thread.start()
            print("Modbus writing started.")
        else:
            print("Modbus writing is already running.")

    def stop_reading(self):
        if self.reader_thread and self.reader_thread.is_alive():
            self.running.clear()
            self.reader_thread.join()
            self.running.set()
            print("Modbus reading stopped.")
        else:
            print("Modbus reading is not running.")

    def write_register(self, address, value, slave_id=1):
        self.write_queue.put((slave_id, address, value))

    def get_data(self):
        data = []
        while not self.data_queue.empty():
            data.append(self.data_queue.get())
        return data
    
    def _read_registers_loop(self):
        while self.running.is_set():
            try:
                # 读取保持寄存器
                rr = self.client.read_holding_registers(address=0, count=10, slave=1)
                if not rr.isError():
                    data = rr.registers
                    self.data_queue.put(data)
                else:
                    print(f"Error reading registers: {rr}")
            except ModbusIOException as e:
                print(f"Modbus IO Error during reading: {e}")
                self.is_connected = False
                break
            except Exception as e:
                print(f"Error during reading: {e}")
            time.sleep(self.read_interval)
    
    def _write_registers_loop(self):
        while self.running.is_set():
            try:
                if not self.write_queue.empty():
                    slave_id, address, value = self.write_queue.get()
                    result = self.client.write_register(address=address, value=value, slave=slave_id)
                    if result.isError():
                        print(f"Error writing register: {result}")
                    else:
                        print(f"Successfully wrote {value} to register {address} on slave {slave_id}")
            except ModbusIOException as e:
                print(f"Modbus IO Error during writing: {e}")
                self.is_connected = False
                break
            except Exception as e:
                print(f"Error during writing: {e}")
            time.sleep(0.01)  # 避免空转，可以调整

if __name__ == '__main__':
    # 配置Modbus参数
    port = 'COM3'  # 根据你的实际端口修改
    baudrate = 9600
    bytesize = 8
    parity = 'N'
    stopbits = 1

    # 创建Modbus客户端实例
    modbus_client = ModbusRTUClient(port, baudrate, bytesize, parity, stopbits)

    # 连接Modbus
    if modbus_client.connect():
        # 启动读写线程
        modbus_client.start_reading()

        try:
            while True:
                # 获取读取的数据
                data = modbus_client.get_data()
                if data:
                    for d in data:
                        print(f"Received data: {d}")

                # 模拟用户输入写寄存器指令
                user_input = input("Enter 'w' to write, or 'q' to quit: ")
                if user_input.lower() == 'w':
                    address = int(input("Enter register address to write: "))
                    value = int(input("Enter value to write: "))
                    modbus_client.write_register(address, value)
                elif user_input.lower() == 'q':
                    break
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("Program interrupted by user.")
        finally:
            # 停止读线程并断开连接
            modbus_client.stop_reading()
            modbus_client.disconnect()
