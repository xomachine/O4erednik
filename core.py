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


from api import LogableThread, FileTransfer
from json import loads, dumps
from logging import debug, error, warning, exception
from os import kill, name as osname, makedirs, sep, _exit
from os.path import dirname, basename
from socket import socket, SOL_SOCKET, SO_REUSEADDR, timeout, gethostbyaddr
from time import sleep, monotonic
from threading import Event, enumerate as threads
from shutil import rmtree
if osname == 'posix':
    from os import killpg


class Job():

    def __init__(self, jtype='dummy', files=dict(), params=dict(),
        uid=None):
        super(Job, self).__init__()
        if uid is None:
            uid = -int(monotonic() * 100)
        self.id = uid
        self.type = jtype
        self.files = files
        self.params = params


class Processor(LogableThread):

    def __init__(self, shared, parent):
        super(Processor, self).__init__()
        self.name = 'Processor'
        self.pid = None
        self.unlocked = Event()
        if shared.settings['Main']['Client mode']:
            self.cur = Job()
            self._alive = False
        else:
            self.unlocked.set()
            self.cur = None
        # Binding shared objects
        self.alloc = parent.alloc_nodes
        self.free = parent.free_nodes
        self.queue = shared.queue
        self.bcastaddr = shared.bcastaddr
        self.ifname = shared.settings['Main']['Interface']
        self.inform = shared.inform
        self.udp = shared.udpsocket
        self.workers = shared.modules
        self.shared = shared

    def getcur(self):
        return self.cur

    def getpid(self):
        return self.pid

    def run(self):
        while self._alive:
            if len(self.queue) == 0:
                # Send Free signal when queue is empty
                self.udp.sendto(
                    dumps(['F', None]).encode('utf-8'),
                    (self.bcastaddr(self.ifname), 50000)
                    )
                self.inform('empty')
                self.shared.clearfrozen()
            self.cur = self.queue.get()
            if len(self.queue) > 0:  # Look For Free if queue still fill
                self.udp.sendto(
                    dumps(['L', None]).encode('utf-8'),
                    (self.bcastaddr(self.ifname), 50000)
                    )
            if self.cur.type in self.workers:
                self.inform('start', self.cur)
                # Do job
                if 'reqprocs' in self.cur.params:
                    self.cur.params['nodelist'], self.cur.params['reqprocs'] = self.alloc(
                        self.cur.params['reqprocs'])
                process = self.workers[self.cur.type].do(self.cur)
                if process:
                    self.pid = process.pid
                    self.shared.freeze(self)
                    process.wait()
                if 'nodelist' in self.cur.params:
                    self.free(self.cur.params['nodelist'])
                self.inform('done', str(self.cur.id))
                if self.cur.id > 0:
                    try:
                        kill(self.cur.id, 9)
                    except:
                        pass
            elif self.cur.type == 'lock':
                self.inform('start', self.cur)
                self.shared.freeze(self)
                self.unlocked.clear()
                self.unlocked.wait()
                self.inform('done', str(self.cur.id))
            elif self.cur.type == 'waitfor':
                debug("Waitfor assignment")
                if 'pid' in self.cur.params:
                    debug("PID set successfuly")
                    self.pid = self.cur.params['pid']
                self.inform('start', self.cur)
                self.shared.freeze(self)
                while True:
                    try:
                        kill(self.pid, 0)
                    except:
                        exception("Looks like job is done")
                        break
                    else:
                        sleep(5) #TODO: Find optimal check interval
                if 'nodelist' in self.cur.params:
                    self.free(self.cur.params['nodelist'])
                self.inform('done', str(self.cur.id))
            self.cur = None


