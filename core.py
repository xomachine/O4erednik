# -*- coding: utf-8 -*-

from api import LogableThread, FileTransfer
from json import loads, dumps
from logging import debug, error
from os import kill, killpg, getpgid
from os.path import isfile, isdir, dirname
from socket import socket, SOL_SOCKET, SO_REUSEADDR
from subprocess import Popen, CREATE_NEW_PROCESS_GROUP
from time import sleep
from shared import Resources


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
        self.nproc = shared.settings['nproc']
        self.g03exe = shared.settings['g03exe']
        # Fill workers
        self.fill_workers()

    def fill_workers(self):
        self.workers = {
            'g03': self.g03
            }

    def run(self):
        while self._alive:
            if not self.queue.fill.isSet():
                self.inform('empty')
            self.cur = self.queue.get()
            if self.cur.type in self.workers:
                self.inform('start', self.cur.params['ifile'])
                self.workers[self.cur.type]()
                self.inform('done', self.cur.params['ifile'])
            self.cur = None

# Workers

    # Gaussian 03 worker
    def g03(self):
        ifile = self.cur.params['ifile']
        if not isfile(ifile):
            return
        # Preparation
        wlines = ["%nprocshared=" + str(self.nproc) + "\n"]
        # Set number of processors by default
        with open(ifile, 'r') as f:
            lines = f.readlines()
            for buf in lines:
                if buf.startswith('%lindaworkers'):
                    buf = "%lindaworkers=\n"
                    #TODO: linda support
                elif buf.startswith('%nprocshared'):
                    buf = '%nprocshared=' + str(self.nproc) + "\n"
                    # Overwrite number of processors and remove default
                    # as annessesery
                    wlines[0] = ""
                elif buf.startswith('%chk'):
                    # If dir to chk file not exist or %chk refers to directory,
                    # save chk to same place as input
                    if isdir(buf[5:-1]) or not isdir(dirname(buf[5:-1])):
                        buf = "%chk=" + ifile[:-3] + "chk\n"
                wlines.append(buf)
        with open(ifile, 'w') as f:
            for buf in wlines:
                f.write(buf)
        # Execution
        proc = Popen(
            [self.g03exe, ifile],
            cwd=dirname(ifile),
            creationflags=CREATE_NEW_PROCESS_GROUP
            )
        self.pgid = getpgid(proc.pid)
        proc.wait()


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
        tcp = socket()
        tcp.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        tcp.settimeout(10)  # OPTIMIZE: Find optimal timeout
        tcp.bind((host, 50000))
        tcp.listen(1)
        self.tcp, addr = tcp.accept()
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
        self.tcp.settimeout(10)  # OPTIMIZE: Find optimal timeout
        sleep(1)  # OPTIMIZE: Find optimal sleep before connection
        try:
            self.tcp.connect((peer, 50000))
        except:
            error('Unable to connect remote worker' + peer)
            self.stop()
            return
        self.setsocket(self.tcp)
        self.job = self.queue.get()
        self.inform('shared', (self.job.params['ifile'], self.peer))

    def run(self):
        if self._alive is False:
            return

    def stop(self):
        self._alive = False


class UDPServer(LogableThread):

    def __init__(self):
        super(UDPServer, self).__init__()
        self.name = 'UDPServer'
        # Binding shared objects
        self.shared = Resources()
        self.queue = self.shared.queue
        self.udp = self.shared.udpsocket
        self.inform = self.shared.backend.signal
        # Creating queue processor
        self.processor = Processor(self.shared)
        # Creating list of receivers
        self.receivers = dict()
        # Fill message-action dictonary
        self.fill_actions()

    def fill_actions(self):
        self.actions = {
            'F': self.mFree,  # To be continued...
            'A': self.mAdd,
            'L': self.mLFF,
            'K': self.mKill,
            'S': self.mShare,
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
        self.inform('add', job.params['ifile'])

    # Possibility to share work
    def mFree(self, params, peer):
        if (
            self.processor.cur is None or
            peer in self.receivers or
            not self.queue.fill.isSet()
            ):
            return
        self.sendto(
            dumps(['S', None]),
            (peer, 50000)
            )
        self.receivers[peer] = RemoteReceiver(self.shared, peer)
        self.receivers[peer].start()

    # Search for possibility to share work
    def mLFF(self, params, peer):
        if self.processor.cur is None and not self.queue.fill.isSet():
            self.udp.sendto(
                dumps(['F', None]).encode('utf-8'),
                (peer, 50000)
                )

    def mKill(self, params, peer):
        if params == 'current':
            killpg(self.processor.pgid, 9)  # Kill current task with SIGKILL
        elif params is int:
            self.queue.remove(params)
        elif params in self.receivers:
            self.receivers[params].stop()

    def mShare(self, params, peer):
        RemoteReporter(self.shared, peer)
