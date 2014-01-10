#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Imports
from threading import Thread, Event, Lock
from socket import socket, gethostbyname, gethostname
from socket import SHUT_RDWR
from json import dump, load, loads
from logging import basicConfig, debug, DEBUG, info, warning, error, exception
from os.path import abspath, isfile, dirname, basename, getsize, realpath
#TODO: GAMESS support
#TODO: Windows support is realy needed?
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
# Notifier starts here
###############################################################################
class Notifier():

    def __init__(self):
        super(Notifier, self).__init__()
        self._new = Event()
        # message has a following structure:
        #     [type, (params)]
        self.message = None

    def get_message(self):
        self._new.wait()
        self._new.clear()
        return self.message

    def notify(self, type, params):
        self.message = [type, params]
        self._new.set()


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
        self._fill = Event()
        # Size of queue
        self.size = 0

    def get(self, block=True):
        if block:
            self._fill.wait()
        elif not self._fill.is_set():
            return None
        self._lock.acquire()
        self._queue.popleft()
        self.size = len(self._queue)
        self._lock.release()

    def put(self, obj):
        self._lock.acquire()
        self._queue.append(obj)
        self.size = len(self._queue)
        self._fill.set()
        self._lock.release()


###############################################################################
# Watcher starts here
###############################################################################
class Watcher(LogableThread):

    def __init__(self):
        super(Watcher, self).__init__()
        self.name = 'Watcher'


###############################################################################
# Feeder starts here
###############################################################################
class Feeder(LogableThread):

    def __init__(self):
        super(Feeder, self).__init__()
        self.name = 'Feeder'
        self.listener = socket()
        self.msgs = dict()
        self.fill_msgs()

# All reactions on messages is in self.msgs
    def fill_msgs(self):
        self.msgs[b'AJ'] = self.m_AddJob

    def stop(self):
        self._alive = False
        self.listener.shutdown(SHUT_RDWR)
        self.listener.close()

    def run(self):
        self.listener.bind((shared.settings['host'], 933))
        self.listener.listen(1)
        while self._alive:
            connection, peer = self.listener.accept()
            msg = connection.recv(2)
            if msg in self.msgs:
                self.msgs[msg](connection, peer)
            connection.close()

    def m_AddJob(self, con, peer):
        con.send(b'RQ')
        # jobinfo = [type, id, params={}]
        jobinfo = loads(con.recv(512).decode('utf-8'))
        shared.queue.put(Job(*jobinfo))


###############################################################################
# LocalProcessor starts here
###############################################################################
class LocalProcessor(LogableThread):

    def __init__(self):
        super(LocalProcessor, self).__init__()
        self.name = 'LocalProcessor'
        self.curjob = None

    def run(self):
        while self._alive:
            self.curjob = shared.queue.get()
            # Set busy flag, that lets RemoteProcessor work
            shared.busy.set()
            # Prepare input
            self.prepare()
            # Do current job
            self.do()
            # Tell other system, that job is done and LocalProcessor is free
            shared.busy.clear()
            self.curjob = None
            shared.queue.task_done()

    def prepare(self):
        pass

    def do(self):
        pass


###############################################################################
# RemoteProcessor starts here
###############################################################################
class RemoteProcessor(LogableThread):

    def __init__(self):
        super(RemoteProcessor, self).__init__()
        self.name = 'RemoteProcessor'


###############################################################################
# ObjectsGroup begins here
###############################################################################
class SharedObjects():

    def __init__(self):
        super(SharedObjects, self).__init__()
        self.queue = Queue()
        self.busy = Event()
        self.spy = Notifier()
        self.settings = dict()
        self.default()

# Load nessesery variables from file
    def load(self, filename):
        if not isfile(filename):
            return False
        with open(filename, 'r') as f:
            objs = load(f)
        self.settings.update(objs['settings'])
        self.queue.load(objs['queue'])
        if objs['busy']:
            self.busy.set()
        else:
            self.busy.clear()
        if self.settings['autohost']:
            self.settings['host'] = gethostbyname(gethostname())

    def default(self):
        self.settings['host'] = gethostbyname(gethostname())
        self.settings['autohost'] = True

    def save(self, filename):
        objs = dict()
        objs['settings'] = self.settings
        objs['busy'] = self.busy.isSet()
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
    feeder = Feeder()
    localproc = LocalProcessor()
    remoteproc = RemoteProcessor()