class RemoteReporter(LogableThread, FileTransfer):

    def __init__(self, processor, shared, peer):
        super(RemoteReporter, self).__init__()
        self.name = 'Reporter-' + gethostbyaddr(peer)[0]
        # Binding shared objects
        self.dir = shared.settings['Main']['Temporary directory'] + sep + \
        hex(int(monotonic() * 100))[2:]
        self.queue = shared.queue
        # Current running job, not nessesary self.cur
        self.curproc = processor.getcur
        self.pid = processor.getpid
        # Socket creation
        tcp = socket()
        tcp.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        tcp.settimeout(10)  # OPTIMIZE: Find optimal timeout
        tcp.bind(('0.0.0.0', 50000))
        tcp.listen(1)
        try:
            self.tcp, addr = tcp.accept()
        except timeout:
            tcp.close()
            self._alive = False
            return
        self.tcp.settimeout(10)
        self.setsocket(self.tcp)  # Setting socket for file transfer
        tcp.close()
        # Receive job class as it is
        try:
            sjob = loads(self.tcp.recv(4096).decode('utf-8'))
        except timeout:
            error('Timeout while obtainig job')
            self.stop()
            return
        self.job = Job(*sjob)
        # Equivalents of local and remote dirs
        self.eqdirs = dict()
        # Receive nessesary files and attach their with local paths to job
        for name, rpath in self.job.files.items():
            rdir = dirname(rpath)
            ldir = self.dir + sep + hex(hash(rdir))[3:]
            self.eqdirs[ldir] = rdir
            lpath = ldir + sep + basename(rpath)
            # Make directory
            try:
                makedirs(ldir, exist_ok=True)
                self.tcp.send(dumps(['G', rpath]).encode('utf-8'))
                # Receive file to local path
                self.recvfile(lpath)
            except:
                error('Error while obtaining job files')
                self.stop()
                return
            # Attach local path to job
            self.job.files[name] = lpath
        # Put job into the queue
        self.queue.put(self.job)
        shared.inform(
            'add', self.job)

    def stop(self):
        self.tcp.close()
        if self.job is self.curproc():
            killpg(self.pid(), 9)
        elif self.job in self.queue:
            self.queue.remove(self.job)
        rmtree(self.dir, True)

    def exception(self):
        warning('''Something stopped thread by rising exception,
remote job has been canceled''')
        self.stop()

    def run(self):
        # While job still in queue, receiver must wait
        while self.job in self.queue:
            self.tcp.send(dumps(['W', 10]).encode('utf-8'))
            self.tcp.recv(1)
            sleep(10)  # OPTIMIZE: Find optimal sleep interval
        # Job leaved queue, lets search it in processor
        # If output file has defined, stream it while job is in process
        if 'ofile' in self.job.files:
            if self.job == self.curproc():
                ldir, name = self.job.files['ofile'].rsplit(sep, 1)
                # Split and translate path to remote dir
                # Request sending log step by step to remote path
                self.tcp.send(dumps(
                    ['S', self.eqdirs[ldir] + sep + name]).encode('utf-8'))
                # Send log
                if self.tcp.recv(1) != b'O':
                    error('Unexpected answer during log streaming')
                    raise
                self.sendfile(self.job.files['ofile'], sbs=True,
                    alive=lambda: True if self.job is self.curproc() else False
                    )
        # Else just wait until job will be done
        else:
            while self.job == self.curproc():
                self.tcp.send(dumps(['W', 10]).encode('utf-8'))
                self.tcp.recv(1)
                sleep(10)  # OPTIMIZE: Find optimal sleep interval
        # After job completion send results back
        for lpath in self.job.files.values():
            # Split path
            ldir, name = lpath.rsplit(sep, 1)
            # Translate local dir to remote dir,
            # request and send file
            self.tcp.send(dumps(
                ['T', self.eqdirs[ldir] + sep + name]).encode('utf-8'))
            if self.tcp.recv(1) != b'O':
                raise
            self.sendfile(lpath)
        # Close connection
        self.tcp.send(dumps(['D', None]).encode('utf-8'))
        self.stop()


class RemoteReceiver(LogableThread, FileTransfer):

    def __init__(self, shared, peer):
        super(RemoteReceiver, self).__init__()
        self.peer = gethostbyaddr(peer)[0]
        self.name = 'Receiver-' + self.peer
        # Binding shared objects
        self.queue = shared.queue
        self.inform = shared.inform
        self.sendto = shared.udpsocket.sendto
        # Socket creation
        self.tcp = socket()
        self.tcp.settimeout(10)  # OPTIMIZE: Find optimal timeout
        sleep(1)  # OPTIMIZE: Find optimal sleep before connection
        try:
            self.tcp.connect((peer, 50000))
        except:
            error('Unable to connect remote worker ' + self.peer)
            self.stop()
            return
        self.setsocket(self.tcp)
        self.job = self.queue.get()
        debug("Job extracted: " + str(self.job.id))

    def exception(self):
        warning(
            '''Something stopped this thread by raising
            exception, job returned into queue''')
        self.stop()
        self.queue.put(self.job)
        self.inform('error', str(self.job.id))

    def run(self):
        # Sending job object as it is
        jpack = dumps([
            self.job.type,
            self.job.files,
            self.job.params,
            self.job.id
            ])
        self.tcp.send(jpack.encode('utf-8'))
        # Waiting for response from remote host
        while self._alive:
            req, param = loads(self.tcp.recv(1024).decode('utf-8'))
            if req == 'G':  # Get file
                self.sendfile(param)
            elif req == 'T':  # Transfer file
                self.tcp.send(b'O')
                self.recvfile(param)
            elif req == 'W':  # Wait some seconds and req again
                self.tcp.send(b'O')
                sleep(param)
            elif req == 'S':  # Start streaming
                self.inform('start', self.job, self.peer)
                self.tcp.send(b'O')
                self.recvfile(param, lambda: True if self._alive else False)
                self.inform('done', str(self.job.id))
            elif req == 'D':  # All Done, job completed
                if self.job.id > 0:
                    try:
                        kill(self.job.id, 9)
                    except:
                        pass
                self.stop()
            else:
                error('Unexpected response:' + req)
                self.exception()
                return
        if self._alive is False:  # Sharing process end
            debug('Closing ' + self.name)
            self.tcp.close()


