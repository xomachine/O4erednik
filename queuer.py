#!/usr/bin/python3
#encoding:utf-8

from socket import socket, gethostbyname, gethostname, gethostbyaddr, SHUT_RDWR
from socket import SOL_SOCKET, SO_REUSEADDR, AF_INET, SOCK_DGRAM, SO_BROADCAST
from signal import SIGKILL
from threading import Thread, Condition, Lock
from time import sleep, strftime
from os.path import abspath, isfile, dirname, basename, getsize, realpath
from os import sysconf, environ, urandom, kill, _exit
from subprocess import Popen, call
from csv import writer, reader
from sys import platform
from uuid import uuid4
from logging import basicConfig, debug, DEBUG, info, warning, error, exception


#================================================================
# Platform dependent variables
#================================================================
selfpath = dirname(realpath(__file__))
if platform == 'win32':  # Do something with platform dependent code
    slash = '\\'
    nprocs = 1  # Gaussian on windows is not parallelized
    logfile = abspath(selfpath + "\\queuer.log")
    icons = abspath(selfpath + "\\icons")
    eol = "\r\n"
    logformat = "out"
    QString = lambda string: string.encode('cp1251').decode('cp1251')
else:
    slash = '/'
    nprocs = sysconf('SC_NPROCESSORS_ONLN')
    logfile = abspath(selfpath + "/queuer.log")
    icons = selfpath + "/icons"
    eol = "\n"
    logformat = "log"
    QString = lambda string: string


#================================================================
# LogableThread begins here
#================================================================
class LogableThread(Thread):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._real_run = self.run
        self.run = self._wrap_run

    def _wrap_run(self):
        try:
            self._real_run()
        except:
            exception('Uncaught exception is occured!')


#================================================================
# Settings class begins here
#================================================================
class Settings():
    array = dict()

    def __init__(self):
        super(Settings, self).__init__()

    def default(self):
        settings = self.array
        settings['rserver'] = False
        settings['rclient'] = False
        settings['rhost'] = "10.42.1.1"
        settings['bcastaddr'] = "10.42.0.255"
        if platform == 'win32':
            settings['gexe'] = "C:\\G03W\\g03.exe"
            settings['gtmp'] = "C:\\G03W\\Scratch"
            settings['lbcastaddr'] = "<broadcast>"
            settings['visexe'] = "gview.exe"
            settings['textexe'] = "notepad.exe"
            settings['samebcast'] = False
        else:
            # "/home/gaus"
            settings['gexe'] = "/home/zelentsov/gaussian/g03/g03"
            settings['gtmp'] = "/home/zelentsov/gaussian/tmp"
            settings['samebcast'] = True
            settings['visexe'] = "gview"
            settings['textexe'] = "kate"
        settings['autohost'] = True
        settings['host'] = gethostbyname(gethostname())

    def load(self):
        settings = self.array
        if isfile(selfpath + slash + "settings.csv"):
            sfile = open(selfpath + slash + "settings.csv")
            for key, val in reader(sfile):
                if val == 'False':
                    settings[key] = False
                elif val == 'True':
                    settings[key] = True
                else:
                    settings[key] = val
            sfile.close()
        if settings['autohost']:
            settings['host'] = gethostbyname(gethostname())
        if settings['samebcast']:
            settings['lbcastaddr'] = settings['bcastaddr']

    def save(self):
        settings = self.array
        sfile = open(selfpath + slash + "settings.csv", "w")
        csvset = writer(sfile)
        for key, val in settings.items():
            csvset.writerow([key, val])
        sfile.close()


#================================================================
# State class begins here
#================================================================
class State():
    _state = None
    _chnged = Condition()

    def __init__(self):
        pass

    def set(self, state, reason=None):  # Set the state and notify about it
        self._chnged.acquire()
        self._state = state
        self._chnged.notifyAll()
        self._chnged.release()

    def get(self):
        return self._state

# Wait for state is set or unset or changed
    def wait(self, state=None, reverse=False):
        self._chnged.acquire()
        if not state:
            self._chnged.wait()
            return
        if reverse:
            while state == self._state:
                self._chnged.wait()
        else:
            while state != self._state:
                self._chnged.wait()
        self._chnged.release()
        return


