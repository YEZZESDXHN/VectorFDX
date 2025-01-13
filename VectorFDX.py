import socket

class VectorFDX(object):
    # 定义命令代码
    COMMAND_CODE_START = 0x0001
    COMMAND_CODE_STOP = 0x0002
    COMMAND_CODE_KEY = 0x0003
    COMMAND_CODE_STATUS = 0x0004
    COMMAND_CODE_DATA_EXCHANGE = 0x0005
    COMMAND_CODE_DATA_REQUEST = 0x0006
    COMMAND_CODE_DATA_ERROR = 0x0007
    COMMAND_CODE_FREE_RUNNING_REQUEST = 0x0008
    COMMAND_CODE_FREE_RUNNING_CANCEL = 0x0009
    COMMAND_CODE_STATUS_REQUEST = 0x000A
    COMMAND_CODE_STATUS_REQUEST_2 = 0x000B # 注意这里，原代码重复定义了COMMAND_CODE_STATUS
    COMMAND_CODE_INCREMENT_TIME = 0x0011
    COMMAND_CODE_FUNCTION_CALL = 0x000C
    COMMAND_CODE_FUNCTION_CALL_ERROR = 0x000D

    def __init__(self, fdx_major_version=2, fdx_minor_version=0, local_ip='127.0.0.1', local_port=12345, target_ip='127.0.0.1', target_port=12346):
        self.max_len = 0xffe3
        self.fdx_data = b''  # 用于存储 FDX 数据
        self.fdx_signature = b'\x43\x41\x4E\x6F\x65\x46\x44\x58'
        self.fdx_major_version = fdx_major_version.to_bytes(1, 'big')
        self.fdx_minor_version = fdx_minor_version.to_bytes(1, 'big')
        self.number_of_commands = 0  # 初始化为0，在添加命令时累加
        self.sequence_number = 1  # 使用更清晰的名称
        self.fdx_protocol_flags = 1  # Byte Order, Little Endian (0) or Big Endian (1)
        self.reserved = int(0).to_bytes(1, 'big')

        self.udp_socket = None
        self.local_ip = local_ip
        self.local_port = local_port

        self.target_ip = target_ip
        self.target_port = target_port

    def create_udp_socket(self):
        """创建 UDP 套接字并绑定到本地地址"""
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        local_address = (self.local_ip, self.local_port)
        self.udp_socket.bind(local_address)

    def build_fdx_header(self):
        """构建 FDX 头部"""
        header = (
            self.fdx_signature +
            self.fdx_major_version +
            self.fdx_minor_version +
            self.number_of_commands.to_bytes(2, 'big') +
            self.sequence_number.to_bytes(2, 'big') +
            self.fdx_protocol_flags.to_bytes(2, 'big') +
            self.reserved
        )
        return header

    def _add_command(self, command_bytes: bytes):
        """添加命令并更新 FDX 数据"""
        if not isinstance(command_bytes, bytes):
            raise TypeError("command_bytes must be bytes")

        if not self.fdx_data:
            self.fdx_data = self.build_fdx_header()
        self.fdx_data += command_bytes
        self.number_of_commands += 1
        # 更新命令数量到header
        self.fdx_data = bytearray(self.fdx_data)
        number_of_commands_bytes = self.number_of_commands.to_bytes(2, 'big')
        self.fdx_data[10] = number_of_commands_bytes[0]
        self.fdx_data[11] = number_of_commands_bytes[1]
        self.fdx_data = bytes(self.fdx_data)


    def _create_command(self, command_code: int, command_data: bytes = b""):
        """创建 FDX 命令"""
        command_size = 4 + len(command_data)
        command = command_size.to_bytes(2, 'big') + command_code.to_bytes(2, 'big') + command_data
        return command

    def start_command(self, is_add_command: bool = False):
        """创建并添加开始命令"""
        command = self._create_command(self.COMMAND_CODE_START)
        if is_add_command:
            self._add_command(command)
        else:
            self.fdx_data = self.build_fdx_header() + command
            self.number_of_commands = 1
            self.sequence_number += 1
        print(self.fdx_data)


    def stop_command(self, is_add_command: bool = False):
        """创建并添加停止命令"""
        command = self._create_command(self.COMMAND_CODE_STOP)
        if is_add_command:
            self._add_command(command)
        else:
            self.fdx_data = self.build_fdx_header() + command
            self.number_of_commands = 1
            self.sequence_number += 1
        print(self.fdx_data)

    def key_command(self, canoe_key_code: int, is_add_command: bool = False):
        """创建并添加按键命令"""
        if not isinstance(canoe_key_code, int):
            raise TypeError("canoe_key_code must be an integer")
        canoe_key_code_bytes = canoe_key_code.to_bytes(4, 'big')
        command = self._create_command(self.COMMAND_CODE_KEY, canoe_key_code_bytes)
        if is_add_command:
            self._add_command(command)
        else:
            self.fdx_data = self.build_fdx_header() + command
            self.number_of_commands = 1
            self.sequence_number += 1
        print(self.fdx_data)

    def datarequest_command(self, group_id: int, is_add_command: bool = False):
        """创建并添加数据请求命令"""
        if not isinstance(group_id, int):
            raise TypeError("group_id must be an integer")
        group_id_bytes = group_id.to_bytes(2, 'big')
        command = self._create_command(self.COMMAND_CODE_DATA_REQUEST, group_id_bytes)
        if is_add_command:
            self._add_command(command)
        else:
            self.fdx_data = self.build_fdx_header() + command
            self.number_of_commands = 1
            self.sequence_number += 1
        print(self.fdx_data)

    def data_exchange_command(self, group_id: int, data_bytes: bytes, is_add_command: bool = False):
        """创建并添加数据交换命令"""
        if not isinstance(group_id, int):
            raise TypeError("group_id must be an integer")
        if not isinstance(data_bytes, bytes):
            raise TypeError("data_bytes must be bytes")
        data_size = len(data_bytes)
        if data_size > self.max_len - 16:
            raise ValueError(f"Data size {data_size} exceeds maximum allowed {self.max_len - 16}")
        data_size_bytes = data_size.to_bytes(2, 'big')
        group_id_bytes = group_id.to_bytes(2, 'big')
        command = self._create_command(self.COMMAND_CODE_DATA_EXCHANGE, group_id_bytes + data_size_bytes + data_bytes)
        if is_add_command:
            self._add_command(command)
        else:
            self.fdx_data = self.build_fdx_header() + command
            self.number_of_commands = 1
            self.sequence_number += 1
        print(self.fdx_data)

    def send_fdx_data(self):
        """发送 FDX 数据报"""
        if not self.fdx_data:
            print("No FDX data to send.")
            return
        target_address = (self.target_ip, self.target_port)
        try:
            self.udp_socket.sendto(self.fdx_data, target_address)
            print(f"Sent {len(self.fdx_data)} bytes of FDX data to {target_address}")
            self.fdx_data = b''  # 发送后清空数据
        except Exception as e:
            print(f"Error sending UDP data: {e}")

    def close_socket(self):
        """关闭 UDP 套接字"""
        if self.udp_socket:
            self.udp_socket.close()
            print("UDP socket closed.")

if __name__ == '__main__':
    fdx = VectorFDX()
    fdx.data_exchange_command(1, b'\x01\x02\x03\x04', True)
    fdx.stop_command(True)
