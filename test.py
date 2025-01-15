import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Callable, Any
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


class CANoeBenchModbus(object):
    CodeReadCoils = 0x01
    CodeReadDiscreteInputs = 0x02
    CodeReadHoldingRegisters = 0x03
    CodeReadInputRegisters = 0x04
    CodeWriteSingleCoil = 0x05
    CodeWriteRegister = 0x06

    def __init__(self,
                 serial_port: str = 'com6',
                 serial_baud_rate: int = 115200,
                 serial_bytesize: int = 8,
                 serial_parity: str = "N",
                 serial_stop_bits: int = 1,
                 serial_timeout: int = 1,
                 use_thread_pool: bool = False,
                 max_workers: int = 4):  # 默认最大工作线程数为4

        # modbus RTU config
        self.modbus_client = None
        self.port = serial_port
        self.serial_baud_rate = serial_baud_rate
        self.serial_bytesize = serial_bytesize
        self.serial_parity = serial_parity
        self.serial_stop_bits = serial_stop_bits
        self.serial_timeout = serial_timeout

        self.use_thread_pool = use_thread_pool
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers) if use_thread_pool else None
        self._lock = threading.Lock()  # 添加锁，防止并发访问modbus_client

        self.modbus_response_handlers = {
            self.CodeReadCoils: self.handler_read_coils_response,
            self.CodeReadDiscreteInputs: self.handler_read_discrete_inputs_response,
            self.CodeReadHoldingRegisters: self.handler_read_holding_registers_response,
            self.CodeReadInputRegisters: self.handler_read_input_registers_response,
            self.CodeWriteSingleCoil: self.handler_write_single_coil_response,
            self.CodeWriteRegister: self.handler_write_register_response,
        }

    def create_modbus_rtu_service(self) -> bool:
        """创建 Modbus RTU 服务，返回是否连接成功"""
        try:
            with self._lock:
                self.modbus_client = ModbusSerialClient(
                    port=self.port,
                    baudrate=self.serial_baud_rate,
                    bytesize=self.serial_bytesize,
                    parity=self.serial_parity,
                    stopbits=self.serial_stop_bits,
                    timeout=self.serial_timeout,
                )
                if not self.modbus_client.connect():
                    print(f"无法连接到从站进行写入")
                    return False
                return True
        except ModbusException as e:
            print(f"向从站写入数据时发生错误: {e}")
            return False

    def _execute_modbus_operation(self, func: Callable, *args, **kwargs) -> Any:
        """内部函数，用于执行 Modbus 操作，支持单线程或线程池"""
        if self.use_thread_pool:
            future = self.thread_pool.submit(func, *args, **kwargs)
            return future
        else:
            return func(*args, **kwargs)

    def write_register(self, address: int, value: int, *, slave: int = 1, no_response_expected: bool = False) -> \
            Optional[List[int]]:
        """写从站寄存器"""

        def _write_register():
            with self._lock:
                if not self.modbus_client:
                    print("Modbus client not initialized.")
                    return None
                try:
                    response = self.modbus_client.write_register(slave=slave, address=address, value=value,
                                                                 no_response_expected=no_response_expected)
                    if not response.isError():
                        self.handle_command(self.CodeWriteRegister, response)
                        # return response.registers
                    else:
                        return None
                except Exception as e:
                    print(f"Error writing register: {e}")
                    return None

        return self._execute_modbus_operation(_write_register)

    def read_holding_registers(self, address: int, count: int, *, slave: int = 1, no_response_expected: bool = False) -> \
            Optional[List[int]]:
        """读从站寄存器"""

        def _read_holding_registers():
            with self._lock:
                if not self.modbus_client:
                    print("Modbus client not initialized.")
                    return None
                try:
                    response = self.modbus_client.read_holding_registers(slave=slave, address=address, count=count,
                                                                         no_response_expected=no_response_expected)
                    if not response.isError():
                        self.handle_command(self.CodeReadHoldingRegisters, response)
                        # return response.registers
                    else:
                        return None
                except Exception as e:
                    print(f"Error reading holding registers: {e}")
                    return None

        return self._execute_modbus_operation(_read_holding_registers)

    def create_modbus_rtu_service_close(self):
        """关闭 modbus_client"""
        with self._lock:
            if self.modbus_client:
                self.modbus_client.close()
                self.modbus_client = None

    def shutdown_thread_pool(self):
        """关闭线程池"""
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)

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



if __name__ == '__main__':
    # # 单线程示例
    # modbus_single = CANoeBenchModbus(serial_port='com6', use_thread_pool=False)
    # if modbus_single.create_modbus_rtu_service():
    #     print("Single thread Modbus connection successful.")
    #
    #     write_result = modbus_single.write_register(address=0, value=0)
    #     if write_result is not None:
    #         print(f"Write register result: {write_result}")
    #
    #     read_result = modbus_single.read_holding_registers(address=0, count=3)
    #     if read_result is not None:
    #         print(f"Read holding registers result: {read_result}")
    #
    #     modbus_single.create_modbus_rtu_service_close()
    # else:
    #     print("Single thread Modbus connection failed.")

    # 线程池示例
    modbus_pool = CANoeBenchModbus(serial_port='com6', use_thread_pool=True, max_workers=4)
    if modbus_pool.create_modbus_rtu_service():
        print("Thread pool Modbus connection successful.")

        futures = []
        for i in range(1):
            write_future0 = modbus_pool.write_register(address=0 + i, value=0 + i, slave=1)
            write_future = modbus_pool.write_register(address=0 + i, value=0 + i)
            read_future = modbus_pool.read_holding_registers(address=0 + i, count=1)
            futures.append((write_future0,write_future, read_future))
        print('----')
        for i, (write_future0,write_future, read_future) in enumerate(futures):
            write_result0 = write_future0.result()
            if write_result0 is not None:
                print(f"Write0 register result {i}: {write_result0}")

            write_result = write_future.result()
            if write_result is not None:
                print(f"Write register result {i}: {write_result}")

            read_result = read_future.result()
            if read_result is not None:
                print(f"Read holding registers result {i}: {read_result}")

        modbus_pool.create_modbus_rtu_service_close()
        modbus_pool.shutdown_thread_pool()
    else:
        print("Thread pool Modbus connection failed.")