#================================================================
# Assignment class begins here
#================================================================
class Assignment():

    def __init__(self, pid=0, ifile=None):
        if ifile:
            self.ifile = abspath(ifile)
            self.wd = dirname(self.ifile)
        else:
            self.ifile = "LINDA"
        self.pid = pid  # PID of caller
        self.ofile = self.ifile[:-3] + logformat
        self.cfile = self.ifile[:-3] + "chk"  # Chk filename will be overwriten
        self.cbfile = basename(self.cfile)
        self.process = None

    def do(self):
        info("Job started:" + self.ifile)
        # Start gaussian job as subprocess
        if platform == 'win32':
            self.process = Popen(
                [keys.array['gexe'], basename(self.ifile)],
                cwd=self.wd
                )
        else:
            self.process = Popen(
                [keys.array['gexe'], self.ifile],
                cwd=self.wd
                )
        self.process.wait()  # and wait for it
        self.complete()
        return

    def complete(self):
        info("Job completed:" + self.ifile)
        if self.pid < 1:
            return
        try:
            kill(self.pid, SIGKILL)
        except OSError:
            pass
        return


#================================================================
# Queue class begins here
#================================================================
class Queue():
    _queue = []
    _shared = dict()
    _by_pid = dict()
    _lock = Lock()
    state = State()
    reason = "n"  # Reason of changing state
    current = None

# Add job into queue and change its state if nessesary
    def add(self, element, pid=0):
        self._lock.acquire()
        self._by_pid[pid] = element
        self._queue.insert(0, element)
        self._lock.release()
        if self.state.get() == 'w':
            self.state.set('f')
        else:
            self.state.set('w')
        self.reason = "a" + element.ifile
        debug("Added to queue pid=" + str(pid) + ",file=" + element.ifile)
        return

    def pop(self, wait=True):
        if len(self._queue) == 0:
            if wait:
                self.state.set('e')
                # Wait for changing state from 'e'
                self.state.wait('e', reverse=True)
            else:
                return None
        self._lock.acquire()
        elem = self._queue.pop()
        self._lock.release()
        if len(self._queue) == 0:
            self.state.set('w')
        else:
            self.state.set('f')
        debug(
            "Poped from queue pid=" + str(elem.pid) + ",file=" + elem.ifile)
        return elem

# Changes parametrs in input file to optimize job for that machine
    def prepare(self, n=nprocs):
        try:
            fs = open(self.current.ifile, 'r')
        except:
            return True
        lines = fs.readlines()
        proc = True
        chk = True
        wlines = []
        for line in lines:
            if line.startswith("%nprocshared"):
                line = "%nprocshared=" + str(n) + "\n"
                proc = False
            elif line.startswith("%chk"):
                if isfile(line[5:-1]):
                    self.current.cfile = line[5:-1]
                    self.current.cbfile = basename(line[5:-1])
                else:
                    line = "%chk=" + self.current.cbfile + "\n"
                chk = False  # CHECKME: handle with custom chknames
            elif line.startswith("%lindaworkers"):
                line = self.lindalock(line[14:])  # TODO: Handle with linda
            wlines.append(line)
        fs.close()
        if chk:
            wlines.insert(0, "%chk=" + self.current.cbfile + "\n")
        if proc:
            wlines.insert(0, "%nprocshared=" + str(n) + "\n")
        fs = open(self.current.ifile, 'w')
        for line in wlines:
            fs.write(line)
        fs.close()
        return False

# Do one job from queue
    def do(self):
        self.current = self.pop()
        if self.prepare():
            return True
        self.current.do()
        self._lock.acquire()
        if self.current.pid in self._by_pid:
            self._by_pid.pop(self.current.pid, self.current)
        self._lock.release()
        self.reason = "e" + self.current.ifile
        self.current = None

    def abort(self, pid):
        info("Aborting:" + str(pid))
        self._lock.acquire()
        if not (pid in self._by_pid):
            warning("PID not registered:" + str(pid))
            self._lock.release()
            return
        self._by_pid[pid].complete()
        if self._by_pid[pid] is self.current:
            try:
                self.current.process.kill()
                if platform == "linux":
                    call('pkill "l[0-9]{1,5}\\.exe"', shell=True)
                    # Abort() does not kill child links of gaussian
            except:
                pass
        else:
            if self._by_pid[pid] in self._queue:
                self._queue.remove(self._by_pid[pid])
            if self._by_pid[pid] in self._shared:
                self._shared.pop(
                    self._by_pid[pid],
                    self._shared[self._by_pid[pid]]
                    )
        self._by_pid.pop(pid, self._by_pid[pid])
        self.state.set(self.state.get())
        self._lock.release()
        return

