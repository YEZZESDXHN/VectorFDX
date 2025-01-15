from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


class CANoeBenchModbus(object):
    ReadCoils = 0x01
    ReadDiscreteInputs = 0x02
    ReadHoldingRegisters = 0x03
    ReadInputRegisters = 0x04
    WriteSingleCoil = 0x05
    WriteRegister = 0x06

    def __init__(self,
                 serial_baud_rate: int = 115200,
                 serial_bytesize: int = 8,
                 serial_parity="N",
                 serial_stop_bits: int = 1,
                 serial_timeout: int = 1):

        # modbus RTU config
        self.modbus_client = None
        self.port = 'com6'
        self.serial_baud_rate = serial_baud_rate
        self.serial_bytesize = serial_bytesize
        self.serial_parity = serial_parity
        self.serial_stop_bits = serial_stop_bits
        self.serial_timeout = serial_timeout

        self.modbus_response_handlers = {
            self.ReadCoils: self.handler_read_coils_response,
            self.ReadDiscreteInputs: self.handler_read_discrete_inputs_response,
            self.ReadHoldingRegisters: self.handler_read_holding_registers_response,
            self.ReadInputRegisters: self.handler_read_input_registers_response,
            self.WriteSingleCoil: self.handler_write_single_coil_response,
            self.WriteRegister: self.handler_write_register_response,

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
            )
            if not self.modbus_client.connect():
                print(f"无法连接到从站进行写入")
                return
            print(self.modbus_client)
            print(type(self.modbus_client))
        except ModbusException as e:
            print(f"向从站写入数据时发生错误: {e}")

    def write_register(self, modbus_client: ModbusSerialClient, address: int, value: int, *, slave: int = 1, no_response_expected: bool = False):
        """写从站寄存器"""
        try:
            response = modbus_client.write_register(slave=slave, address=address, value=value, no_response_expected=no_response_expected)
            if not response.isError():
                return response.registers
            else:
                return None
        except:
            return None

    def read_holding_registers(self, modbus_client: ModbusSerialClient, address: int, count: int, *, slave: int = 1, no_response_expected: bool = False):
        """读从站寄存器"""
        try:
            response = modbus_client.read_holding_registers(slave=slave, address=address, count=count, no_response_expected=no_response_expected)
            if not response.isError():
                return response.registers
            else:
                return None
        except:
            return None

    def create_modbus_rtu_service_close(self):
        """关闭 modbus_client"""
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
        pass

    def handler_read_discrete_inputs_response(self, response):
        """read_discrete_inputs后处理"""
        pass

    def handler_read_holding_registers_response(self, response):
        """read_holding_registers后处理"""
        pass

    def handler_read_input_registers_response(self, response):
        """read_input_registers后处理"""
        pass

    def handler_write_single_coil_response(self, response):
        """write_single_coil后处理"""
        pass

    def handler_write_register_response(self, response):
        """write_register_response后处理"""
        pass

if __name__ == '__main__':
    client = CANoeBenchModbus()
    client.create_modbus_rtu_service()
    client.write_register(slave=1, address=0, value=0)
    client.read_holding_registers(slave=1, address=0, count=2)
    # for _ in range(10):
    #     client.write_register(address=0,value=1)
    #     client.write_register(address=0, value=0)

