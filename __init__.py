# -*- coding: utf-8 -*-

from core import UDPServer

if __name__ == '__main__':
    # Starting app
    mainsrv = UDPServer()
    mainsrv.start()
    #TODO: Separate GUI from UDPServer
    mainsrv.shared.backend.run()
    mainsrv.join()