# Send job from queue to given target and wait for its completeon
    def share(self, target):
        info("Trying to share with " + target)
        sock = socket()
        # Handshake with remote comp
        debug("Trying to connect:" + target)
        sock.connect((target, 9043))
        sock.send("s".encode('utf-8'))
        if sock.recv(2) != b'OK':
            sock.close()
            return
        debug("Handshake complete:" + target)
        job = self.pop(wait=False)
        if job is None:
            sock.send(b'ER')
            sock.close()
            return
        self.reason = "s" + job.ifile
        self._shared[job] = gethostbyaddr(target)[0]
        sock.send(b'go')
        info("Sharing:" + basename(job.ifile) + " to " + target)
        self.sendfile(job.ifile, sock, b'ti')
        if isfile(job.cfile):
            self.sendfile(job.cfile, sock, b'tc')
        else:
            sock.send(b'no')
        sock.send(b'do')
        sock.close()
        sleep(2)
        # Start recerving stream and results
        sock = socket()
        try:
            sock.connect((target, 9109))
        except:
            error(
                "Cann't connect to " + target + " for " + basename(job.ofile)
                )
            info("Turning " + basename(job.ifile) + " back to queue")
            self._shared.pop(job, gethostbyaddr(target)[0])
            self.add(job, job.pid)
            return 1

        if sock.recv(2) != b'ts':  # Recerving stream
            sock.send(b'ER')
            error(
                "Unexpected responce from " + target +
                " while recerving " + basename(job.ofile)
                )
            info("Turning " + basename(job.ifile) + " back to queue")
            self._shared.pop(job, gethostbyaddr(target)[0])
            self.add(job, job.pid)
            return 1
        fs = open(job.ofile, 'wb+', 0)
        sock.send(b'OK')
        info(
            "Recerving " + basename(job.ofile) +
            " step by step from " + target
            )
        while True:
            if sock.recv(1) != b'R':
                info(basename(job.ifile) + " completetd at " + target)
                break
            if (job in self._shared):
                sock.send(b'O')
            else:
                info(basename(job.ifile) + " at " + target + "is aborted here")
                sock.send('A')
                sock.close()
                return
            buf = sock.recv(1024)
            sock.send(b'O')
            fs.write(buf)
        fs.close()
        self.recvfile(job.ofile, sock, b'tl')
        self.recvfile(job.cfile, sock, b'tc')
        self._shared.pop(job, gethostbyaddr(target)[0])
        self._by_pid.pop(job.pid, job)
        sock.close()
        job.complete()
        self.state.set(self.state.get())

# Find and lock computers for linda
    def lindalock(self, lindastring):
        return ""

# Reserve and add to queue job from another queuer
    def recerve(self, sock):
        if not keys.array['rserver']:
            if self.state.get() != "e":
                sock.send(b'ER')
                return
            fakepid = 0
        else:
            fakepid = -ord(urandom(1))
        tmpinput = keys.array['gtmp'] + slash + gethostbyaddr(
            sock.getpeername()[0]
            )[0] + '_' + str(uuid4()).replace("-", "")[:2] + ".com"
        info("Accepting job from " + basename(tmpinput)[:-4])
        shared = Assignment(pid=fakepid, ifile=tmpinput)
        sock.send(b'OK')
        if sock.recv(2) == b'go':
            self.recvfile(shared.ifile, sock, b'ti')
            self.recvfile(shared.cfile, sock, b'tc')
            if sock.recv(2) == b'do':
                ls = LogableThread(
                    target=self.sendlog,
                    name="logsender",
                    args=[shared, sock.getsockname()[0]]
                    )  # Log will start streaming in separated thread
                ls.start()
                queue.add(shared)

# Stream log of remotely added job
# TODO: IsAlive requests
    def sendlog(self, job, host):
        sleep(1)
        info("Preparing for streaming " + basename(job.ofile))
        lsock = socket()
        lsock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        lsock.bind(
            (host, 9109)  # CHECKME Or rhost
            )
        lsock.listen(1)
        debug("Created socket for streaming " + basename(job.ofile))
        sock, addr = lsock.accept()
        debug("Accepted from " + addr[0])

        sock.send(b'ts')
        if sock.recv(2) != b'OK':
            error("Unexpected response from " + addr[0])
            return 1
        fs = None
        while job.process.poll() is None:
            try:
                fs = open(job.ofile, 'rb')
            except:
                sleep(10)
                continue
            else:
                break
        while job.process.poll() is None:
            where = fs.tell()
            buf = fs.readline()
            if not buf:
                fs.seek(where)
                sleep(1)
            else:
                try:
                    sock.send(b'R')
                    if sock.recv(1) == b'O':
                        sock.send(buf)
                        sock.recv(1)
                    else:
                        info(basename(job.ifile) + " is aborted remotely")
                        self.abort(0)
                        lsock.close()
                        fs.close()
                        return
                except:
                    info("Disconected while " + basename(job.ifile))
                    self.abort(0)
                    lsock.close()
                    fs.close()
                    return
        sock.send(b'C')
        info(basename(job.ifile) + " is completed")
        if fs:
            fs.close()

        if isfile(job.ofile):
            self.sendfile(job.ofile, sock, b'tl')
        else:
            sock.send(b'no')
        if isfile(job.cfile):
            self.sendfile(job.cfile, sock, b'tc')
        else:
            sock.send(b'no')
        sock.close()
        lsock.close()
        return

