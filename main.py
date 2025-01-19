import json
import struct
import sys
from typing import Literal

import serial.tools.list_ports

from PyQt5.QtCore import QCoreApplication, Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import QMainWindow, QApplication

from VectorFDX import VectorFDX
from ModbusClient import SerialModbusRTUClient
from VectoeFDX_UI import Ui_MainWindow


class QVectorFDX(VectorFDX, QObject):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def handle_status_command(self, command_data: bytes, addr: str, byteorder: Literal["little", "big"]):
        parent_result = super().handle_status_command(command_data, addr, byteorder)
        # print(parent_result)

class QSerialModbusRTUClient(SerialModbusRTUClient, QObject):
    read_holding_registers_response_data = pyqtSignal(dict)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handler_read_holding_registers_response(self, slave, response):
        try:
            self.read_holding_registers_response_data.emit({'slave':slave,'data': response.registers})
        except Exception as e:
            print(f'read_holding_registers_response_data emit error:{e}')



def list_to_bytes_struct_direct(input_list,byte_oder):
    output_bytes = b""
    for item in input_list:
        if isinstance(item, int):
            if item > 0xFFFF:
                raise ValueError("Integer value too large to represent as 2 bytes")
            if byte_oder == 'big':
                output_bytes += struct.pack(">H", item) # 大端字节序
            else:
                output_bytes += struct.pack("<H", item)  # 小端字节序
        else:
            raise ValueError("List item must be an integer")
    return output_bytes

