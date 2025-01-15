import sys
import time
from threading import Thread, Event
from queue import Queue

from PyQt5.QtCore import pyqtSlot, QCoreApplication, Qt, QTimer, QObject, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QApplication
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

from VectoeFDX_UI import Ui_MainWindow


class ModbusRequest(object):
    """封装 Modbus 请求"""

    def __init__(self, code, slave, address, value=None, count=None, no_response_expected=False):
        self.code = code
        self.slave = slave
        self.address = address
        self.value = value
        self.count = count
        self.no_response_expected = no_response_expected


class CANoeBenchModbus(object):
    CodeReadCoils = 0x01
    CodeReadDiscreteInputs = 0x02
    CodeReadHoldingRegisters = 0x03
    CodeReadInputRegisters = 0x04
    CodeWriteSingleCoil = 0x05
    CodeWriteRegister = 0x06

    def __init__(self,
                 port='com1',
                 serial_baud_rate: int = 115200,
                 serial_bytesize: int = 8,
                 serial_parity="N",
                 serial_stop_bits: int = 1,
                 serial_timeout: int = 1,
                 queue_maxsize: int = 100,  # 新增队列最大值参数
                 read_interval: float = 1.0,  # 新增读取间隔参数
                 ):
        super().__init__()

        # modbus RTU config
        self.modbus_client = None
        self.port = port
        self.serial_baud_rate = serial_baud_rate
        self.serial_bytesize = serial_bytesize
        self.serial_parity = serial_parity
        self.serial_stop_bits = serial_stop_bits
        self.serial_timeout = serial_timeout
        self.retries = 0
        self.is_running = False
        self.request_queue = Queue(maxsize=queue_maxsize)  # 使用 maxsize
        self.worker_thread = None
        self.add_request_thread = None  # 添加请求的线程
        self.stop_add_request_event = Event()  # 控制添加请求线程停止的事件
        self.read_interval = read_interval
        self.modbus_response_handlers = {
            self.CodeReadCoils: self.handler_read_coils_response,
            self.CodeReadDiscreteInputs: self.handler_read_discrete_inputs_response,
            self.CodeReadHoldingRegisters: self.handler_read_holding_registers_response,
            self.CodeReadInputRegisters: self.handler_read_input_registers_response,
            self.CodeWriteSingleCoil: self.handler_write_single_coil_response,
            self.CodeWriteRegister: self.handler_write_register_response,

        }

    def create_modbus_rtu_service(self):
        try:
            self.modbus_client = ModbusSerialClient(
                port=self.port,
                baudrate=self.serial_baud_rate,
                bytesize=self.serial_bytesize,
                parity=self.serial_parity,
                stopbits=self.serial_stop_bits,
                timeout=self.serial_timeout,
                retries=self.retries,
            )
            if not self.modbus_client.connect():
                print(f"无法连接到从站进行写入")
                return False
            return True
        except ModbusException as e:
            print(f"向从站写入数据时发生错误: {e}")
            return False

    def start_modbus_service(self):
        """启动 Modbus 服务，开始处理请求"""
        if self.is_running:
            return
        self.is_running = True
        self.worker_thread = Thread(target=self._run_request_loop, daemon=True)
        self.worker_thread.start()
        self.stop_add_request_event.clear()  # 清除停止事件
        self.add_request_thread = Thread(target=self._add_request_loop, daemon=True)
        self.add_request_thread.start()

    def stop_modbus_service(self):
        """停止 Modbus 服务"""
        self.is_running = False
        self.stop_add_request_event.set()  # 设置停止事件
        if self.worker_thread:
            self.worker_thread.join()
            self.worker_thread = None
        if self.add_request_thread:
            self.add_request_thread.join()
            self.add_request_thread = None

    def enqueue_request(self, request):
        """将请求添加到队列"""
        self.request_queue.put(request, block=True)  # 阻塞添加

    def _run_request_loop(self):
        """循环处理请求队列中的请求"""
        while self.is_running:
            try:
                request = self.request_queue.get(timeout=0.1)
                self._process_request(request)
                self.request_queue.task_done()
            except Exception as e:
                # print(f"Error in request loop: {e}")
                pass

    def _process_request(self, request):
        """处理单个 Modbus 请求"""
        try:
            if request.code == self.CodeReadHoldingRegisters:
                response = self.modbus_client.read_holding_registers(slave=request.slave, address=request.address,
                                                                     count=request.count)
                if not response.isError():
                    self.handle_command(request.code, response)
                else:
                    print(f"Error reading registers from slave {request.slave}, address {request.address}")
            elif request.code == self.CodeWriteRegister:
                response = self.modbus_client.write_register(slave=request.slave, address=request.address,
                                                             value=request.value)
                if not response.isError():
                    self.handle_command(request.code, response)
                else:
                    print(f"Error writing register to slave {request.slave}, address {request.address}")
        except Exception as e:
            print(f"Error processing request: {e}")

    def write_register(self, address: int, value: int, *, slave: int = 1, no_response_expected: bool = False):
        """写从站寄存器"""
        request = ModbusRequest(code=self.CodeWriteRegister, slave=slave, address=address, value=value,
                                no_response_expected=no_response_expected)
        self.enqueue_request(request)

    def read_holding_registers(self, address: int, count: int, *, slave: int = 1):
        """读从站寄存器"""
        request = ModbusRequest(code=self.CodeReadHoldingRegisters, slave=slave, address=address, count=count)
        self.enqueue_request(request)

    def create_modbus_rtu_service_close(self):
        """关闭 modbus_client"""
        if self.modbus_client:
            self.modbus_client.close()

    def handle_command(self, code, response):
        """根据response调用相应的处理函数"""
        handler = self.modbus_response_handlers.get(code)
        if handler:
            handler(response)
        else:
            print(f"Unknown code: {code}")

    def handler_read_coils_response(self, response):
        """read_coils后处理"""
        print(f'# handler_read_coils_response:{response}')
        pass

    def handler_read_discrete_inputs_response(self, response):
        """read_discrete_inputs后处理"""
        print(f'# handler_read_discrete_inputs_response:{response}')
        pass

    def handler_read_holding_registers_response(self, response):
        """read_holding_registers后处理"""
        print(f'# handler_read_holding_registers_response:{response}')
        pass

    def handler_read_input_registers_response(self, response):
        """read_input_registers后处理"""
        print(f'# handler_read_input_registers_response:{response}')
        pass

    def handler_write_single_coil_response(self, response):
        """write_single_coil后处理"""
        print(f'# handler_write_single_coil_response:{response}')
        pass

    def handler_write_register_response(self, response):
        """write_register_response后处理"""
        print(f'# handler_write_register_response:{response}')
        pass

    def _add_request_loop(self):
        """循环添加读取寄存器请求"""
        while not self.stop_add_request_event.is_set():
            self.read_holding_registers(address=0, count=10)  # 示例：读取地址 0 开始的 10 个寄存器
            time.sleep(self.read_interval)


