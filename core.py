# -*- coding: utf-8 -*-

from api import LogableThread, FileTransfer
from json import loads, dumps
from logging import debug, error
from os import kill
from socket import socket


class Job():

    def __init__(self, jtype='dummy', uid=0, params=None):
        super(Job, self).__init__()
        self.id = uid
        self.type = jtype
        self.params = params


class Processor(LogableThread):

    def __init__(self, shared):
        super(Processor, self).__init__()
        self.name = 'Processor'
        self.cur = None
        # Binding shared objects
        self.queue = shared.queue
        self.inform = shared.backend.signal
        # Fill workers
        self.fill_workers()

    def fill_workers(self):
        self.workers = {
            'g03': self.g03
            }

    def run(self):
        while self._alive:
            self.cur = self.queue.get()
            if self.cur.type in self.workers:
                self.workers[self.cur.type]()
            self.cur = None

# Workers

    # Gaussian 03 worker
    def g03(self):
        pass


class RemoteReporter(LogableThread, FileTransfer):

    def __init__(self, processor, shared, peer):
        super(RemoteReporter, self).__init__()
        self.name = 'reporter-' + peer
        # Binding shared objects
        host = shared.settings['host']
        self.cur = Job()
        self.inform = shared.backend.signal
        self.queue = shared.queue
        self.checker = lambda: True if self.queue.is_contain(
            self.cur) else False
        self.pooler = lambda: True if self.cur is processor.cur else False
        # Socket creation
        self.tcp = socket()
        self.tcp.settimeout(10)
        self.tcp.bind((host, 50000))
        self.tcp.listen(1)
        self.setsocket(self.tcp)  # Setting socket for file transfer

    def run(self):
        pass

    def check(self):
        return self.checker() or self.pooler()


class RemoteReceiver(LogableThread, FileTransfer):

    def __init__(self, shared, peer):
        super(RemoteReceiver, self).__init__()
        self.name = 'receiver-' + peer
        # Binding shared objects
        self.queue = shared.queue
        self.inform = shared.backend.signal
        # Socket creation
        self.tcp = socket()
        self.tcp.settimeout(10)
        try:
            self.tcp.connect((peer, 50000))
        except:
            error('Unable to connect remote worker' + peer)
            self._alive = False
            return
        self.setsocket(self.tcp)
        self.job = self.queue.get()
        self.inform('shared', self.job)

    def run(self):
        if self._alive is False:
            return
        pass


class UDPServer(LogableThread):

    def __init__(self, shared):
        super(UDPServer, self).__init__()
        self.name = 'UDPServer'
        # Binding shared objects
        self.shared = shared
        self.queue = shared.queue
        self.udp = shared.udpsocket
        # Creating queue processor
        self.processor = Processor(self.shared)
        # Fill message-action dictonary
        self.fill_actions()

    def fill_actions(self):
        self.actions = {
            'F': self.mFree,  # To be continued...
            'A': self.mAdd,
            'L': self.mLFF,
            }

    def run(self):
        while self._alive:
            data, peer = self.udp.recvfrom(1024)
            debug(data)
            mtype, params = loads(data.decode('utf-8'))
            if mtype in self.actions:
                self.actions[mtype](params, peer)

# Actions

    # Local addition to queue
    def mAdd(self, params, peer):
        job = Job(*params)
        self.queue.put(job)
        kill(job.id, 19)

    # Possibility to share work
    def mFree(self, params, peer):
        if self.queue.fill.isSet() and not self.processor.cur is None:
            self.sendto(
                dumps(['S', None]),
                (peer, 50000)
                )
            RemoteReceiver(self.shared, peer).start()

    # Search for possibility to share work
    def mLFF(self, params, peer):
        if self.processor.cur is None and not self.queue.fill.isSet():
            self.udp.sendto(
                dumps(['F', None]).encode('utf-8'),
                (peer, 50000)
                )
