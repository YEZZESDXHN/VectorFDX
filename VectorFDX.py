import socket
import struct
import threading
from typing import Literal


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
    COMMAND_CODE_FUNCTION_CALL = 0x000C
    COMMAND_CODE_FUNCTION_CALL_ERROR = 0x000D
    COMMAND_CODE_INCREMENT_TIME = 0x0011

    # Data Error Code
    DataErrorCode_MeasurmentNotRunning = 1
    DataErrorCode_GroupIdInvalid = 2
    DataErrorCode_DataSizeToLarge = 3

    # State of Measurement
    MeasurementState_NotRunning = 1
    MeasurementState_PreStart = 2
    MeasurementState_Running = 3
    MeasurementState_Stop = 4

    # Free Running Flags
    FreeRunningFlag_TransmitAtPreStart = 1
    FreeRunningFlag_TransmitAtStop = 2
    FreeRunningFlag_TransmitCyclic = 4
    FreeRunningFlag_TransmitAtTrigger = 8


    def __init__(self, UDP_Or_TCP: Literal["UDP", "TCP"] = 'UDP',
                 fdx_major_version: int = 2, fdx_minor_version: int = 1,
                 fdx_byte_order: Literal["little", "big"] = 'big',
                 local_ip='127.0.0.1', local_port: int = 2000,
                 target_ip='127.0.0.1', target_port: int = 2001):
        self.UDP_Or_TCP = UDP_Or_TCP
        self.max_len = 0xffe3
        self.fdx_data = b''  # 用于存储 FDX 数据
        self.fdx_signature = b'\x43\x41\x4E\x6F\x65\x46\x44\x58'
        self.fdx_major_version = fdx_major_version.to_bytes(1, fdx_byte_order)
        self.fdx_minor_version = fdx_minor_version.to_bytes(1, fdx_byte_order)
        self.number_of_commands = 0  # 初始化为0，在添加命令时累加
        self.sequence_number = 1
        self.dgramLen = 0
        self.fdx_byte_order = fdx_byte_order
        if self.fdx_byte_order == 'big':
            self.fdx_protocol_flags = 1
        else:
            self.fdx_protocol_flags = 0

        self.reserved = 0

        self.socket = None
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
            self.COMMAND_CODE_STATUS: self.handle_status_command,
            self.COMMAND_CODE_DATA_EXCHANGE: self.handle_data_exchange_command,
            self.COMMAND_CODE_DATA_REQUEST: self.handle_data_request_command,
            self.COMMAND_CODE_DATA_ERROR: self.handle_data_error,
            self.COMMAND_CODE_FREE_RUNNING_REQUEST: self.handle_free_running_request,
            self.COMMAND_CODE_FREE_RUNNING_CANCEL: self.handle_free_running_cancel,
            self.COMMAND_CODE_STATUS_REQUEST: self.handle_status_request,
            self.COMMAND_CODE_SEQUENCE_NUMBER_ERROR: self.handle_sequence_number_error,
            self.COMMAND_CODE_FUNCTION_CALL: self.handle_function_call,
            self.COMMAND_CODE_FUNCTION_CALL_ERROR: self.handle_function_call_error,
            self.COMMAND_CODE_INCREMENT_TIME: self.handle_increment_time,
        }

    def create_socket(self):
        if self.UDP_Or_TCP == 'UDP':
            self.create_udp_socket()
        elif self.UDP_Or_TCP == 'TCP':
            self.create_tcp_socket()
        else:
            print(f"不支持{self.UDP_Or_TCP}协议")

    def create_udp_socket(self):
        """创建 UDP 套接字并绑定到本地地址"""
        try:
            if self.socket is None:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                local_address = (self.local_ip, self.local_port)
                # self.socket.bind(local_address)
                self.socket.settimeout(1)
            else:
                try:
                    self.close_socket()
                except Exception as e:
                    print(e)
        except:
            self.socket = None

    def create_tcp_socket(self):  # 客户端
        """创建 TCP客户端 套接字并绑定到本地地址"""
        try:
            if self.socket is None:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                # self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                local_address = (self.local_ip, self.local_port)
                service_address = (self.target_ip, self.target_port)
                # self.socket.bind(local_address)
                self.socket.settimeout(1)
                self.socket.connect(service_address)
            else:
                try:
                    self.close_socket()
                except Exception as e:
                    print(e)
        except OSError as e:
            if e.errno == 98:  # "Address already in use" error
                print(f"错误: 端口 {self.local_port} 已经被占用.")
            else:
                print(f"error: {e}")
            self.close_socket()

    # def create_tcp_socket(self):  # 服务端
    #     """创建 TCP服务端 套接字并绑定到本地地址"""
    #     self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #     local_address = (self.local_ip, self.local_port)
    #     self.socket.bind(local_address)
    #     self.socket.listen(1)  # 最大连接数
    #     conn, addr = self.socket.accept()
    #     print(f"客户端 {addr} 已连接")

    def start_receiving(self):
        """启动接收线程"""
        if not self.socket:
            self.create_socket()
        if self.socket:
            self.is_running = True
            self.receive_thread = threading.Thread(target=self._receive_data_thread, daemon=True)
            self.receive_thread.start()

    def stop_receiving(self):
        """停止接收线程"""
        self.is_running = False
        if self.receive_thread:
            self.receive_thread.join()

    def _receive_data_thread(self):
        """接收数据的线程函数"""
        while self.is_running:
            if self.UDP_Or_TCP == "UDP":
                try:
                    data, addr = self.socket.recvfrom(65535)
                    if not data.startswith(self.fdx_signature):
                        print("Invalid FDX signature.")
                    else:
                        self.parse_fdx_data(data, addr)
                    # print(f"Received data from {addr}: {data.hex()}")
                except socket.timeout:
                    pass
                    # print('socket.timeout')
                except Exception as e:
                    if True:  # 仅当 is_running 为 True 时才打印错误
                        print(f"Error receiving data: {e}")
                        if e.args[0] == 10054:  # [WinError 10054] 远程主机强迫关闭了一个现有的连接。 端口不可达
                            pass
                        else:
                            break
            else:
                try:
                    data = self.socket.recv(65535)
                    if not data.startswith(self.fdx_signature):
                        print("Invalid FDX signature.")
                    else:
                        self.parse_fdx_data(data)
                    # print(f"Received data from {addr}: {data.hex()}")
                except socket.timeout:
                    pass
                    # print('socket.timeout')
                except Exception as e:
                    if True:  # 仅当 is_running 为 True 时才打印错误
                        print(f"Error receiving data: {e}")
                        break

    def parse_fdx_data(self, data, addr=None):
        """解析 FDX 数据"""
        # print(f"rec :{data.hex(' ')}")
        try:
            # 检查数据长度是否足够
            header_len = 16
            if len(data) < header_len + 4:
                print(f"Data too short: {len(data)} bytes")
                return

            if data[14] == 1: # big
                fdx_signature, major_version, minor_version, number_of_commands, sequence_number, protocol_flags, reserved = struct.unpack(
                    f'>8sBBHHBB', data[:header_len])
            else:
                fdx_signature, major_version, minor_version, number_of_commands, sequence_number, protocol_flags, reserved = struct.unpack(
                    f'<8sBBHHBB', data[:header_len])



            if fdx_signature != self.fdx_signature:
                raise ValueError("Invalid FDX signature.")
            if protocol_flags == 1:
                byteorder = 'big'
            elif protocol_flags == 0:
                byteorder = 'little'
            else:
                byteorder = 'big'
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
                self.handle_command(command_code, command_data, addr, byteorder)
                offset += command_size

        except Exception as e:
            print(f"Error parsing FDX data: {e}")

    def handle_command(self, command_code, command_data, addr, byteorder):
        """根据命令代码调用相应的处理函数"""
        handler = self.command_handlers.get(command_code)
        if handler:
            handler(command_data, addr, byteorder)
        else:
            print(f"Unknown command code: {command_code}")

    def handle_start_command(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理开始命令"""
        pass

    def handle_stop_command(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理停止命令"""
        pass

    def handle_key_command(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理按键命令"""
        ret = {'remote_addr': addr}
        if byteorder == 'big':
            canoekeycode = struct.unpack(f'>I', command_data)
        else:
            canoekeycode = struct.unpack(f'<I', command_data)

        ret['canoekeycode'] = canoekeycode
        return ret

    def handle_status_command(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理状态命令"""
        ret = {'remote_addr': addr}
        if byteorder == 'big':
            measurementstate, _, timestamps = struct.unpack(f'>B3pQ', command_data)
        else:
            measurementstate, _, timestamps = struct.unpack(f'<B3pQ', command_data)

        ret['measurementstate'] = measurementstate
        ret['timestamps'] = timestamps
        return ret

    def handle_data_exchange_command(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理数据交换命令"""
        ret = {'remote_addr': addr}
        if byteorder == 'big':
            groupid, datasize = struct.unpack(f'>HH', command_data[:4])
            databytes = command_data[4:]
        else:
            groupid, datasize = struct.unpack(f'<HH', command_data[:4])
            databytes = command_data[4:]

        ret['groupid'] = groupid
        ret['datasize'] = datasize
        ret['databytes'] = databytes
        return ret

    def handle_data_request_command(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理数据请求命令"""
        ret = {'remote_addr': addr}
        if byteorder == 'big':
            groupid = struct.unpack(f'>H', command_data)
        else:
            groupid = struct.unpack(f'<H', command_data)

        ret['groupid'] = groupid
        return ret

    def handle_data_error(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理数据异常"""
        ret = {'remote_addr': addr}
        if byteorder == 'big':
            groupid, dataerrorcode = struct.unpack(f'>HH', command_data)
        else:
            groupid, dataerrorcode = struct.unpack(f'<HH', command_data)

        ret['groupid'] = groupid
        ret['dataerrorcode'] = dataerrorcode
        return ret

    def handle_free_running_request(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理自由运行请求"""
        ret = {'remote_addr': addr}
        if byteorder == 'big':
            groupid, flags, cycletime, firstduration = struct.unpack(f'>HHII', command_data)
        else:
            groupid, flags, cycletime, firstduration = struct.unpack(f'<HHII', command_data)

        ret['groupid'] = groupid
        ret['flags'] = flags
        ret['cycletime'] = cycletime
        ret['firstduration'] = firstduration
        return ret

    def handle_free_running_cancel(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理取消自由运行"""
        ret = {'remote_addr': addr}
        if byteorder == 'big':
            groupid = struct.unpack(f'>H', command_data)
        else:
            groupid = struct.unpack(f'<H', command_data)

        ret['groupid'] = groupid
        return ret

    def handle_status_request(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理状态请求"""
        pass

    def handle_sequence_number_error(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理序列错误"""
        ret = {'remote_addr': addr}
        if byteorder == 'big':
            receivedSeqNr, expectedSeqNr = struct.unpack(f'>HH', command_data)
        else:
            receivedSeqNr, expectedSeqNr = struct.unpack(f'<HH', command_data)

        ret['receivedSeqNr'] = receivedSeqNr
        ret['expectedSeqNr'] = expectedSeqNr
        return ret

    def handle_function_call(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理function触发命令"""
        pass

    def handle_function_call_error(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理function触发异常"""
        pass

    def handle_increment_time(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        """处理时间命令"""
        ret = {'remote_addr': addr}
        if byteorder == 'big':
            _, timestep = struct.unpack(f'>IQ', command_data)
        else:
            _, timestep = struct.unpack(f'<IQ', command_data)

        ret['timestep'] = timestep
        return ret

    def build_fdx_header(self):
        """构建 FDX 头部"""
        self.number_of_commands = 1
        if self.UDP_Or_TCP == 'UDP':
        # if True:
            # if self.fdx_protocol_flags == 1:
            #     self.fdx_byte_order = 'big'
            # else:
            #     self.fdx_byte_order = 'little'
            header = (
                    self.fdx_signature +
                    self.fdx_major_version +
                    self.fdx_minor_version +
                    self.number_of_commands.to_bytes(2, self.fdx_byte_order) +
                    self.sequence_number.to_bytes(2, self.fdx_byte_order) +
                    self.fdx_protocol_flags.to_bytes(1, self.fdx_byte_order) +
                    self.reserved.to_bytes(1, self.fdx_byte_order)
            )
            self.sequence_number += 1
            if self.sequence_number == 0x7FFF:
                self.sequence_number = 1
        else:
            header = (
                    self.fdx_signature +
                    self.fdx_major_version +
                    self.fdx_minor_version +
                    self.number_of_commands.to_bytes(2, self.fdx_byte_order) +
                    self.dgramLen.to_bytes(2, self.fdx_byte_order) +
                    self.fdx_protocol_flags.to_bytes(1, self.fdx_byte_order) +
                    self.reserved.to_bytes(1, self.fdx_byte_order)
            )

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
        if self.UDP_Or_TCP == 'TCP':
            dataLen = len(self.fdx_data) + len(command_bytes)
            dataLen = dataLen.to_bytes(2, self.fdx_byte_order)
            self.fdx_data[12] = dataLen[0]
            self.fdx_data[13] = dataLen[1]
        number_of_commands_bytes = self.number_of_commands.to_bytes(2, self.fdx_byte_order)
        self.fdx_data[10] = number_of_commands_bytes[0]
        self.fdx_data[11] = number_of_commands_bytes[1]
        self.fdx_data = bytes(self.fdx_data)

    def _create_command(self, command_code: int, command_data: bytes = b""):
        """创建 FDX 命令"""
        command_size = 4 + len(command_data)
        command = command_size.to_bytes(2, self.fdx_byte_order) + command_code.to_bytes(2,
                                                                                        self.fdx_byte_order) + command_data
        return command

    def start_command(self, is_add_command: bool = False):
        """创建并添加开始命令"""
        command = self._create_command(self.COMMAND_CODE_START)
        if is_add_command:
            self._add_command(command)
        else:
            if self.UDP_Or_TCP == 'TCP':
                self.dgramLen = 16 + len(command)
            self.fdx_data = self.build_fdx_header() + command
        # print(f"start_command: {self.fdx_data.hex(' ').upper()}")

    def stop_command(self, is_add_command: bool = False):
        """创建并添加停止命令"""
        command = self._create_command(self.COMMAND_CODE_STOP)
        if is_add_command:
            self._add_command(command)
        else:
            if self.UDP_Or_TCP == 'TCP':
                self.dgramLen = 16 + len(command)
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
            if self.UDP_Or_TCP == 'TCP':
                self.dgramLen = 16 + len(command)
            self.fdx_data = self.build_fdx_header() + command
        # print(f"key_command: {self.fdx_data.hex(' ').upper()}")

    def data_request_command(self, group_id: int, is_add_command: bool = False):
        """创建并添加数据请求命令"""
        if not isinstance(group_id, int):
            raise TypeError("group_id must be an integer")
        group_id_bytes = group_id.to_bytes(2, self.fdx_byte_order)
        command = self._create_command(self.COMMAND_CODE_DATA_REQUEST, group_id_bytes)
        if is_add_command:
            self._add_command(command)
        else:
            if self.UDP_Or_TCP == 'TCP':
                self.dgramLen = 16 + len(command)
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
            if self.UDP_Or_TCP == 'TCP':
                self.dgramLen = 16 + len(command)
            self.fdx_data = self.build_fdx_header() + command
        # print(f"data_exchange_command: {self.fdx_data.hex(' ').upper()}")

    def free_running_request_command(self, group_id: int, flags: int, cycle_time: int, first_duration: int, is_add_command: bool = False):
        """创建并添加状态命令"""
        if not isinstance(group_id, int):
            raise TypeError("group_id must be an integer")
        if not isinstance(flags, int):
            raise TypeError("flags must be an integer")
        if not isinstance(cycle_time, int):
            raise TypeError("cycle_time must be an integer")
        if not isinstance(first_duration, int):
            raise TypeError("first_duration must be an integer")
        group_id_bytes = group_id.to_bytes(2, self.fdx_byte_order)
        flags_bytes = flags.to_bytes(2, self.fdx_byte_order)
        cycle_time_bytes = cycle_time.to_bytes(4, self.fdx_byte_order)
        first_duration_bytes = first_duration.to_bytes(4, self.fdx_byte_order)

        command = self._create_command(self.COMMAND_CODE_FREE_RUNNING_REQUEST,group_id_bytes+flags_bytes+cycle_time_bytes+first_duration_bytes)
        if is_add_command:
            self._add_command(command)
        else:
            if self.UDP_Or_TCP == 'TCP':
                self.dgramLen = 16 + len(command)
            self.fdx_data = self.build_fdx_header() + command
        # print(f"free_running_request_command: {self.fdx_data.hex(' ').upper()}")

    def free_running_cancel_command(self, group_id: int, is_add_command: bool = False):
        """创建并添加状态命令"""
        if not isinstance(group_id, int):
            raise TypeError("group_id must be an integer")

        group_id_bytes = group_id.to_bytes(2, self.fdx_byte_order)

        command = self._create_command(self.COMMAND_CODE_FREE_RUNNING_CANCEL,group_id_bytes)
        if is_add_command:
            self._add_command(command)
        else:
            if self.UDP_Or_TCP == 'TCP':
                self.dgramLen = 16 + len(command)
            self.fdx_data = self.build_fdx_header() + command
        # print(f"free_running_cancel_command: {self.fdx_data.hex(' ').upper()}")

    def status_command(self, is_add_command: bool = False):
        """创建并添加状态命令"""
        command = self._create_command(self.COMMAND_CODE_STATUS)
        if is_add_command:
            self._add_command(command)
        else:
            if self.UDP_Or_TCP == 'TCP':
                self.dgramLen = 16 + len(command)
            self.fdx_data = self.build_fdx_header() + command
        # print(f"stop_command: {self.fdx_data.hex(' ').upper()}")

    def status_request_command(self, is_add_command: bool = False):
        """创建并添加状态请求命令"""
        command = self._create_command(self.COMMAND_CODE_STATUS_REQUEST)
        if is_add_command:
            self._add_command(command)
        else:
            if self.UDP_Or_TCP == 'TCP':
                self.dgramLen = 16 + len(command)
            self.fdx_data = self.build_fdx_header() + command
        # print(f"stop_command: {self.fdx_data.hex(' ').upper()}")

    def send_fdx_data(self):
        """发送 FDX 数据"""
        if self.socket is None:
            return
        # print(f"send:{self.fdx_data.hex(' ')}")
        if not self.fdx_data:
            print("No FDX data to send.")
            return
        if self.UDP_Or_TCP == 'UDP':
            target_address = (self.target_ip, self.target_port)
            try:
                if not self.socket:
                    self.create_udp_socket()
                self.socket.sendto(self.fdx_data, target_address)
                # print(f"Sent {len(self.fdx_data)} bytes of FDX data to {target_address}")
                self.fdx_data = b''  # 发送后清空数据
            except Exception as e:
                print(f"Error sending UDP data: {e}")
        else:
            try:
                if not self.socket:
                    self.create_socket()
                self.socket.sendall(self.fdx_data)
                self.fdx_data = b''  # 发送后清空数据
            except Exception as e:
                print(f"Error sending UDP data: {e}")

    def close_socket(self):
        """关闭 UDP 套接字"""
        if self.is_running:
            self.stop_receiving()
        if self.socket:
            if self.UDP_Or_TCP == 'TCP':
                try:
                    self.socket.shutdown(socket.SHUT_RDWR)  # 先尝试优雅地关闭连接
                except OSError:
                    pass  # 如果连接已经关闭，忽略错误
            self.socket.close()
            self.socket = None
            print("UDP socket closed.")


if __name__ == '__main__':
    fdx = VectorFDX(target_port=2809)
    fdx.create_udp_socket()
    fdx.start_command()
    fdx.send_fdx_data()
    # fdx.close_socket()
