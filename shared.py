# -*- coding: utf-8 -*-
'''
    This file is part of O4erednik.

    O4erednik is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License or
    (at your option) any later version.

    O4erednik is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with O4erednik.  If not, see <http://www.gnu.org/licenses/>.

    Copyright 2014 Fomichev Dmitriy
'''


from threading import Lock, Event
from socket import socket, AF_INET, SOCK_DGRAM, IPPROTO_UDP
from socket import SOL_SOCKET, SO_REUSEADDR, SO_BROADCAST, inet_ntoa
from json import dump, load
from os.path import realpath, isfile, dirname
from os import remove, makedirs, listdir, sep, curdir, name as osname
from logging import basicConfig, debug, warning, DEBUG as LEVEL
from struct import pack
from core import Job
if osname == 'posix':
    from fcntl import ioctl
    from os import sysconf
    from socket import if_nameindex


class Queue(list):

    def __init__(self):
        super(Queue, self).__init__()
        self._lock = Lock()
        self._fill = Event()

    def put(self, obj):
        with self._lock:
            self.append(obj)
            self._fill.set()

    def get(self, block=True):
        with self._lock:
            if len(self) == 0:
                self._fill.clear()
        if not self._fill.isSet():
            if block:
                self._fill.wait()
            else:
                return None
        with self._lock:
            return self.pop(0)

    def delete(self, index):
        if 0 <= index < len(self):
            with self._lock:
                del self[index]

    def remove(self, element):
        if element in self:
            with self._lock:
                del self[self.index(element)]


class Resources():


    

    def __init__(self):
        super(Resources, self).__init__()
        # Programm position
        self.path = dirname(realpath(__file__))
        # Logging
        basicConfig(
            filename=self.path + sep + 'queuer.log',
            level=LEVEL,
            format='[%(asctime)s] %(threadName)s: %(levelname)s, %(message)s',
            datefmt='%d.%m.%y %H:%M:%S'
            )
        # Settings init
        self.settings = dict()
        self.default()
        # Settings load
        self.load()
        self.settings['Main']
        if osname == 'posix':
            self.bcastaddr = lambda x: inet_ntoa(
                ioctl(
                    socket(AF_INET, SOCK_DGRAM), 0x8919, pack(  # SIOCGIFBRDADDR
                        '256s', ''.join(x).encode('utf-8'))
                    )[20:24]
                )
        elif osname == 'nt':
            self.bcastaddr = lambda x: "<broadcast>"
        # Environment
        makedirs(self.settings['Main']['Temporary directory'], exist_ok=True)
        # Socket
        self.udpsocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        self.udpsocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.udpsocket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        self.udpsocket.bind(('0.0.0.0', 50000))
        # Modules init
        self.modules = dict()
        self.loadmodules()
        # Queue
        self.queue = Queue()

        # If programm was frozen...
        self.unfreeze()
        self.save()  # Just renew/create config

    def loadmodules(self):
        for mname in listdir(dirname(__file__) + sep + 'modules'):
            if mname == '__init__.py' or mname[-3:] != '.py':
                continue
            try:
                module = __import__('modules.' + mname[:-3], locals(),
                    globals(), ['Module']).Module(self.settings)
                self.modules[mname[:-3]] = module
            except ImportError:
                warning("Errors occured while loading " + mname)

    def default(self):
        if not 'Main' in self.settings:
            self.settings['Main'] = dict()
        ms = self.settings['Main']
        ms['Text editor executable file'] = ''
        ms['Number of processors'] = 1
        ms['Interface'] = 'Does not matter'
        ms['Temporary directory'] = curdir + sep + 'tmp'
        ms['Client mode'] = True
        if osname == 'posix':
            ms[tuple('Interface')] = list(zip(*if_nameindex()))[1]
            ms['Interface'] = ['lo']
            ms['Number of processors'] = sysconf('SC_NPROCESSORS_ONLN')
            ms['Client mode'] = False
        # To be continued...

    def save(self):
        with open(self.path + sep + 'queuer.conf', 'w') as f:
            dump(self.settings, f, indent=4, skipkeys=True)

    def load(self):
        if not isfile(self.path + sep + 'queuer.conf'):
            return
        with open(self.path + sep + 'queuer.conf', 'r') as f:
            loaded = load(f)
            for key, value in loaded.items():
                if key in self.settings:
                    self.settings[key].update(value)
                else:
                    self.settings[key] = value

# Used to freeze shared resources before restart programm
    def freeze(self, processor):
        cur = processor.getcur()
        if (cur is None) and (len(self.queue)==0):
            return
        dmp = dict()
        dmp['queue'] = list()
        if cur:
            if not (cur.type == 'lock'):
                cur.type = 'waitfor'
            cur.params['pid'] = processor.getpid()
            dmp['queue'].append({'uid': cur.id, 'files': cur.files, 'params': cur.params, 'jtype': 'waitfor'})
        for j in self.queue:
            dmp['queue'].append({'uid': j.id, 'files': j.files, 'params': j.params, 'jtype': j.type})
        with open(self.path + sep + 'frozen.dat', 'w') as f:
            dump(dmp, f, indent=4, skipkeys=True)

# Used to unfreeze shared resources after programm restarted
    def unfreeze(self):
        if isfile(self.path + sep + 'frozen.dat'):
            debug("unfreezing...")
            with open(self.path + sep + 'frozen.dat', 'r') as f:
                dmp = load(f)
            for j in dmp['queue']:
                debug("Added to queue ", j)
                self.queue.put(Job(*j))
            
    def clearfrozen(self):
        if isfile(self.path + sep + 'frozen.dat'):
            remove(self.path + sep + 'frozen.dat')

# Stub informer, will be replaced by gui informer
    def inform(self, *signal):
        return
