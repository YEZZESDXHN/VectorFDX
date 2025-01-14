import sys

from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtWidgets import QMainWindow, QApplication

from VectorFDX import VectorFDX
from VectoeFDX_UI import Ui_MainWindow


class QtVectorFDX(VectorFDX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def handle_status_command(self, command_data, addr):
        print('my handle_status_command')




class MainWindows(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.local_ip='127.0.0.1'
        self.local_port: int = 2000
        self.target_ip='127.0.0.1'
        self.target_port: int = 2001

        self.fdx = QtVectorFDX(fdx_byte_order='big',local_ip=self.local_ip,local_port=self.local_port,
                               target_ip=self.target_ip,target_port=self.target_port)

        self.connect_signals()
    def connect_signals(self):
        self.pushButton_StartCANoe.clicked.connect(self.start_canoe_command)
        self.pushButton_StopCANoe.clicked.connect(self.stop_canoe_command)
        self.pushButton_fdxConnect.clicked.connect(self.operate_fdx_connection)
        self.pushButton_StatusRequest.clicked.connect(self.status_request_command)

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
        elif self.pushButton_fdxConnect.text() == 'Connected':
            self.disconnect_fdx()


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
