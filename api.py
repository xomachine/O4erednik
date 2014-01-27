# -*- coding: utf-8 -*-

from threading import Thread
from logging import exception
from os.path import isfile
from struct import pack, unpack
from time import sleep


class LoggableThread(Thread):

    def __init__(self):
        super(LoggableThread, self).__init__()
        self.daemon = True
        self._alive = True
        self._real_run = self.run
        self.run = self._wrap_run

    def _wrap_run(self):
        try:
            self._real_run()
        except:
            exception('Uncaught exception was occured!')


class FileTransfer():

    FT_OK = b'O'
    FT_HANDSHAKE = b'H'
    FT_SENDREQ = b'S'
    FT_SLEEP = b'W'
    FT_STOP = b'B'
    FT_ERROR = b'E'
    FT_REQFMT = 'cQ'
    FT_HSIZE = 2
    FT_SREQSIZE = 16

    def __init__(self):
        super(FileTransfer, self).__init__()

    def setsocket(self, sock):
        self._tcp = sock

    def sendfile(self, path, blocksize=2048, sbs=False, alive=lambda: True,
        sleeptime=10):
        if not isfile(path):
            self._tcp.send(pack('c?', self.FT_ERROR, sbs))
            return
        # Request for sending
        self._tcp.send(pack('c?', self.FT_HANDSHAKE, sbs))
        if self._tcp.recv(1) != self.FT_OK:
            return
        with open(path, 'rb') as f:
            # Sending cycle
            while alive():
                where = f.tell()
                buf = f.read(blocksize)
                if buf:
                    self._tcp.send(pack(self.FT_REQFMT, len(buf)))
                    answer = self._tcp.recv(1)
                    if answer != self.FT_OK:
                        return answer
                    self._tcp.send(buf)
                    answer = self._tcp.recv(1)
                    if answer != self.FT_OK:
                        return answer
                elif sbs:
                    self._tcp.send(pack(self.FT_SLEEP, sleeptime))
                    sleep(sleeptime)
                    f.seek(where)
                else:
                    break
            self._tcp.send(pack(self.FT_STOP, 0))

    def recvfile(self, path, alive=True):
        req, sbs = unpack(self.FT_REQFMT, self._tcp.recv(self.FT_HSIZE))
        if req != self.FT_SENDREQ:
            return req
        with open(path, 'wb+') as f:
            self._tcp.send(self.FT_OK)
            while alive():
                req, size = unpack(
                    self.FT_REQFMT,
                    self._tcp.recv(self.FT_REQSIZE)
                    )
                if req == self.FT_SENDREQ:
                    self._tcp.send(self.FT_OK)
                    f.write(self._tcp.recv(size))
                    self._tcp.send(self.FT_OK)
                elif req == self.FT_SLEEP:
                    sleep(size)
                elif req == self.FT_STOP:
                    return self.FT_OK
                else:
                    self._tcp.send(self.FT_ERROR)
            self._tcp.send(self.FT_STOP)