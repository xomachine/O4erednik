# -*- coding: utf-8 -*-

from api import LogableThread, FileTransfer
from json import loads, dumps
from logging import debug, error
from os import kill, killpg, getpgid
from os.path import isfile, isdir, dirname
from socket import socket, SOL_SOCKET, SO_REUSEADDR, timeout
from subprocess import Popen
from time import sleep
from shared import Resources


class Job():

    def __init__(self, jtype='dummy', uid=0, files=dict(), params=dict()):
        super(Job, self).__init__()
        self.id = uid
        self.type = jtype
        self.files = files
        self.params = params


class Processor(LogableThread):

    def __init__(self, shared):
        super(Processor, self).__init__()
        self.name = 'Processor'
        self.cur = None
        # Binding shared objects
        self.queue = shared.queue
        self.inform = shared.backend.signal
        self.udp = shared.udpsocket
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
                # Send Free signal when queue is empty
                self.udp.sendto(
                    dumps(['F', None]).encode('utf-8'),
                    ('', 50000)
                    )
                self.inform('empty')
            self.cur = self.queue.get()
            if self.queue.fill.isSet():  # Look For Free if queue still fill
                self.udp.sendto(
                    dumps(['L', None]).encode('utf-8'),
                    ('', 50000)
                    )
            if self.cur.type in self.workers:
                self.inform('start', self.cur.id)
                self.workers[self.cur.type]()
                self.inform('done', self.cur.id)
                if self.job.id > 0:
                    try:
                        kill(self.job.id, 9)
                    except:
                        pass
            self.cur = None

# Workers

    # Gaussian 03 worker
    def g03(self):
        ifile = self.cur.files['ifile']
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
            shell=True
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
        self.queue = shared.queue
        # Current running job, not nessesary self.cur
        self.curproc = processor.cur
        self.pgid = processor.pgid
        # Socket creation
        tcp = socket()
        tcp.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        tcp.settimeout(10)  # OPTIMIZE: Find optimal timeout
        tcp.bind((host, 50000))
        tcp.listen(1)
        self.tcp, addr = tcp.accept()
        self.setsocket(self.tcp)  # Setting socket for file transfer
        tcp.close()

    def stop(self):
        self.tcp.close()
        if self.cur is self.curproc:
            killpg(self.pgid, 9)
        elif self.queue.is_contain(self.cur):
            self.queue.remove(self.cur)

    def run(self):
        # Receiving job class as it is
        try:
            sjob = loads(self.tcp.recv(4096).decode('utf-8'))
        except timeout:
            pass
        self.cur = Job(*sjob)
        # Receiving nessesary files
        for jfile in self.cur.files.values():
            self.tcp.send(dumps(['G', jfile]).encode('utf-8'))
            self.recvfile(jfile)
        # Putting job to queue
        self.queue.put(self.cur)
        # While job still in queue receiver must wait
        while self.queue.is_contain(self.cur):
            self.tcp.send(dumps(['W', 10]).encode('utf-8'))
            try:
                self.tcp.recv(1)
            except:
                self.stop()
                return
            else:
                sleep(10)  # OPTIMIZE: Find optimal sleep interval
        # Job leaved queue, lets search it in processor
        # If output file has defined, stream it while job is in process
        #FIXME lambdas behaviour is undefined here
        if 'ofile' in self.cur.files:
            if self.cur is self.curproc:
                self.sendfile(
                    self.cur.files['ofile'],
                    sbs=True,
                    alive=lambda: True if self.cur is self.curproc else False
                    )
        # Else just wait until job will be done
        else:
            while self.cur is self.curproc:
                self.tcp.send(dumps(['W', 10]).encode('utf-8'))
                try:
                    self.tcp.recv(1)
                except:
                    self.stop()
                    return
                else:
                    sleep(10)  # OPTIMIZE: Find optimal sleep interval
        # After job completion sending results back
        for jfile in self.cur.files.values():
            self.tcp.send(dumps(['T', jfile]).encode('utf-8'))
            self.sendfile(jfile)
        # Closing connection
        self.tcp.send(dumps(['D', jfile]).encode('utf-8'))
        self.tcp.close()


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
        self.inform('shared', (self.job.id, self.peer))

    def run(self):
        if self._alive is False:
            return
        # Sending job object as it is
        jpack = dumps([
            self.job.type,
            0,  # Id of remote job must be 0 to avoid spontanous process kills
            self.job.files,
            self.job.params
            ])
        self.tcp.send(jpack.encode('utf-8'))
        # Waiting for response from remote host
        while self._alive:
            try:
                req, param = loads(self.tcp.recv(1024).decode('utf-8'))
            except timeout:
                req = 'E'
            if req == 'G':  # Get file
                self.sendfile(param)
            elif req == 'T':  # Transfer file
                self.recvfile(param)
            elif req == 'W':  # Wait some seconds and req again
                self.tcp.send(b'O')
                sleep(param)
            elif req == 'S':  # Start streaming
                self.recvfile(param, self._alive)
            elif req == 'D':  # All Done, job completed
                if self.job.id > 0:
                    try:
                        kill(self.job.id, 9)
                    except:
                        pass
                self.inform('done', self.job.id)
                self.stop()
            else:
                self.stop()
                self.queue.put(self.job)
                self.inform('error', self.job.id)
                if req != 'E':  # Unexpected response
                    error('Unexpected response:' + req)
        if self._alive is False:  # Sharing process end
            self.tcp.close()

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
        self.processor.start()
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
        if self.processor.cur:  # Look For Free if processor is already busy
            self.udp.sendto(
                dumps(['L', None]).encode('utf-8'),
                ('', 50000)
                )
        self.queue.put(job)
        kill(job.id, 19)
        self.inform('add', job)

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
        if self.queue.fill.isSet():  # Look For Free if queue still fill
            self.udp.sendto(
                dumps(['L', None]).encode('utf-8'),
                ('', 50000)
                )
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
        RemoteReporter(self.shared, peer).start()
