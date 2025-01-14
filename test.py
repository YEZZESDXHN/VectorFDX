from VectorFDX import VectorFDX


class MyVectorFDX(VectorFDX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)



if __name__ == '__main__':
    fdx = MyVectorFDX(target_port=2809)
    fdx.create_udp_socket()
    fdx.start_command()
    fdx.send_fdx_data()
