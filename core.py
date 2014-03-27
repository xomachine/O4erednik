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
from logging import debug, error, warning
from os import kill, killpg, makedirs, urandom
from os.path import dirname, basename
from socket import socket, SOL_SOCKET, SO_REUSEADDR, timeout, gethostbyaddr
from time import sleep
from threading import Event, enumerate as threads
from shutil import rmtree


class Job():

    def __init__(self, jtype='dummy', uid=0, files=dict(), params=dict()):
        super(Job, self).__init__()
        self.id = uid
        self.type = jtype
        self.files = files
        self.params = params


class Processor(LogableThread):

    def __init__(self, shared, parent):
        super(Processor, self).__init__()
        self.name = 'Processor'
        self.cur = None
        self.pid = None
        self.lock = Event()
        self.lock.set()
        # Binding shared objects
        self.alloc = parent.alloc_nodes
        self.free = parent.free_nodes
        self.queue = shared.queue
        self.bcastaddr = shared.bcastaddr
        self.ifname = shared.settings['Main']['Interface']
        self.inform = shared.inform
        self.udp = shared.udpsocket
        self.workers = shared.modules

    def getcur(self):
        return self.cur

    def getpid(self):
        return self.pid

    def run(self):
        while self._alive:
            if not self.queue.fill.isSet():
                # Send Free signal when queue is empty
                self.udp.sendto(
                    dumps(['F', None]).encode('utf-8'),
                    (self.bcastaddr(self.ifname), 50000)
                    )
                self.inform('empty')
            self.cur = self.queue.get()
            if self.queue.fill.isSet():  # Look For Free if queue still fill
                self.udp.sendto(
                    dumps(['L', None]).encode('utf-8'),
                    (self.bcastaddr(self.ifname), 50000)
                    )
            if self.cur.type in self.workers:
                self.inform('start', self.cur.files['ofile'], self.cur.type)
                # Do job
                if 'reqprocs' in self.cur.params:
                    self.cur.params['nodelist'] = self.alloc(
                        self.cur.params['reqprocs'])
                process = self.workers[self.cur.type].do(self.cur)
                self.pid = process.pid
                process.wait()
                if 'nodelist' in self.cur.params:
                    self.free(self.cur.params['nodelist'])
                self.inform('done', None)
                if self.cur.id > 0:
                    try:
                        kill(self.cur.id, 9)
                    except:
                        pass
            elif self.cur.type == 'lock':
                self.inform('start', self.cur.files['ifile'], self.cur.type)
                self.lock.clear()
                self.lock.wait()
                self.inform('done', None)
            self.cur = None


class RemoteReporter(LogableThread, FileTransfer):

    def __init__(self, processor, shared, peer):
        super(RemoteReporter, self).__init__()
        self.name = 'reporter-' + peer
        # Binding shared objects
        self.dir = shared.settings['Main']['Temporary directory'] + '/' + \
        hex(ord(urandom(1)))[2:]
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
        self.cur = Job(*sjob)
        # Equivalents of local and remote dirs
        self.eqdirs = dict()
        # Receive nessesary files and attach their with local paths to job
        for name, rpath in self.cur.files.items():
            rdir = dirname(rpath)
            ldir = self.dir + '/' + hex(hash(rdir))[3:]
            self.eqdirs[ldir] = rdir
            lpath = ldir + '/' + basename(rpath)
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
            self.cur.files[name] = lpath
        # Put job into the queue
        shared.inform(
            'add', basename(self.cur.files['ifile']) + ' - ' + self.name[9:])
        self.queue.put(self.cur)

    def stop(self):
        self.tcp.close()
        if self.cur is self.curproc():
            killpg(self.pid(), 9)
        elif self.cur in self.queue:
            self.queue.remove(self.cur)
        rmtree(self.dir, True)

    def exception(self):
        warning('''Something stopped thread by rising exception,
remote job has been canceled''')
        self.stop()

    def run(self):
        # While job still in queue, receiver must wait
        while self.cur in self.queue:
            self.tcp.send(dumps(['W', 10]).encode('utf-8'))
            self.tcp.recv(1)
            sleep(10)  # OPTIMIZE: Find optimal sleep interval
        # Job leaved queue, lets search it in processor
        # If output file has defined, stream it while job is in process
        if 'ofile' in self.cur.files:
            if self.cur == self.curproc():
                ldir, name = self.cur.files['ofile'].rsplit('/', 1)
                # Split and translate path to remote dir
                # Request sending log step by step to remote path
                self.tcp.send(dumps(
                    ['S', self.eqdirs[ldir] + '/' + name]).encode('utf-8'))
                # Send log
                if self.tcp.recv(1) != b'O':
                    error('Unexpected answer during log streaming')
                    raise
                self.sendfile(self.cur.files['ofile'], sbs=True,
                    alive=lambda: True if self.cur is self.curproc() else False
                    )
        # Else just wait until job will be done
        else:
            while self.cur == self.curproc():
                self.tcp.send(dumps(['W', 10]).encode('utf-8'))
                self.tcp.recv(1)
                sleep(10)  # OPTIMIZE: Find optimal sleep interval
        # After job completion send results back
        for lpath in self.cur.files.values():
            # Split path
            ldir, name = lpath.rsplit('/', 1)
            # Translate local dir to remote dir,
            # request and send file
            self.tcp.send(dumps(
                ['T', self.eqdirs[ldir] + '/' + name]).encode('utf-8'))
            if self.tcp.recv(1) != b'O':
                raise
            self.sendfile(lpath)
        # Close connection
        self.tcp.send(dumps(['D', None]).encode('utf-8'))
        self.stop()


