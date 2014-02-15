# -*- coding: utf-8 -*-
'''
    This file is part of O4erednik.

    O4erednik is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License or
    (at your option) any later version.

    Foobar is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Foobar.  If not, see <http://www.gnu.org/licenses/>.

    Copyright 2014 Fomichev Dmitriy
'''


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