#----------------------------------------------
# Transfering stuff
#----------------------------------------------
    def sendfile(self, path, sock, id, bufsize=1024):
        size = 0
        filesize = getsize(path)
        sock.send(id)  # Check that this action is required
        if sock.recv(2) != b'OK':
            error(str(id) + " action is not required")
            return 1
        sock.send(str(filesize).encode('utf-8'))  # Send filesize
        if sock.recv(2) != b'OK':
            error("Unexpected response")
            return 1
        info(
            "Sending file=" + basename(path) + ",size=" + str(filesize)
            )
        fs = open(path, 'rb')
        while size < filesize:
            buf = fs.read(bufsize)
            size += len(buf)
            sock.send(buf)
        if sock.recv(2) != b'SS':  # Success
            fs.close()
            return 1
        info(
            "Success:" + basename(path)
            )
        fs.close()
        return 0

    def recvfile(self, path, sock, id, bufsize=1024):
        size = 0
        if sock.recv(2) != id:  # Check that this action is required
            error(str(id) + " action is required but not given")
            sock.send(b'ER')
            return 1
        fs = open(path, 'wb+')
        sock.send(b'OK')
        filesize = int(sock.recv(64).decode('utf-8'))  # Get filesize
        sock.send(b'OK')
        info("Recerving file=" + basename(path) + ",size=" + str(filesize))
        while size < filesize:
            buf = sock.recv(bufsize)
            size += len(buf)
            fs.write(buf)
        sock.send(b'SS')
        fs.close()
        return 0


#================================================================
# ShareHandler class begins here
#================================================================
class ShareHandler(LogableThread):

    alive = True

    def __init__(self):
        LogableThread.__init__(self)
        self.daemon = True
        self.name = "sharehandler"
        self.listener = LogableThread(
            target=self.listen,
            name="bcastlistener"
            )
        self.listener.daemon = True
        self.action = None
        self.sender = None
        self.listener.start()

    def stop(self):
        self.alive = False
        if self.sock:
            self.sock.close()

    def run(self):
        while self.alive:
            if queue.state.get() == 'f':  # Full of assignments
                debug("Queue is full!")
                self.listenfor = b'f'
                self.action = lambda: LogableThread(
                    target=queue.share,
                    args=[self.sender],
                    name="share-" + gethostbyaddr(self.sender)[0]
                    ).start()
                self.broadcast(b'h')
            elif queue.state.get() == 'w':  # Working last
                debug("Queue is working on last!")
                self.listenfor = b'n'
            elif queue.state.get() == 'e':  # Free
                debug("Queue is empty!")
                self.listenfor = b'h'
                self.action = lambda: self.broadcast(b'f')
                self.action()
            queue.state.wait()

    def listen(self):
        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            self.sock.bind((keys.array['lbcastaddr'], 5043))
        except:
            warning("Local network not found!")
            return
        while self.alive:
            msg = self.sock.recvfrom(1)
            if not self.alive:
                return
            debug("Got broadcast:" + str(msg[0]) + " from " + str(msg[1]))
            if msg[0] == self.listenfor:
                self.sender = msg[1][0]
                self.action()

    def broadcast(self, msg):
        sendsock = socket(AF_INET, SOCK_DGRAM)
        sendsock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        sendsock.setblocking(0)
        sendsock.sendto(msg, (keys.array['bcastaddr'], 5043))
        sendsock.close()
        return


#================================================================
# Listener class begins here
#================================================================
class Listener(LogableThread):

    def __init__(self, lhost):
        LogableThread.__init__(self)
        self.daemon = True
        self.name = "listener"
        self.localsock = socket()
        self.localsock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.host = lhost
        self.alive = True

