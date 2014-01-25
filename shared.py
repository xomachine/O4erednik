# -*- coding: utf-8 -*-

from threading import Lock, Event
from socket import socket, AF_INET, SOCK_DGRAM, IPPROTO_UDP, gethostname
from socket import SOL_SOCKET, SO_REUSEADDR
from json import dump, load
from os.path import realpath, isfile, dirname
try:
    from gui import Backend
except ImportError:
    class GUIBackend():

        def __init__(self, udp):
            super(GUIBackend, self).__init__()
            self.sendto = udp.sendto

        def signal(self, signal):
            if signal[0] == 'empty':
                self.sendto(b'[\"F\"]', ('<broadcast>', 50000))

else:
    class GUIBackend(Backend):

        def __init__(self, udp):
            super(GUIBackend, self).__init__()
            self.sendto = udp.sendto


class Queue():

    def __init__(self, inform):
        super(Queue, self).__init__()
        self._queue = []
        self._lock = Lock()
        self.fill = Event()
        self.size = 0
        self.inform = inform  # Function to send signals for GUI

    def put(self, obj):
        with self._lock:
            self._queue.append(obj)
            self.fill.set()
            self.size += 1
        self.inform(['put', obj])

    def get(self, block=True):
        if not self.fill.isSet():
            self.inform(['empty'])
            if block:
                self.fill.wait()
            else:
                return None
        with self._lock:
            obj = self._queue.popleft()
            self.size -= 1
            if self.size == 0:
                self.fill.clear()
        self.inform(['get', obj])
        return obj


class Resources():

    def __init__(self):
        super(Resources, self).__init__()
        # Programm position
        self.path = dirname(realpath(__file__))
        # Settings
        self.settings = dict()
        self.default()
        self.load()
        self.save()  # Just renew/create config
        # Socket
        self.udpsocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        self.udpsocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.udpsocket.bind((self.settings['host'], 50000))
        # GUIBackend
        self.backend = GUIBackend(self.udpsocket)
        # Queue
        self.queue = Queue(self.backend.signal)
        # If programm was frozen...
        self.unfreeze()

    def default(self):
        self.settings['host'] = gethostname()
        # To be continued...

    def save(self):
        with open(self.path + '/config.jsn', 'w') as f:
            dump(self.settings, f, indent=0)

    def load(self):
        if not isfile(self.path + '/config.jsn'):
            return
        with open(self.path + '/config.jsn', 'r') as f:
            self.settings.update(load(f))

# Used to freeze shared resources before restart programm
    def freeze(self):
        pass  # TODO: Hot restart

# Used to unfreeze shared resources after programm restarted
    def unfreeze(self):
        if not isfile(self.path + '/frozen.data'):
            return