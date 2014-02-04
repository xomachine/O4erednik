# -*- coding: utf-8 -*-

from threading import Lock, Event
from socket import socket, AF_INET, SOCK_DGRAM, IPPROTO_UDP
from socket import SOL_SOCKET, SO_REUSEADDR, SO_BROADCAST
from json import dump, load
from os.path import realpath, isfile, dirname
from os import sysconf, makedirs, listdir
from logging import basicConfig, DEBUG


class Queue():

    def __init__(self):
        super(Queue, self).__init__()
        self._queue = []
        self._lock = Lock()
        self.fill = Event()
        self.size = 0

    def put(self, obj):
        with self._lock:
            self._queue.append(obj)
            self.fill.set()
            self.size += 1

    def get(self, block=True):
        if not self.fill.isSet():
            if block:
                self.fill.wait()
            else:
                return None
        with self._lock:
            obj = self._queue.pop(0)
            self.size -= 1
            if self.size == 0:
                self.fill.clear()
        return obj

    def is_contain(self, obj):
        return True if obj in self._queue else False

    def remove(self, index):
        if index + 1 > self.size:
            return
        else:
            self._queue.pop(index)


class Resources():

    def __init__(self):
        super(Resources, self).__init__()
        # Programm position
        self.path = dirname(realpath(__file__))
        # Logging
        basicConfig(
            filename=self.path + '/queuer.log',
            level=DEBUG,
            format='[%(asctime)s] %(threadName)s: %(levelname)s, %(message)s',
            datefmt='%d.%m.%y %H:%M:%S'
            )
        # Settings
        self.settings = dict()
        self.default()
        self.load()
        self.mainset = self.settings['Main']
        # Environment
        makedirs(self.mainset['tmp'], exist_ok=True)
        # Socket
        self.udpsocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        self.udpsocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.udpsocket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        self.udpsocket.bind(('0.0.0.0', 50000))
        # Queue
        self.queue = Queue()
        # Modules
        self.modules = dict()
        self.loadmodules()
        # If programm was frozen...
        self.unfreeze()
        self.save()  # Just renew/create config

    def loadmodules(self):
        for mname in listdir(dirname(__file__) + '/modules'):
            if mname == '__init__.py' or mname[-3:] != '.py':
                continue
            module = __import__(
                'modules.' + mname[:-3], locals(), globals(), ['Module'])
            self.modules[mname[:-3]] = module.Module(self.settings)

    def default(self):
        if not 'Main' in self.settings:
            self.settings['Main'] = dict()
        ms = self.settings['Main']
        ms['nproc'] = sysconf('SC_NPROCESSORS_ONLN')
        ms['tmp'] = '/tmp/queuer'
        # To be continued...

    def save(self):
        with open(self.path + '/queuer.conf', 'w') as f:
            dump(self.settings, f, indent=4)

    def load(self):
        if not isfile(self.path + '/queuer.conf'):
            return
        with open(self.path + '/queuer.conf', 'r') as f:
            self.settings = load(f)

# Used to freeze shared resources before restart programm
    def freeze(self):
        pass  # TODO: Hot restart

# Used to unfreeze shared resources after programm restarted
    def unfreeze(self):
        if not isfile(self.path + '/frozen.dat'):
            return

# Stub informer, will be replaced by gui informer
    def inform(self, *signal):
        return