# CHECKME May raise exceptions
    def stop(self):
        self.alive = False
        self.localsock.shutdown(SHUT_RDWR)
        self.localsock.close()

    def run(self):
        self.localsock.bind((self.host, 9043))
        self.localsock.listen(5)
        while self.alive:
            try:
                conn, addr = self.localsock.accept()
            except:
                continue
            data = conn.recv(256).decode('utf-8')
            debug("Reserved data=" + data)
            self.handle(conn, addr, data)
            conn.close()
        self.localsock.close()

    def handle(self, conn, addr, data):
        if not data:
            return
        if data[0] == 'a':  # The dialog may be prefered
            try:
                pidlen = int(data[1:2])
                pid = int(data[2:2 + pidlen])
                kill(pid, 0)
                arg = data[2 + pidlen:-1]
            except:
                error("Incorrect message format: " + data)
                return
            queue.add(Assignment(pid, arg), pid)
            conn.send(('O').encode('utf-8'))
            conn.close()
        elif data[0] == 'k':
            try:
                pid = int(data[1:])
            except:
                error("Incorrect PID: " + data[1:])
                return
            queue.abort(pid)
        elif data[0] == 's':
            queue.recerve(conn)
            return
        elif data[0] == 'l':
            if len(data) > 1:
                if data[1] == 'b':
                    if queue.state.get() == 'e':
                        queue._lock.acquire()
                        queue.current = Assignment()
                elif data[1] == 'e':
                    if queue.current and queue.current.ifile == 'LINDA':
                        queue.current = None
                        queue._lock.release()


#================================================================
# Processor class begins here
#================================================================
class Processor(LogableThread):

    def __init__(self):
        LogableThread.__init__(self)
        self.daemon = True
        self.name = "processor"
        self.alive = True

    def run(self):
        while self.alive:
            queue.do()
            if keys.array['rclient']:
                sleep(10)


#================================================================
# ThreadsHandler class begins here
#================================================================
class ThreadsHandler():

    def __init__(self):
        super(ThreadsHandler, self).__init__()
        self.listener = None
        self.rlistener = None
        self.sharehandler = None
        # Queue processor, that takes jobs from queue and doing it
        processor = Processor()
        processor.start()
        self.init()

    def init(self):
        self.listener = Listener(keys.array['host'])
        if keys.array['rserver']:
            self.rlistener = Listener(keys.array['rhost'])
        if keys.array['rclient']:
            queue.do = lambda: queue.share(keys.array['rhost'])
        else:
            self.sharehandler = ShareHandler()

    def start(self):
        self.listener.start()
        if self.rlistener:
            self.rlistener.start()
        # Interactor with other queuers, propouses help than queue is empty
        # and requests help in other case
        if self.sharehandler:
            self.sharehandler.start()

    def stop(self):
        if self.listener and self.listener.isAlive():
            self.listener.stop()
        if self.rlistener and self.rlistener.isAlive():
            self.rlistener.stop()
        if self.sharehandler and self.sharehandler.isAlive():
            self.sharehandler.stop()
        self.listener = None
        self.rlistener = None
        self.sharehandler = None

    def restart(self):
        self.stop()
        self.init()
        self.start()


#================================================================
#================================================================
# Application starts here
#================================================================
#================================================================
# Preparing settings and log
# Preparing log
basicConfig(
    filename=logfile,
    level=DEBUG,  # INFO
    format='[%(asctime)s] %(threadName)s: %(levelname)s, %(message)s',
    datefmt='%d.%m.%y %H:%M:%S'
    )

# Declaring main queue of assignments
queue = Queue()

# Inital settings loading
keys = Settings()
keys.default()
keys.load()
keys.save()
# Preparing gaussian environment
environ['g03root'] = dirname(dirname(keys.array['gexe']))
environ['GAUSS_EXEDIR'] = dirname(keys.array['gexe'])
environ['GAUSS_SCRDIR'] = keys.array['gtmp']
"""
if platform == "linux":
    call(
        ['/usr/bin/rm', '-f', keys.array['gtmp'] + '/*'],
        shell=False,
        stderr=None,
        stdout=None
        )
"""
# Starting main threads
threads = ThreadsHandler()
threads.start()

info("=====================================")
info("Started on " + keys.array['host'])
info("=====================================")

#================================================================
# GUI begins here
#================================================================
try:
    from PyQt4 import QtGui
    from PyQt4.QtCore import SIGNAL, Qt
    import icons
except:
    exception("PyQt4 library not found! Running without GUI")