class MainWindows(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.modbus_client = CANoeBenchModbus()
        self.connect_signal()
        self.modbus_connected = False

    def connect_signal(self):
        self.pushButton_fdxConnect.clicked.connect(self.toggle_modbus_read)
        self.pushButton_StatusRequest.clicked.connect(self.set_write_request_flag)

    @pyqtSlot()
    def toggle_modbus_read(self):
        """连接/断开 Modbus 客户端并开始/停止读取"""
        if not self.modbus_connected:
            if self.modbus_client.create_modbus_rtu_service():
                self.modbus_client._add_request_loop()
                self.modbus_connected = True
                self.pushButton_fdxConnect.setText("断开")
            else:
                print("Modbus 连接失败")
        else:
            self.modbus_client.stop_modbus_service()
            self.modbus_client.create_modbus_rtu_service_close()
            self.modbus_connected = False
            self.pushButton_fdxConnect.setText("连接")

    def start_reading_registers(self):
        """开始读取从站 1 和 2 的寄存器 1-5"""
        for slave in [1, 2]:
            self.modbus_client.read_holding_registers(address=0, count=5, slave=slave)


    def set_write_request_flag(self):
        """设置写寄存器标志"""
        if self.modbus_connected:
            self.modbus_client.write_register(address=1, value=100, slave=1)
        else:
            print("Modbus not connected")




if __name__ == "__main__":
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    app.setStyle("WindowsVista")
    w = MainWindows()
    current_version = "v1.0.0"
    w.setWindowTitle("tool " + current_version)
    w.show()
    sys.exit(app.exec_())
