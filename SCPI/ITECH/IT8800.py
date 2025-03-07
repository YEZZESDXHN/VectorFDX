from enum import Enum

import pyvisa


class Function(Enum):
    CURRENT = "CURRent"
    RESISTANCE = "RESistance"
    VOLTAGE = "VOLTage"
    POWER = "POWer"


class IT8800:
    def __init__(self, pyvisa_instrument):
        self.pyvisa_instrument = pyvisa_instrument


        self.SYSTem = IT8800.SYSTem(self)
        self.Common = IT8800.Common(self)
        self.SOURce = IT8800.SOURce(self)
        self.MEASure = IT8800.MEASure(self)

    def write(self, command):
        self.pyvisa_instrument.write(command)

    def read(self):
        return self.pyvisa_instrument.read()


    class Common:
        def __init__(self, outer):
            self.outer = outer  # 存储外部类的引用

        def identification_query(self):
            self.outer.write("*IDN?")
            response = self.outer.read()
            return response

    class MEASure:
        def __init__(self, outer):
            self.outer = outer  # 存储外部类的引用

        def read_voltage(self):
            # self.outer.write(f"MEASure:VOLTage:DC?")
            self.outer.write(f"MEAS:VOLT?")
            response = self.outer.read()
            return int(response)

    class SOURce:
        def __init__(self, outer):
            self.outer = outer  # 存储外部类的引用

        def set_function(self, mode: Function):
            self.outer.write(f"SOURce:FUNCtion {mode.value}")
            # response = self.outer.read()
            # return response


    class SYSTem:
        def __init__(self, outer):
            self.outer = outer  # 存储外部类的引用

        def remote(self):
            self.outer.write("SYSTem:REMote")

        def rwlock(self):
            self.outer.write("SYSTem:RWLock")

        def local(self):
            self.outer.write("SYSTem:LOCal")



if __name__ == '__main__':
    rm = pyvisa.ResourceManager('@py')
    # resources = rm.list_resources()
    # print(resources)
    # 替换为你的串口资源名称
    instrument = rm.open_resource("ASRL3::INSTR", baud_rate=115200, data_bits=8, parity=pyvisa.constants.Parity.none,
                                  stop_bits=pyvisa.constants.StopBits.one)

    # 设置超时时间 (可选)
    instrument.timeout = 5000  # 5 秒

    IT8813 = IT8800(instrument)
    print(IT8813.Common.identification_query())