else:
#----------------------------------------------
# Left click menu
#----------------------------------------------
    class LeftMenu(QtGui.QMenu):
        def __init__(self, parent=None):
            QtGui.QMenu.__init__(self, parent)
            self.connect(self, SIGNAL('MenusUpdate()'), self.MenusUpdate)
            self.connect(self, SIGNAL('MenuLastAdd(QString)'), self.MenuLastAdd)
            act = QtGui.QAction(icon_['add'], QString("Добавить задачу"), self)
            act.triggered.connect(self.selectJob)
            self.addAction(act)

            self.addSeparator()

            hoveract = lambda x:\
                QtGui.QToolTip.showText(
                    QtGui.QCursor.pos(),
                    x.toolTip()
                    )
            self.local = self.addMenu(
                icon_['run'],
                QString("На этом компьютере")
                )
            self.local.hovered.connect(hoveract)

            self.remote = self.addMenu(
                icon_['remote'],
                QString("На других компьютерах")
                )
            self.remote.hovered.connect(hoveract)

            self.last = self.addMenu(
                icon_['wait'],
                QString("Последние задачи")
                )
            self.last.hovered.connect(hoveract)

            self.dialog = QtGui.QFileDialog()
            # Prevents exit from GUI after closing dialog
            self.dialog.setAttribute(Qt.WA_QuitOnClose, False)

        def MenusUpdate(self):
            self.MenuLocalUpdate()
            self.MenuRemoteUpdate()

        def MenuLocalUpdate(self):
            self.local.clear()
            if queue.current is None:
                return
            pid = queue.current.pid
            name = basename(queue.current.ifile)
            if pid == 0:
                menu = self.local.addMenu(icon_['remote'], name)
            else:
                menu = self.local.addMenu(icon_['run'], name)
            menu.setToolTip(queue.current.ifile)
            act = menu.addAction(icon_['delete'], QString("Отмена"))
            act.triggered.connect(lambda: queue.abort(queue.current.pid))
            for element in reversed(queue._queue):  # CHECKME order in queue
                pid = element.pid
                name = basename(element.ifile)
                menu = self.local.addMenu(icon_['wait'], name)
                menu.setToolTip(element.ifile)
                abort = lambda: queue.abort(element.pid)
                act = menu.addAction(icon_['delete'], QString("Удалить"))
                act.triggered.connect(abort)

        def MenuRemoteUpdate(self):
            self.remote.clear()
            for element in queue._shared.keys():
                name = queue._shared[element] + ":" + basename(element.ifile)
                menu = self.remote.addMenu(icon_['remote'], name)
                menu.setToolTip(element.ifile)
                abort = lambda: queue.abort(element.pid)
                act = menu.addAction(icon_['delete'], QString("Отмена"))
                act.triggered.connect(abort)

        def MenuLastAdd(self, ofile):
            menu = self.last.addMenu(
                icon_['free'],
                strftime("[%H:%M] ") + basename(ofile)
                )
            menu.setToolTip(ofile)
            act = menu.addAction(
                icon_['run'],
                QString("Открыть в визуализаторе")
                )
            act.triggered.connect(
                lambda: Popen([keys.array['visexe'], ofile])
                )
            act = menu.addAction(icon_['run'], QString("Открыть как текст"))
            act.triggered.connect(
                lambda: Popen([keys.array['textexe'], ofile])
                )
            act = menu.addAction(icon_['delete'], QString("Удалить из списка"))
            act.triggered.connect(
                lambda: self.last.removeAction(
                    menu.menuAction()
                    )
                )
            if len(self.last.actions()) > 20:
                self.last.removeAction(self.last.actions.pop())

        def selectJob(self):
            self.dialog.setWindowTitle(QString("Выберите задачу"))
            self.dialog.setLabelText(1, QString("Имя файла"))
            self.dialog.setLabelText(2, QString("Тип файла"))
            self.dialog.setLabelText(3, QString("Добавить"))
            self.dialog.setLabelText(4, QString("Отмена"))
            self.dialog.setDirectory(dirname(keys.array['gexe']))
            self.dialog.setFilter(
                QString("Задачи Gaussian (*.gjf *.com *.g03)")
                )
            self.dialog.setOption(QtGui.QFileDialog.DontUseNativeDialog)
            self.dialog.exec_()
            filename = self.dialog.selectedFiles()[0]
            if isfile(filename):
                fakepid = -ord(urandom(1))
                queue.add(Assignment(fakepid, filename), fakepid)

