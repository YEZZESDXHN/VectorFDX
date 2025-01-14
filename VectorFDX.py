import socket
import struct
import threading


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
    COMMAND_CODE_SEQUENCE_NUMBER_ERROR = 0x000B
    COMMAND_CODE_INCREMENT_TIME = 0x0011
    COMMAND_CODE_FUNCTION_CALL = 0x000C
    COMMAND_CODE_FUNCTION_CALL_ERROR = 0x000D


    def __init__(self, fdx_major_version=2, fdx_minor_version=0, local_ip='127.0.0.1', local_port=2000, target_ip='127.0.0.1', target_port=2001):
        self.max_len = 0xffe3
        self.fdx_data = b''  # 用于存储 FDX 数据
        self.fdx_signature = b'\x43\x41\x4E\x6F\x65\x46\x44\x58'
        self.fdx_major_version = fdx_major_version.to_bytes(1, 'little')
        self.fdx_minor_version = fdx_minor_version.to_bytes(1, 'little')
        self.number_of_commands = 0  # 初始化为0，在添加命令时累加
        self.sequence_number = 1
        self.fdx_protocol_flags = 1  # Byte Order, Little Endian (0) or Big Endian (1)
        if self.fdx_protocol_flags == 1:
            self.fdx_byte_order = 'big' # According to fdx_protocol_flags
        else:
            self.fdx_byte_order = 'little'
        self.reserved = int(0).to_bytes(1, 'little')

        self.udp_socket = None
        self.local_ip = local_ip
        self.local_port = local_port

        self.target_ip = target_ip
        self.target_port = target_port
        self.receive_thread = None
        self.is_running = False

        # self.received_data = []  # 存储接收到的数据
        self.command_handlers = {
            self.COMMAND_CODE_START: self.handle_start_command,
            self.COMMAND_CODE_STOP: self.handle_stop_command,
            self.COMMAND_CODE_KEY: self.handle_key_command,
            # self.COMMAND_CODE_STATUS: self.handle_status_command,
            self.COMMAND_CODE_DATA_EXCHANGE: self.handle_data_exchange_command,
            self.COMMAND_CODE_DATA_REQUEST: self.handle_data_request_command,
            self.COMMAND_CODE_DATA_ERROR: self.handle_data_error,
            self.COMMAND_CODE_FREE_RUNNING_REQUEST: self.handle_free_running_request,
            self.COMMAND_CODE_FREE_RUNNING_CANCEL: self.handle_free_running_cancel,
            # self.COMMAND_CODE_STATUS_REQUEST: self.handle_status_request,
            self.COMMAND_CODE_SEQUENCE_NUMBER_ERROR: self.handle_sequence_number_error,
            # self.COMMAND_CODE_INCREMENT_TIME: self.handle_increment_time,
            # self.COMMAND_CODE_FUNCTION_CALL: self.handle_function_call,
            self.COMMAND_CODE_FUNCTION_CALL_ERROR: self.handle_function_call_error,
        }

    def create_udp_socket(self):
        """创建 UDP 套接字并绑定到本地地址，设置为非阻塞模式"""
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        local_address = (self.local_ip, self.local_port)
        self.udp_socket.bind(local_address)

    def start_receiving(self):
        """启动接收线程"""
        if not self.udp_socket:
            self.create_udp_socket()
        self.is_running = True
        self.receive_thread = threading.Thread(target=self._receive_data_thread, daemon=True)
        self.receive_thread.start()

    def stop_receiving(self):
        """停止接收线程"""
        self.is_running = False
        if self.receive_thread:
            self.receive_thread.join()
            self.receive_thread = None


    def _receive_data_thread(self):
        """接收数据的线程函数"""
        while self.is_running:
            try:
                data, addr = self.udp_socket.recvfrom(65535)
                if not data.startswith(self.fdx_signature):
                    print("Invalid FDX signature.")
                else:
                    self.parse_fdx_data(data, addr)
                # print(f"Received data from {addr}: {data.hex()}")
            except Exception as e:
                if self.is_running:  # 仅当 is_running 为 True 时才打印错误
                    print(f"Error receiving data: {e}")
                    # 如果套接字被关闭，recvfrom 会抛出异常，正常退出循环
                break
    def parse_fdx_data(self, data, addr):
        """解析 FDX 数据"""
        try:
            # 检查数据长度是否足够
            header_len = 16
            if len(data) < header_len + 4:
                print(f"Data too short: {len(data)} bytes")
                return
            fdx_signature, major_version, minor_version, number_of_commands, sequence_number, protocol_flags, reserved = struct.unpack(f'<8sBBHHBB', data[:header_len])
            if fdx_signature != self.fdx_signature:
                raise ValueError("Invalid FDX signature.")
            if protocol_flags == 1:
                byteorder = 'big'
            elif protocol_flags == 0:
                byteorder = 'little'
            else:
                byteorder = 'big'
            # print(f"Received data: signature={signature.hex()}, major_version={major_version}, minor_version={minor_version}, number_of_commands={number_of_commands}, sequence_number={sequence_number}, protocol_flags={protocol_flags}, reserved={reserved}")

            # 从头部之后开始解析命令
            offset = header_len
            for _ in range(number_of_commands):
                # 检查剩余数据长度是否足够
                if offset + 4 > len(data):
                    raise ValueError(f"Data too short for command: {len(data) - offset} bytes")
                command_size = int.from_bytes(data[offset:offset + 2], byteorder)
                command_code = int.from_bytes(data[offset + 2:offset + 4], byteorder)
                command_data = data[offset + 4:offset + command_size]

                # print(f"command_size={command_size}, command_code={command_code}, command_data={command_data.hex()}")

                # 调用命令处理函数
                self.handle_command(command_code, command_data, addr)
                offset += command_size

        except Exception as e:
            print(f"Error parsing FDX data: {e}")

    def handle_command(self, command_code, command_data, addr):
        """根据命令代码调用相应的处理函数"""
        handler = self.command_handlers.get(command_code)
        if handler:
            handler(command_data, addr)
        else:
            print(f"Unknown command code: {command_code}")

    def handle_start_command(self, command_data, addr):
        """处理开始命令"""
        pass

    def handle_stop_command(self, command_data, addr):
        """处理停止命令"""
        pass

    def handle_key_command(self, command_data, addr):
        """处理按键命令"""
        pass

    def handle_data_exchange_command(self, command_data, addr):
        """处理数据交换命令"""
        pass

    def handle_data_request_command(self, command_data, addr):
        """处理数据请求命令"""
        pass

    def handle_data_error(self):
        """处理数据异常"""
        pass

    def handle_free_running_request(self):
        """处理自由运行请求"""
        pass

    def handle_free_running_cancel(self):
        """处理取消自由运行"""
        pass
    def handle_sequence_number_error(self):
        """处理序列错误"""
        pass

    def handle_function_call_error(self):
        """处理function触发异常"""
        pass



    def build_fdx_header(self):
        """构建 FDX 头部"""
        self.number_of_commands = 1
        if self.fdx_protocol_flags == 1:
            self.fdx_byte_order = 'big'
        else:
            self.fdx_byte_order = 'little'
        header = (
            self.fdx_signature +
            self.fdx_major_version +
            self.fdx_minor_version +
            self.number_of_commands.to_bytes(2, 'little') +
            self.sequence_number.to_bytes(2, 'little') +
            self.fdx_protocol_flags.to_bytes(1, 'little') +
            self.reserved
        )
        self.sequence_number += 1
        if self.sequence_number == 0x7FFF:
            self.sequence_number = 1
        # print(header.hex(' '))
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
        number_of_commands_bytes = self.number_of_commands.to_bytes(2, self.fdx_byte_order)
        self.fdx_data[10] = number_of_commands_bytes[0]
        self.fdx_data[11] = number_of_commands_bytes[1]
        self.fdx_data = bytes(self.fdx_data)


    def _create_command(self, command_code: int, command_data: bytes = b""):
        """创建 FDX 命令"""
        command_size = 4 + len(command_data)
        command = command_size.to_bytes(2, self.fdx_byte_order) + command_code.to_bytes(2, self.fdx_byte_order) + command_data
        return command

    def start_command(self, is_add_command: bool = False):
        """创建并添加开始命令"""
        command = self._create_command(self.COMMAND_CODE_START)
        if is_add_command:
            self._add_command(command)
        else:
            self.fdx_data = self.build_fdx_header() + command
        # print(f"start_command: {self.fdx_data.hex(' ').upper()}")

    def stop_command(self, is_add_command: bool = False):
        """创建并添加停止命令"""
        command = self._create_command(self.COMMAND_CODE_STOP)
        if is_add_command:
            self._add_command(command)
        else:
            self.fdx_data = self.build_fdx_header() + command
        # print(f"stop_command: {self.fdx_data.hex(' ').upper()}")

    def key_command(self, canoe_key_code: int, is_add_command: bool = False):
        """创建并添加按键命令"""
        if not isinstance(canoe_key_code, int):
            raise TypeError("canoe_key_code must be an integer")
        canoe_key_code_bytes = canoe_key_code.to_bytes(4, self.fdx_byte_order)
        command = self._create_command(self.COMMAND_CODE_KEY, canoe_key_code_bytes)
        if is_add_command:
            self._add_command(command)
        else:
            self.fdx_data = self.build_fdx_header() + command
        # print(f"key_command: {self.fdx_data.hex(' ').upper()}")

    def datarequest_command(self, group_id: int, is_add_command: bool = False):
        """创建并添加数据请求命令"""
        if not isinstance(group_id, int):
            raise TypeError("group_id must be an integer")
        group_id_bytes = group_id.to_bytes(2, self.fdx_byte_order)
        command = self._create_command(self.COMMAND_CODE_DATA_REQUEST, group_id_bytes)
        if is_add_command:
            self._add_command(command)
        else:
            self.fdx_data = self.build_fdx_header() + command
        # print(f"datarequest_command: {self.fdx_data.hex(' ').upper()}")

    def data_exchange_command(self, group_id: int, data_bytes: bytes, is_add_command: bool = False):
        """创建并添加数据交换命令"""
        if not isinstance(group_id, int):
            raise TypeError("group_id must be an integer")
        if not isinstance(data_bytes, bytes):
            raise TypeError("data_bytes must be bytes")
        data_size = len(data_bytes)
        if data_size > self.max_len - 16:
            raise ValueError(f"Data size {data_size} exceeds maximum allowed {self.max_len - 16}")
        data_size_bytes = data_size.to_bytes(2, self.fdx_byte_order)
        group_id_bytes = group_id.to_bytes(2, self.fdx_byte_order)
        command = self._create_command(self.COMMAND_CODE_DATA_EXCHANGE, group_id_bytes + data_size_bytes + data_bytes)
        if is_add_command:
            if len(self.fdx_data) < 20:
                raise ValueError("must build fdx header before add command")
            self._add_command(command)
        else:
            self.fdx_data = self.build_fdx_header() + command
        # print(f"data_exchange_command: {self.fdx_data.hex(' ').upper()}")

    def send_fdx_data(self):
        """发送 FDX 数据报"""
        if not self.fdx_data:
            print("No FDX data to send.")
            return
        target_address = (self.target_ip, self.target_port)
        try:
            self.udp_socket.sendto(self.fdx_data, target_address)
            # print(f"Sent {len(self.fdx_data)} bytes of FDX data to {target_address}")
            self.fdx_data = b''  # 发送后清空数据
        except Exception as e:
            print(f"Error sending UDP data: {e}")

    def close_socket(self):
        """关闭 UDP 套接字"""
        self.stop_receiving()
        if self.udp_socket:
            self.udp_socket.close()
            print("UDP socket closed.")



if __name__ == '__main__':
    fdx = VectorFDX(target_port=2809)
    fdx.create_udp_socket()
    # fdx.start_receiving()
    fdx.start_command()
    fdx.send_fdx_data()
    # time.sleep(1)
    # fdx.data_exchange_command(1, b'\x01\x02\x03\x04')
    # fdx.send_fdx_data()
    # time.sleep(1)
    # fdx.stop_command(True)
    # fdx.send_fdx_data()
    # time.sleep(1)
    # received_data = fdx.get_received_data()
    # print(f"Received data: {received_data}")
    # fdx.close_socket()

