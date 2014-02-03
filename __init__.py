# -*- coding: utf-8 -*-

from core import UDPServer
from shared import Resources
from logging import warning

if __name__ == '__main__':
    # Prepare resources
    shared = Resources()
    # Try to prepare GUI
    try:
        from gui import Backend
    except ImportError:
        warning('GUI cann\'t be imported! Running without it.')
        guibackend = None
    else:
        guibackend = Backend(shared)
        shared.inform = guibackend.signal
    # Start app
    mainsrv = UDPServer(shared)
    mainsrv.start()
    if guibackend:
        guibackend.run()
    mainsrv.join()