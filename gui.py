# -*- coding: utf-8 -*-

from PyQt4.QtGui import QApplication, QSystemTrayIcon, QIcon, QPixmap, QMenu
from PyQt4.QtGui import QCursor, QToolTip
from PyQt4.QtCore import QTextCodec, SIGNAL
from os import _exit
from os.path import basename
from logging import debug
from json import dumps
import icons

_icons = dict()


class LeftMenu(QMenu):

    def __init__(self):
        super(LeftMenu, self).__init__()
        self.now = dict()
        # Fill elements of menu
        self.addAction(
            _icons['add'],
            self.tr('Add assignment')
            ).triggered.connect(self.DoAdd)

        self.addSeparator()

        self.working = self.addMenu(
            _icons['run'],
            self.tr('In process')
            )

        self.queue = self.addMenu(
            _icons['wait'],
            self.tr('Queue')
            )

        self.recent = self.addMenu(
            _icons['free'],
            self.tr('Recent')
            )

    def DoAdd(self):
        pass


class RightMenu(QMenu):

    def __init__(self):
        super(RightMenu, self).__init__()

        exitact = self.addAction(_icons['delete'], self.tr('Exit'))
        exitact.triggered.connect(self.DoExit)

    def DoExit(self):
        _exit(0)


class TrayIcon(QSystemTrayIcon):

    def __init__(self):
        super(TrayIcon, self).__init__()

        # Create right and left click menus
        self.rmenu = RightMenu()
        self.lmenu = LeftMenu()

        self.setContextMenu(self.rmenu)
        self.activated.connect(self.DoActivate)

        # Connect signals
        # self.connect(self, SIGNAL(), self.sigfunc)
        self.connect(self, SIGNAL('add(QString, QString)'), self.sigAdd)
        self.connect(self, SIGNAL('empty()'), self.sigEmpty)
        self.connect(self, SIGNAL('start()'), self.sigStart)
        self.connect(self, SIGNAL('done(QString)'), self.sigDone)
        self.connect(self, SIGNAL('shared(QString)'), self.sigStart)
        self.connect(self, SIGNAL('error(QString)'), self.sigError)

    def DoActivate(self, reason):
        if reason == self.Trigger:
            self.lmenu.exec_(QCursor.pos())

# Signals

    def sigAdd(self, name, tooltip):
        elem = self.lmenu.queue.addMenu(_icons['wait'], name)
        elem.setToolTip(tooltip)
        elem.enterEvent = lambda x: QToolTip.showText(QCursor.pos(), name)
        elem.leaveEvent = lambda x: QToolTip.hideText()
        act = elem.addAction(
            _icons['delete'],
            self.tr('Cancel')
            )
        act.triggered.connect(
            lambda: self.backend.sendto(
                dumps(
                    ['K', self.lmenu.queue.actions().index(elem.menuAction())]
                    ).encode('utf-8'),
                ('127.0.0.1', 50000)
                )
            )

    def sigEmpty(self):
        self.setIcon(_icons['free'])
        self.showMessage(self.tr('Status'), self.tr('The computer is free!'))

    def sigStart(self, target='current'):
        self.setIcon(_icons['run'])
        fromqueue = self.lmenu.queue.actions()[0]
        self.lmenu.queue.removeAction(fromqueue)
        started = fromqueue.menu()
        if target != 'current':
            started.setTitle(target + ': ' + started.title())
        started.clear()
        started.setIcon(_icons['run'])
        #TODO: Stream log file action
        started.addAction(
            _icons['delete'],
            self.tr('Cancel')
            #TODO: Removing from list after canceled
            ).triggered.connect(
                lambda: self.backend.sendto(
                    dumps(['K', target]).encode('utf-8'),
                    ('127.0.0.1', 50000)
                    )
                )
        if self.lmenu.working.isEmpty:
            self.lmenu.working.addMenu(started)
        else:
            self.lmenu.working.insertMenu(
                self.lmenu.working.actions()[0],
                started
                )
        self.lmenu.now[target] = started.menuAction()

    def sigDone(self, target):
        if not target in self.lmenu.now:
            return
        act = self.lmenu.now[target]
        self.lmenu.now.pop(target, act)
        self.lmenu.working.removeAction(act)
        menu = act.menu()
        menu.clear()
        #TODO: Open log file action
        menu.addAction(_icons['delete'], self.tr('Delete')).triggered.connect(
            lambda: self.lmenu.recent.removeAction(menu.menuAction())
            )
        self.lmenu.recent.addMenu(menu)

    def sigError(self, target):
        if not target in self.lmenu.now:
            return
        act = self.lmenu.now[target]
        self.lmenu.now.pop(target, act)
        self.lmenu.working.removeAction(act)
        menu = act.menu()
        menu.clear()
        #TODO: Open log file action
        menu.addAction(_icons['delete'], self.tr('Delete')).triggered.connect(
            lambda: self.backend.sendto(
                dumps(
                    ['K', self.lmenu.queue.actions().index(menu.menuAction())]
                    ).encode('utf-8'),
                ('127.0.0.1', 50000)
                )
            )
        self.lmenu.recent.addMenu(menu)


class Backend():

    def __init__(self):
        super(Backend, self).__init__()

        self._app = QApplication([])
        self.loadicons()
        QTextCodec.setCodecForTr(QTextCodec.codecForName("UTF-8"))
        self._tray = TrayIcon()
        self._tray.backend = self
        self._tray.setIcon(_icons['wait'])
        #TODO: make signal system lighter
        self.signals = {
            'add': self.sAdd,
            'shared': self.sLists,
            'empty': self.sState,
            'start': self.sState,
            'done': self.sLists,
            'error': self.sLists,
            }
        debug('Backend initialized')

    def loadicons(self):
        _icons['add'] = self.loadicon(icons.add_icon)
        _icons['delete'] = self.loadicon(icons.delete_icon)
        _icons['free'] = self.loadicon(icons.free_icon)
        _icons['remote'] = self.loadicon(icons.remote_icon)
        _icons['run'] = self.loadicon(icons.run_icon)
        _icons['wait'] = self.loadicon(icons.wait_icon)

    def run(self):
        pass
        self._tray.show()
        self._app.exec_()

    def loadicon(self, icon):
        p = QPixmap()
        p.loadFromData(icon)
        return QIcon(p)

    def signal(self, *signal):
        if signal[0] in self.signals:
            self.signals[signal[0]](*signal)

# Signals

    def sAdd(self, func, filename):
        self._tray.emit(
            SIGNAL('add(QString, QString)'),
            basename(filename),
            filename
            )

    def sLists(self, func, target):
        self._tray.emit(SIGNAL(func + '(QString)'), target)

    def sState(self, func):
        self._tray.emit(SIGNAL(func + '()'))