#----------------------------------------------
# Settings window
#----------------------------------------------
    class SettingsWindow(QtGui.QDialog):
        def __init__(self, parent=None):
            QtGui.QDialog.__init__(self, parent)

            self.setAttribute(Qt.WA_QuitOnClose, False)

            try:
                from settings import Ui_SettingsDialog
            except ImportError:
                warning("Cann't find settings component")
                self.setWindowTitle("Ошибка, диалог не найден")
                self.resize(200, 100)
            else:
                self.ui = Ui_SettingsDialog()
                self.ui.setupUi(self)
                self.Load()
                self.ui.Save.released.connect(self.Save)
                self.ui.Default.released.connect(self.Default)
                self.ui.gcomch.released.connect(
                    lambda: self.Open(self.ui.gcom, 1)
                    )
                self.ui.gtmpch.released.connect(
                    lambda: self.Open(self.ui.gtmp, 2)
                    )
                self.ui.viscomch.released.connect(
                    lambda: self.Open(self.ui.viscom, 1)
                    )
                self.ui.textcomch.released.connect(
                    lambda: self.Open(self.ui.textcom, 1)
                    )
                self.ui.autohost.stateChanged.connect(
                        lambda x: self.ui.host.setDisabled(
                            True if x == 2 else False
                            )
                    )
                self.ui.lbcastsame.stateChanged.connect(
                        lambda x: self.ui.lbcast.setDisabled(
                            True if x == 2 else False
                            )
                    )
                self.ui.clientmode.toggled.connect(
                        lambda: self.ui.rhost.setEnabled(
                            self.ui.clientmode.isChecked(
                                ) or self.ui.servermode.isChecked()
                            )
                    )
                self.ui.servermode.toggled.connect(
                        lambda: self.ui.rhost.setEnabled(
                            self.ui.clientmode.isChecked(
                                ) or self.ui.servermode.isChecked()
                            )
                    )

                self.dialog = QtGui.QFileDialog()
                self.dialog.setAttribute(Qt.WA_QuitOnClose, False)
                self.dialog.setOption(QtGui.QFileDialog.DontUseNativeDialog)
                self.dialog.setWindowTitle(QString("Выберите назначение"))
                self.dialog.setLabelText(1, QString("Имя файла"))
                self.dialog.setLabelText(2, QString("Тип файла"))
                self.dialog.setLabelText(3, QString("Выбор"))
                self.dialog.setLabelText(4, QString("Отмена"))
                self.dialog.setDirectory(dirname(keys.array['gexe']))

        def Open(self, qline, mode):
            self.dialog.setFileMode(mode)
            if self.dialog.exec_():
                filename = self.dialog.selectedFiles()[0]
                qline.clear()
                qline.insert(filename)

        def Save(self):
            keys.array['host'] = self.ui.host.displayText()
            keys.array['rhost'] = self.ui.rhost.displayText()
            keys.array['bcastaddr'] = self.ui.bcast.displayText()
            keys.array['lbcastaddr'] = self.ui.lbcast.displayText()
            keys.array['gtmp'] = self.ui.gtmp.displayText()
            keys.array['gexe'] = self.ui.gcom.displayText()
            keys.array['visexe'] = self.ui.viscom.displayText()
            keys.array['textexe'] = self.ui.textcom.displayText()
            keys.array['autohost'] = self.ui.autohost.isChecked()
            keys.array['samebcast'] = self.ui.lbcastsame.isChecked()
            keys.array['rclient'] = self.ui.clientmode.isChecked()
            keys.array['rserver'] = self.ui.servermode.isChecked()
            keys.save()
            keys.load()
            self.Load()
            threads.restart()
            self.accept()

        def Load(self):
            self.ui.autohost.setCheckState(
                2 if keys.array['autohost'] else 0
                )
            self.ui.servermode.setCheckState(
                2 if keys.array['rserver'] else 0
                )
            self.ui.clientmode.setCheckState(
                2 if keys.array['rclient'] else 0
                )
            self.ui.lbcastsame.setCheckState(
                2 if keys.array['samebcast'] else 0
                )
            self.ui.host.clear()
            self.ui.host.insert(keys.array['host'])
            self.ui.host.setDisabled(keys.array['autohost'])
            self.ui.rhost.clear()
            self.ui.rhost.insert(keys.array['rhost'])
            self.ui.rhost.setEnabled(
                keys.array['rclient'] or keys.array['rserver']
                )
            self.ui.bcast.clear()
            self.ui.bcast.insert(keys.array['bcastaddr'])
            self.ui.lbcast.clear()
            self.ui.lbcast.insert(keys.array['lbcastaddr'])
            self.ui.lbcast.setDisabled(keys.array['samebcast'])
            self.ui.gtmp.clear()
            self.ui.gtmp.insert(keys.array['gtmp'])
            self.ui.gcom.clear()
            self.ui.gcom.insert(keys.array['gexe'])
            self.ui.viscom.clear()
            self.ui.viscom.insert(keys.array['visexe'])
            self.ui.textcom.clear()
            self.ui.textcom.insert(keys.array['textexe'])

        def Default(self):
            keys.default()
            self.Load()

#----------------------------------------------
# Right click menu
#----------------------------------------------
    class RightMenu(QtGui.QMenu):
        def __init__(self, parent=None):
            QtGui.QMenu.__init__(self, parent)

            self.setwin = SettingsWindow()

            act = QtGui.QAction(QString("Настройки"), self)
            act.triggered.connect(self.setwin.show)
            self.addAction(act)

            act = QtGui.QAction(icon_['delete'], QString("Выход"), self)
            act.triggered.connect(self.doExit)
            self.addAction(act)

        def doExit(self):
            _exit(0)

