import json
import threading
from threading import Event
from queue import Queue

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException, ModbusIOException



class ModbusRequestParameter:
    def __init__(self):
        self.code = None
        self.value = 0
        self.values = [0]
        self.slave= 1
        self.address= 0
        self.count=1
        self.no_response_expected=False

    def init(self):
        self.code = None
        self.value = 0
        self.values = [0]
        self.slave = 1
        self.address = 0
        self.count = 1
        self.no_response_expected = False

class SerialModbusRTUClient(object):
    CodeReadCoils = 0x01
    CodeReadDiscreteInputs = 0x02
    CodeReadHoldingRegisters = 0x03
    CodeReadInputRegisters = 0x04
    CodeWriteSingleCoil = 0x05
    CodeWriteRegister = 0x06
    CodeReadExceptionStatus = 0x07
    CodeWriteRegisters = 0x10

    def __init__(self,
                 port='com1',
                 serial_baud_rate: int = 115200,
                 serial_bytesize: int = 8,
                 serial_parity="N",
                 serial_stop_bits: int = 1,
                 serial_timeout: int = 1,
                 serial_retries: int = 0,
                 queue_maxsize: int = 20,  # 新增队列最大值参数
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
        self.retries = serial_retries

        self.is_connected = False
        self.modbus_cycle_thread = None
        self.modbus_cycle_is_run_event = threading.Event()
        self.is_stop_cycle_loop = False
        self.modbus_single_thread = None
        self.request_queue = Queue(maxsize=queue_maxsize)  # 使用 maxsize
        # self.request_parameter = ModbusRequestParameter()
        self.stop_read_cycle_request_event = Event()  # 控制添加请求线程停止的事件
        self.modbus_response_handlers = {
            self.CodeReadCoils: self.handler_read_coils_response,
            self.CodeReadDiscreteInputs: self.handler_read_discrete_inputs_response,
            self.CodeReadHoldingRegisters: self.handler_read_holding_registers_response,
            self.CodeReadInputRegisters: self.handler_read_input_registers_response,
            self.CodeWriteSingleCoil: self.handler_write_single_coil_response,
            self.CodeWriteRegister: self.handler_write_register_response,

        }

        self.slaves_list = {
            1: 3,
            2: 10,
            3: 10,
        }
        self.cycle_read_slaves_list = [1]
        self.offline_slaves_list = []

        self.modbus_request_handlers = {
            # self.CodeReadCoils: self.handler_read_coils_response,
            # self.CodeReadDiscreteInputs: self.handler_read_discrete_inputs_response,
            self.CodeReadHoldingRegisters: self._read_holding_registers,
            # self.CodeReadInputRegisters: self.handler_read_input_registers_response,
            # self.CodeWriteSingleCoil: self.handler_write_single_coil_response,
            self.CodeWriteRegister: self._write_register,
            self.CodeWriteRegisters: self._write_registers,
        }

    def create_cycle_and_single_thread(self):
        if self.modbus_cycle_thread is None or not self.modbus_cycle_thread.is_alive():
            self.modbus_cycle_thread = threading.Thread(target=self._cycle_read__loop, daemon=True)
        if self.modbus_single_thread is None or not self.modbus_single_thread.is_alive():
            self.modbus_single_thread = threading.Thread(target=self._single__loop, daemon=True)
            self.modbus_single_thread.start()

    def create_modbus_rtu_service(self):
        if not self.is_connected:
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

                self.is_connected = True
                self.create_cycle_and_single_thread()
                return True
            except ModbusException as e:
                print(f"向从站写入数据时发生错误: {e}")
                return False
            except Exception as e:
                print(f"创建modbus rtu错误:{e}")
                return False
    def start_cycle_read__loop(self):
        if self.modbus_cycle_thread is not None and self.is_connected:
            self.modbus_cycle_is_run_event.set()
            self.is_stop_cycle_loop = False
            self.create_cycle_and_single_thread()
            self.modbus_cycle_thread.start()

    def stop_cycle_read__loop(self):
        if self.is_connected and self.modbus_cycle_thread.is_alive():
            self.modbus_cycle_is_run_event.clear()
            self.is_stop_cycle_loop = True
            self.modbus_cycle_thread.join()

    def _single__loop(self):
        if self.is_connected:
            while True:
                try:
                    request_param = self.request_queue.get()
                    self.request_handle_command(request_param)

                except ModbusIOException as e:
                    print(f"Modbus IO Error during writing: {e}")
                    self.is_connected = False
                    break
                except Exception as e:
                    print(f"Error during writing: {e}")


    def _cycle_read__loop(self):
        while True:
            if self.is_stop_cycle_loop:
                return
            if self.modbus_cycle_is_run_event.is_set():
                try:
                    for slave in self.cycle_read_slaves_list:
                        count = self.slaves_list.get(slave)
                        if count:
                            self.read_holding_registers(address=0,count=count,slave=slave)
                except ModbusIOException as e:
                    print(f"Modbus IO Error during reading: {e}")
                    self.is_connected = False
                    break
                except Exception as e:
                    print(f"Error during reading: {e}")
            else:
                self.modbus_cycle_is_run_event.wait()

    def request_handle_command(self, request_parameter:ModbusRequestParameter):
        """根据response调用相应的处理函数"""
        handler = self.modbus_request_handlers.get(request_parameter.code)
        if handler:
            params = vars(request_parameter)
            handler(**params)
        else:
            print(f"Unknown code: {request_parameter.code}")

    def write_register(self, address: int, value: int, *, slave: int = 1,
                       no_response_expected: bool = False,**kwargs):
        """写从站寄存器"""
        try:
            response = self.modbus_client.write_register(slave=slave, address=address, value=value,
                                                    no_response_expected=no_response_expected)
            if not response.isError():
                self.response_handle_command(slave, self.CodeWriteRegister,response)
                # return response.registers
            else:
                return None
        except:
            return None

    def _write_register(self, address: int, value: int, *, slave: int = 1,
                       no_response_expected: bool = False,**kwargs):
        """写从站寄存器"""
        try:
            self.modbus_cycle_is_run_event.clear()
            response = self.modbus_client.write_register(slave=slave, address=address, value=value,
                                                    no_response_expected=no_response_expected)
            self.modbus_cycle_is_run_event.set()
            if not response.isError():
                self.response_handle_command(slave, self.CodeWriteRegister,response)
                # return response.registers
            else:
                return None
        except:
            return None

    def add_write_register_queue(self, address: int, value: int, *, slave: int = 1,
                               no_response_expected: bool = False):
        request_parameter = ModbusRequestParameter()
        request_parameter.code=self.CodeWriteRegister
        request_parameter.value=value
        request_parameter.address = address
        request_parameter.slave = slave
        request_parameter.no_response_expected = no_response_expected

        self.request_queue.put(request_parameter)

    def write_registers(self, address: int, values: list[int], *, slave: int = 1,
                       no_response_expected: bool = False,**kwargs):
        """写从站寄存器"""
        try:
            response = self.modbus_client.write_registers(slave=slave, address=address, values=values,
                                                    no_response_expected=no_response_expected)
            if not response.isError():
                self.response_handle_command(slave, self.CodeWriteRegister,response)
                # return response.registers
            else:
                return None
        except:
            return None

    def _write_registers(self, address: int, values: list[int], *, slave: int = 1,
                       no_response_expected: bool = False,**kwargs):
        """写从站寄存器"""
        try:
            self.modbus_cycle_is_run_event.clear()
            response = self.modbus_client.write_registers(slave=slave, address=address, values=values,
                                                    no_response_expected=no_response_expected)
            self.modbus_cycle_is_run_event.set()
            if not response.isError():
                self.response_handle_command(slave, self.CodeWriteRegister,response)
                # return response.registers
            else:
                return None
        except Exception as e:
            return None

    def add_write_registers_queue(self, address: int, values: list[int], *, slave: int = 1,
                               no_response_expected: bool = False):
        request_parameter = ModbusRequestParameter()
        request_parameter.code=self.CodeWriteRegisters
        request_parameter.values=values
        request_parameter.address = address
        request_parameter.slave = slave
        request_parameter.no_response_expected = no_response_expected

        self.request_queue.put(request_parameter)

    def read_holding_registers(self, address: int, count: int, *, slave: int = 1,
                               no_response_expected: bool = False,**kwargs):
        """读从站寄存器"""
        try:
            self.modbus_cycle_is_run_event.clear()
            response = self.modbus_client.read_holding_registers(slave=slave, address=address, count=count,
                                                            no_response_expected=no_response_expected)
            self.modbus_cycle_is_run_event.set()
            if not response.isError():
                self.response_handle_command(slave, self.CodeReadHoldingRegisters,response)
                # return response.registers
            else:
                return None
        except:
            return None

    def _read_holding_registers(self, address: int, count: int, *, slave: int = 1,
                               no_response_expected: bool = False,**kwargs):
        """读从站寄存器"""
        try:
            response = self.modbus_client.read_holding_registers(slave=slave, address=address, count=count,
                                                            no_response_expected=no_response_expected)
            if not response.isError():
                self.response_handle_command(slave, self.CodeReadHoldingRegisters,response)
                # return response.registers
            else:
                return None
        except:
            return None

    def add_read_holding_registers_queue(self, address: int, count: int, *, slave: int = 1,
                               no_response_expected: bool = False):
        request_parameter = ModbusRequestParameter()
        request_parameter.code=self.CodeReadHoldingRegisters
        request_parameter.count=count
        request_parameter.address = address
        request_parameter.slave = slave
        request_parameter.no_response_expected = no_response_expected

        self.request_queue.put(request_parameter)

        self.request_parameter.init()


    def modbus_rtu_service_close(self):
        """关闭 modbus_client"""
        if self.modbus_client and self.modbus_client.connected:
            self.modbus_client.close()
            self.is_connected = False

    def response_handle_command(self, slave, code, response):
        """根据response调用相应的处理函数"""
        handler = self.modbus_response_handlers.get(code)
        if handler:
            handler(slave,response)
        else:
            print(f"Unknown code: {code}")

    def handler_read_coils_response(self, slave, response):
        """read_coils后处理"""
        # print(f'# handler_read_coils_response:{response}')
        pass

    def handler_read_discrete_inputs_response(self, slave, response):
        """read_discrete_inputs后处理"""
        # print(f'# handler_read_discrete_inputs_response:{response}')
        pass

    def handler_read_holding_registers_response(self, slave, response):
        """read_holding_registers后处理"""
        # print(f'# handler_read_holding_registers_response:{response}')
        pass

    def handler_read_input_registers_response(self, slave, response):
        """read_input_registers后处理"""
        # print(f'# handler_read_input_registers_response:{response}')
        pass

    def handler_write_single_coil_response(self, slave, response):
        """write_single_coil后处理"""
        # print(f'# handler_write_single_coil_response:{response}')
        pass

    def handler_write_register_response(self, slave, response):
        """write_register_response后处理"""
        # print(f'# handler_write_register_response:{response}')
        pass

