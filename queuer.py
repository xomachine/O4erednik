#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Imports
from threading import Thread, Event, Lock
from os import kill
from socket import socket, gethostbyname, gethostname
from socket import SHUT_RDWR, SOCK_DGRAM, AF_INET
from json import dump, load, loads, dumps
from logging import basicConfig, DEBUG, exception
from os.path import isfile, dirname, realpath
#TODO: GAMESS support
#TODO: Is windows support really nessesary?
#TODO: Hot restart


###############################################################################
# LogableThread starts here
###############################################################################
class LogableThread(Thread):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._initargs = kwargs
        self.daemon = True
        self._real_run = self.run
        self.run = self._wrap_run
        self._alive = True

    def stop(self):
        self._alive = False

    def _wrap_run(self):
        while self._alive:
            try:
                self._real_run()
            except:
                # Thread will be restarted after exception
                exception('Uncaught exception occured!')
                super().__init__(**self._initargs)
            else:
                self._alive = False


###############################################################################
# Job starts here
###############################################################################
class Job():

    def __init__(self, type, id, params):
        super(Job, self).__init__()
        self.type = type
        self.id = id
        self.params = params


###############################################################################
# Queue starts here
###############################################################################
class Queue():

    def __init__(self):
        super(Queue, self).__init__()
        # The queue as it is
        self._queue = []
        # Lock to keep one by one access
        self._lock = Lock()
        # Empty indicator
        self.fill = Event()
        # Size of queue
        self.size = 0

    def get(self, block=True):
        if block:
            self.fill.wait()
        elif not self.fill.is_set():
            return None
        self._lock.acquire()
        self._queue.popleft()
        self.size = len(self._queue)
        if self.size == 0:
            self.fill.clear()
        self._lock.release()

    def put(self, obj):
        self._lock.acquire()
        self._queue.append(obj)
        self.size = len(self._queue)
        self.fill.set()
        self._lock.release()


###############################################################################
# Feeder starts here
###############################################################################
class UDPServer(LogableThread):

    def __init__(self):
        super(UDPServer, self).__init__()
        self.name = 'UDPServer'
        self.connector = socket(AF_INET, SOCK_DGRAM)
        self.fill_handlers()

# All reactions on messages is in self.msgs
    def fill_handlers(self):
        self.msghandlers = [
            self.m_AddJob,  # Add signal 0
            self.m_ShareJob,  # Share signal 1
            self.m_LFF,  # Looking For Free 2
            self.m_Free,  # Free signal 3
            ]

    def stop(self):
        self._alive = False
        self.connector.shutdown(SHUT_RDWR)
        self.connector.close()

    def run(self):
        self.connector.bind((shared.settings['host'], 59043))
        self.connector.listen(1)
        while self._alive:
            msg = self.connector.recvfrom(1024)
            if msg is None:
                continue
            data, peer = msg
            mtype, mdata = loads(data.decode('utf-8'))
            if mtype in self.msgs:
                self.msgs[mtype](mdata, peer)

# Handlers list
###############################################################################
    def m_AddJob(self, data, peer):
        # data = [type, id, params={}]
        shared.queue.put(Job(*data))
        kill(data[1], 19)  # Sends SIGSTOP to fake process

    def m_ShareJob(self, data, peer):
        pass

    def m_LFF(self, data, peer):
        if shared.processor.curjob is None:
            self.connector.sendto(
                dumps([3, None]).encode('utf-8'),
                (peer, 59043)
                )

    def m_Free(self, data, peer):
        pass


###############################################################################
# LocalProcessor starts here
###############################################################################
class Processor(LogableThread):

    def __init__(self):
        super(Processor, self).__init__()
        self.name = 'Processor'
        self.curjob = None
        self.preparators = dict()
        self.workers = dict()
        self.fill_handlers()

    def fill_handlers(self):
        self.preparators['G03'] = self.prepareG03
        self.workers['G03'] = self.doG03

    def run(self):
        while self._alive:
            self.curjob = shared.queue.get()
            # Prepare input
            self.prepare()
            # Do current job
            self.do()
            self.curjob = None

    def prepare(self):
        jt = self.curjob.type
        if jt in self.preparators:
            self.preparators[jt]()

    def do(self):
        jt = self.curjob.type
        if jt in self.workers:
            self.workers[jt]()

# Gaussian worker
###############################################################################
    def prepareG03(self):
        pass

    def doG03(self):
        pass


###############################################################################
# ObjectsGroup begins here
###############################################################################
class SharedObjects():

    def __init__(self):
        super(SharedObjects, self).__init__()
        self.queue = Queue()
        self.settings = dict()
        self.server = UDPServer()
        self.processor = Processor()
        self.default()

# Load nessesery variables from file
    def load(self, filename):
        if not isfile(filename):
            return False
        with open(filename, 'r') as f:
            objs = load(f)
        self.settings.update(objs['settings'])
        self.queue.load(objs['queue'])
        if self.settings['autohost']:
            self.settings['host'] = gethostbyname(gethostname())

    def default(self):
        self.settings['host'] = gethostbyname(gethostname())
        self.settings['autohost'] = True

    def save(self, filename):
        objs = dict()
        objs['settings'] = self.settings
        objs['queue'] = self.queue._queue
        with open(filename, 'w') as f:
            dump(objs, f, indent=4)


###############################################################################
# Start here
###############################################################################
if __name__ == '__main__':
    # environment initialization
    slash = '/'
    selfpath = dirname(realpath(__file__))
    logfile = selfpath + slash + 'queuer.log'
    # log initialization
    basicConfig(
        filename=logfile,
        level=DEBUG,
        format='[%(asctime)s] %(threadName)s: %(levelname)s, %(message)s',
        datefmt='%d.%m.%y %H:%M:%S'
    )
    # objects initialization
    # Objects, that used by threads will be in separated class
    shared = SharedObjects()
    # Loading settings and/or saving defaults to file
    shared.load(selfpath + slash + 'shared.jsn')
    shared.save(selfpath + slash + 'shared.jsn')
    # main working threads initialization