class RemoteReceiver(LogableThread, FileTransfer):

    def __init__(self, shared, peer):
        super(RemoteReceiver, self).__init__()
        self.name = 'receiver-' + peer
        self.peer = peer
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
            error('Unable to connect remote worker ' + peer)
            self.stop()
            return
        self.setsocket(self.tcp)
        self.job = self.queue.get()

    def exception(self):
        warning(
            '''Something stopped this thread by raising
            exception, job returned into queue''')
        self.stop()
        self.queue.put(self.job)
        self.inform('error', self.peer)

    def run(self):
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
            #FIXME: Change inform system to prevent 'done'ing new job like completed
                self.inform('start', self.job.files['ofile'], self.job.type, self.peer)
                self.tcp.send(b'O')
                self.recvfile(param, lambda: True if self._alive else False)
                self.inform('done', self.peer)
            elif req == 'D':  # All Done, job completed
                if self.job.id > 0:
                    try:
                        kill(self.job.id, 9)
                    except:
                        pass
                self.stop()
            else:
                error('Unexpected response:' + req)
                raise
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
                dumps(['L', None]).encode('utf-8'),
                (self.shared.bcastaddr(self.ifname), 50000)
                )
        sleep(2)
        self.actions['F'] = self.mFree
        # Select nprocs from list
        debug("Found:" + str(allocated))
        for node, nproc in allocated:
            if procs < nprocs:
                debug("Asking for " + node)
                procs += nproc
                self.udp.sendto(
                    dumps(['A',
                        ['lock', 0, {'ifile': self.udp.getsockname()[0]}, {}]
                        ]).encode('utf-8'),
                    (node, 50000)
                    )
                lst.append([node, nproc])
        debug("Registred" + str(lst))
        return lst

    def free_nodes(self, lst):
        for node, nproc in lst:
            self.udp.sendto(
                dumps(['K', ""]).encode('utf-8'),
                (node, 50000)
                )

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
                self.actions[mtype](params, gethostbyaddr(peer[0])[0])

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
        self.inform('add', job.files['ifile'])
        self.queue.put(job)
        if job.id > 0:
            kill(job.id, 19)

    # Possibility to share work
    def mFree(self, params, peer):
        if (
            self.processor.cur is None or
            not self.queue.fill.isSet()
            ):
            return
        self.udp.sendto(
            dumps(['S', None]).encode('utf-8'),
            (peer, 50000)
            )
        RemoteReceiver(self.shared, peer).start()
        if self.queue.fill.isSet():  # Look For Free if queue still fill
            self.udp.sendto(
                dumps(['L', None]).encode('utf-8'),
                (self.shared.bcastaddr(self.ifname), 50000)
                )

    # Search for possibility to share work
    def mLFF(self, params, peer):
        if self.processor.cur is None and not self.queue.fill.isSet():
            self.udp.sendto(dumps(['F',
                    self.shared.settings['Main']['Number of processors']
                    ]).encode('utf-8'), (peer, 50000))

    def mKill(self, params, peer):
        debug('Kill "' + str(params) + '"')
        if type(params) is int:
            self.queue.delete(params)
        elif len(params) == 0:
            if self.processor.lock.isSet():
                killpg(self.processor.pid, 9)  # Kill current task with SIGKILL
            else:
                self.processor.lock.set()
        else:
            all_threads = threads()
            for thread in all_threads:
                if thread.name == 'receiver-' + params:
                    debug('Killing receiver-' + params)
                    thread.stop()
        self.inform('done', str(params))

    def mShare(self, params, peer):
        RemoteReporter(self.processor, self.shared, peer).start()