#----------------------------------------------
# Tray icon
#----------------------------------------------
    class TrayIcon(QtGui.QSystemTrayIcon):
        def __init__(self, parent=None):
            QtGui.QSystemTrayIcon.__init__(self, parent)
            self.setIcon(icon_['wait'])
            self.setToolTip(QString('Инициализация'))
            self.connect(
                self,
                SIGNAL('setStateIcon(QString)'),
                self.setStateIcon
                )
            self.connect(
                self,
                SIGNAL('setToolTip(QString)'),
                self.setToolTip
                )
            self.connect(self,
                SIGNAL('showMessage(QString,QString)'),
                self.showMessage
                )

            self.Rmenu = RightMenu(parent)
            self.setContextMenu(self.Rmenu)

            self.Lmenu = LeftMenu(parent)

            self.activated.connect(
                lambda x: x == self.Trigger and self.Lmenu.exec_(
                    QtGui.QCursor.pos()))

        def setStateIcon(self, icon):
            self.setIcon(icon_[icon])

#----------------------------------------------
# GUI Handler
#----------------------------------------------
    class GUIHandler(LogableThread):
        def __init__(self):
            LogableThread.__init__(self)
            self.daemon = True
            self.name = "GUIHandler"

        def run(self):
            while True:
                self.setMainIcon()
                self.setLocalList()
                queue.state.wait()

        def setMainIcon(self):
            debug(
                "MemStat:\n" +
                "Queue:" + str(len(queue._queue)) + "\n" +
                str(queue._queue) + "\n" +
                "Shared:" + str(len(queue._shared)) + "\n" +
                str(queue._shared) + "\n" +
                "by pid:" + str(len(queue._by_pid)) + "\n" +
                str(queue._by_pid)
                )
            if queue.state.get() == 'e':
                tray.emit(SIGNAL('setStateIcon(QString)'), "free")
                tray.emit(SIGNAL('setToolTip(QString)'), QString("Свободен!"))
            else:
                if queue.current:
                    curpid = queue.current.pid
                    curname = basename(queue.current.ifile)
                else:
                    return
                if curpid == 0:
                    tray.emit(SIGNAL('setStateIcon(QString)'), "remote")
                    tray.emit(
                        SIGNAL('setToolTip(QString)'),
                        QString("Идет расчет задачи с другого компьютера")
                        )
                else:
                    tray.emit(SIGNAL('setStateIcon(QString)'), "run")
                    tray.emit(
                        SIGNAL('setToolTip(QString)'),
                        QString(
                            'Идет расчет:' + curname + "..." + eol +
                            str(len(queue._queue)) + ' осталось.'
                            )
                        )
            if queue.reason[0] == 'e':
                tray.emit(
                    SIGNAL('showMessage(QString,QString)'),
                    QString('Задача завершена'),
                    QString(queue.reason[1:])
                    )
                tray.Lmenu.emit(
                    SIGNAL('MenuLastAdd(QString)'),
                    QString(queue.reason[1:-3] + logformat)
                    )
                debug(queue.reason)
            elif queue.reason[0] == 'a':
                tray.emit(
                    SIGNAL('showMessage(QString,QString)'),
                    QString('Задача добавлена'),
                    QString(queue.reason[1:])
                    )
            elif queue.reason[0] == 's':
                tray.emit(
                    SIGNAL('showMessage(QString,QString)'),
                    QString('Задача отправлена'),
                    QString(
                        basename(queue.reason[1:]) +
                        ' отправлено на другой компьютер.'
                        )
                    )
            queue.reason = "n"

        def setLocalList(self):
                tray.Lmenu.emit(SIGNAL('MenusUpdate()'))

    gui = GUIHandler()
    app = QtGui.QApplication([])
#----------------------------------------------
# Icon loader
#----------------------------------------------

    def loadicon(icon):
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(icon)
        return QtGui.QIcon(pixmap)

    icon_ = dict()
    icon_['add'] = loadicon(icons.add_icon)
    icon_['delete'] = loadicon(icons.delete_icon)
    icon_['free'] = loadicon(icons.free_icon)
    icon_['remote'] = loadicon(icons.remote_icon)
    icon_['run'] = loadicon(icons.run_icon)
    icon_['wait'] = loadicon(icons.wait_icon)

    tray = TrayIcon()
    tray.show()
    gui.start()
    app.exec_()

threads.listener.join()