class MainWindows(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.local_ip='127.0.0.1'
        self.local_port: int = 2000
        self.target_ip='127.0.0.1'
        self.target_port: int = 2001

        self.fdx = QVectorFDX(fdx_byte_order='big',local_ip=self.local_ip,local_port=self.local_port,
                                target_ip=self.target_ip,target_port=self.target_port)

        self.slaves_lists = {}
        self.cycle_read_slaves_list = []
        self.serial_baud_rate = 115200
        self.serial_bytesize = 8
        self.serial_parity = "N"
        self.serial_stop_bits = 1
        self.serial_timeout = 1
        self.serial_retries = 0
        self.port = 'com6'
        self.ports_list=[]
        self._load_modbus_config('config.json')
        self.get_available_ports()
        try:
            self.port = self.ports_list[0]
        except:
            pass
        self.modbus_client = QSerialModbusRTUClient(port=self.port,
                                                    serial_baud_rate=self.serial_baud_rate,
                                                    serial_bytesize=self.serial_bytesize,
                                                    serial_parity=self.serial_parity,
                                                    serial_stop_bits=self.serial_stop_bits,
                                                    serial_timeout=self.serial_timeout,
                                                    serial_retries=self.serial_retries)

        self.modbus_client.slaves_list=self.slaves_lists
        self.modbus_client.cycle_read_slaves_list=self.cycle_read_slaves_list

        self.connect_ui_signals()
        self.connect_modbus_client_signals()
        self.ui_setdisabled(True)

    def _load_modbus_config(self, config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                lists = config.get("slaves_list", {})
                self.slaves_lists = {int(k): v for k, v in lists.items()}
                self.cycle_read_slaves_list = config.get("cycle_read_slaves_list", [])
                self.serial_baud_rate = config.get("serial_baud_rate", self.serial_baud_rate)
                self.serial_bytesize = config.get("serial_bytesize", self.serial_bytesize)
                self.serial_parity = config.get("serial_parity", self.serial_parity)
                self.serial_stop_bits = config.get("serial_stop_bits", self.serial_stop_bits)
                self.serial_timeout = config.get("serial_timeout", self.serial_timeout)
                self.serial_retries = config.get("serial_retries", self.serial_retries)
        except FileNotFoundError:
            print(f"Error: Config file '{config_file}' not found. Using default values.")
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in '{config_file}'. Using default values.")

    def get_available_ports(self):
        self.ports_list = [port.device for port in serial.tools.list_ports.comports()]
        self.comboBox_serialPorts.clear()
        for port in self.ports_list:
            self.comboBox_serialPorts.addItem(port)

    def ui_setdisabled(self, Disabled: bool):
        self.pushButton_StartCANoe.setDisabled(Disabled)
        self.pushButton_StopCANoe.setDisabled(Disabled)
        self.pushButton_StatusRequest.setDisabled(Disabled)
        self.comboBox_serialPorts.currentIndexChanged.connect(self.on_port_selected)

    def on_port_selected(self,index):
        self.modbus_client.port=self.ports_list[index]

    def connect_ui_signals(self):
        self.pushButton_StartCANoe.clicked.connect(self.start_canoe_command)
        self.pushButton_StopCANoe.clicked.connect(self.stop_canoe_command)
        self.pushButton_fdxConnect.clicked.connect(self.operate_fdx_connection)
        self.pushButton_StatusRequest.clicked.connect(self.status_request_command)
        self.pushButton_connectmodbus.clicked.connect(self.operate_modbus_connection)
        self.checkBox_isCycleReadModbus.clicked.connect(self.start_stop_read_modbus_cycle)
        self.pushButton_WriteRegister.clicked.connect(self.write_modbus_register)

    def write_modbus_register(self):
        slave=int(self.lineEdit_WriteSlave.text())
        address=int(self.lineEdit_WriteRegisterAddress.text())
        value=int(self.lineEdit_WriteRegisterValue.text())
        self.modbus_client.add_write_register_queue(address=address,value=value,slave=slave)

    def start_stop_read_modbus_cycle(self,checked):
        if checked:
            self.modbus_client.start_cycle_read__loop()
        else:
            self.modbus_client.stop_cycle_read__loop()
    def operate_modbus_connection(self):
        if self.pushButton_connectmodbus.text() == 'Connect':
            self.creat_modbus_client()
        else:
            self.close_modbus_client()
    def creat_modbus_client(self):
        """连接/断开 Modbus 客户端并开始/停止读取"""
        if self.modbus_client.modbus_client == None:
            if self.modbus_client.create_modbus_rtu_service():
                self.pushButton_connectmodbus.setText("Connected")
            else:
                self.modbus_client.stop_cycle_read__loop()
                self.pushButton_connectmodbus.setText("Connect")

    def close_modbus_client(self):
        if self.modbus_client.modbus_client is not None and self.modbus_client.is_connected:
            self.modbus_client.stop_cycle_read__loop()
            self.modbus_client.modbus_rtu_service_close()
            self.pushButton_connectmodbus.setText("Connect")

    def connect_modbus_client_signals(self):
        self.modbus_client.read_holding_registers_response_data.connect(self.modbus_registers_to_fdx)

    def modbus_registers_to_fdx(self, data):
        self.fdx.data_exchange_command(data['slave'], list_to_bytes_struct_direct(data['data'], 'big'))
        self.fdx.send_fdx_data()


    def start_canoe_command(self):
        self.fdx.start_command()
        self.fdx.send_fdx_data()

    def stop_canoe_command(self):
        self.fdx.stop_command()
        self.fdx.send_fdx_data()

    def status_request_command(self):
        self.fdx.status_request_command()
        self.fdx.send_fdx_data()


    def operate_fdx_connection(self):
        if self.pushButton_fdxConnect.text() == 'Connect':
            self.connect_fdx()
            self.ui_setdisabled(False)
        elif self.pushButton_fdxConnect.text() == 'Connected':
            self.disconnect_fdx()
            self.ui_setdisabled(True)


    def connect_fdx(self):
        self.local_ip = self.lineEdit_localip.text()
        self.local_port = int(self.lineEdit_localport.text())
        self.target_ip = self.lineEdit_targetip.text()
        self.target_port = int(self.lineEdit_targetport.text())

        self.fdx.local_ip = self.local_ip
        self.fdx.local_port = self.local_port
        self.fdx.target_ip = self.target_ip
        self.fdx.target_port = self.target_port

        self.fdx.start_receiving()

        self.lineEdit_localip.setDisabled(True)
        self.lineEdit_localport.setDisabled(True)
        self.lineEdit_targetip.setDisabled(True)
        self.lineEdit_targetport.setDisabled(True)

        self.pushButton_fdxConnect.setText('Connected')

    def disconnect_fdx(self):
        self.fdx.stop_receiving()
        self.fdx.close_socket()

        self.lineEdit_localip.setDisabled(False)
        self.lineEdit_localport.setDisabled(False)
        self.lineEdit_targetip.setDisabled(False)
        self.lineEdit_targetport.setDisabled(False)

        self.pushButton_fdxConnect.setText('Connect')







if __name__ == "__main__":
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    app.setStyle("WindowsVista")
    w = MainWindows()
    current_version = "v1.0.0"
    w.setWindowTitle("CAN tool " + current_version)

    w.show()
    sys.exit(app.exec_())