class UDPServer(LogableThread):

    def __init__(self, shared):
        super(UDPServer, self).__init__()
        self.name = 'UDPServer'
        # Binding shared objects
        self.shared = shared
        self.queue = shared.queue
        self.udp = shared.udpsocket
        self.inform = shared.inform
        self.ifname = shared.settings['Main']['Interface']
        # Creating queue processor
        self.processor = Processor(self.shared, self)
        # Fill message-action dictonary
        self.fill_actions()

    def fill_actions(self):
        self.actions = {
            'F': self.mFree,  # To be continued...
            'A': self.mAdd,
            'L': self.mLFF,
            'K': self.mKill,
            'S': self.mShare,
            'E': self.mExit
            }

    def alloc_nodes(self, nprocs):
        allocated = []
        lst = []
        debug("Allocating nodes, requested: " + str(nprocs))
        procs = 0
        # Replace FreeHandler to collect list of free computers
        self.actions['F'] = lambda x, y: allocated.append([y, x])
        debug("Sending req for free nodes")
        self.udp.sendto(
                dumps(['L', 'lock']).encode('utf-8'),  # "lock" will protect us from interseption from other computers
                (self.shared.bcastaddr(self.ifname), 50000)
                )
        sleep(1)
        self.actions['F'] = self.mFree
        # Select nprocs from list
        debug("Found:" + str(allocated))
        for node, nproc in allocated:
            if [node, nproc] in lst: # Dublicate calls protection
                continue
            if procs < nprocs:
                if nproc == None:
                    continue
                debug("Asking for " + node)
                procs += nproc
                self.udp.sendto(
                    dumps(['A',
                        ['lock', {
                            'ifile': self.udp.getsockname()[0], 'ofile': ""
                            }, {}, 0]
                        ]).encode('utf-8'),
                    (node, 50000)
                    )
                lst.append([node, nproc])
        debug("Registred" + str(lst))
        return lst, procs

    def free_nodes(self, lst):
        for node, nproc in lst:
            self.udp.sendto(
                dumps(['K', "lock"]).encode('utf-8'),
                (node, 50000)
                )

    def stop(self):
        self.shared.freeze(self.processor)
        self._alive = False
        _exit(0)

    def run(self):
        self.processor.start()
        #self.processor.cur = True  # For tests
        while self._alive:
            data, peer = self.udp.recvfrom(1024)
            debug((data, peer))
            try:
                mtype, params = loads(data.decode('utf-8'))
            except ValueError:
                debug('It is not a proper request')
                continue
            if mtype in self.actions:
                self.actions[mtype](params, peer[0])

# Actions

    # Local addition to queue
    def mAdd(self, params, peer):
        job = Job(*params)
        if job.type in self.shared.modules:
            job = self.shared.modules[job.type].register(job)
        if self.processor.cur:  # Look For Free if processor is already busy
            self.udp.sendto(
                dumps(['L', None]).encode('utf-8'),
                (self.shared.bcastaddr(self.ifname), 50000)
                )
        debug("Added job with id:" + str(job.id))
        self.inform('add', job)
        self.queue.put(job)
        if job.id > 0:
            kill(job.id, 19)

    # Possibility to share work
    def mFree(self, params, peer):
        if (
            self.processor.cur is None or
            len(self.queue) == 0
            ):
            return
        self.udp.sendto(
            dumps(['S', None]).encode('utf-8'),
            (peer, 50000)
            )
        RemoteReceiver(self.shared, peer).start()
        if len(self.queue) > 0:  # Look For Free if queue still fill
            self.udp.sendto(
                dumps(['L', None]).encode('utf-8'),
                (self.shared.bcastaddr(self.ifname), 50000)
                )

    # Search for possibility to share work
    def mLFF(self, params, peer):
        if self.processor.cur is None and len(self.queue) == 0:
            self.udp.sendto(dumps(['F',
                    self.shared.settings['Main']['Number of processors']
                    ]).encode('utf-8'), (peer, 50000))
            if params is str:
                if params == "lock":
                    sleep(1)

    def mKill(self, params, peer):
        debug('Kill "' + str(params) + '"')
        if type(params) is int:
            debug("Removing from queue")
            self.queue.delete(params)
            debug(self.queue)
            self.inform('done', params)
        elif self.processor.cur and (
            params == "lock" or params == str(self.processor.cur.id)):
            debug("Stopping current job")
            if self.processor.unlocked.isSet():
                killpg(self.processor.pid, 9)  # Kill current task with SIGKILL
            else:
                self.processor.unlocked.set()
        else:
            all_threads = threads()
            for thread in all_threads:
                if thread.name.startswith('Receiver'
                ) and thread.job.id == int(params):
                    debug('Killing job ' + params)
                    thread.stop()

    def mShare(self, params, peer):
        RemoteReporter(self.processor, self.shared, peer).start()
        
    def mExit(self, params, peer):
        self.shared.freeze(self.processor)
        _exit(0)
