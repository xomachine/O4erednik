# -*- coding: utf-8 -*-

from PyQt4.QtGui import QApplication, QSystemTrayIcon, QIcon, QPixmap, QMenu
from PyQt4.QtGui import QCursor
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

        self.addAction(
            _icons['remote'],
            self.tr('Settings')
            ).triggered.connect(self.DoSetup)

        self.addAction(
            _icons['delete'],
            self.tr('Exit')
            ).triggered.connect(self.DoExit)

    def DoExit(self):
        _exit(0)

    def DoSetup(self):
        #TODO: Settings
        pass


class TrayIcon(QSystemTrayIcon):

    def __init__(self):
        super(TrayIcon, self).__init__()

        # Create right and left click menus
        self.rmenu = RightMenu()
        self.lmenu = LeftMenu()

        self.setContextMenu(self.rmenu)
        self.activated.connect(
            lambda x: self.lmenu.exec_(QCursor.pos())
            if x == self.Trigger
            else False
            )

        # Connect signals
        # self.connect(self, SIGNAL(), self.signalhandler)
        self.connect(self, SIGNAL('add(QString, QString)'), self.sAdd)
        self.connect(self, SIGNAL('empty()'), self.sEmpty)
        self.connect(self, SIGNAL('start(QString)'), self.sStart)
        self.connect(self, SIGNAL('done(QString, QString)'), self.sDone)

# Signal handlers

    def sAdd(self, name, tooltip):
        elem = self.lmenu.queue.addMenu(_icons['wait'], name)
        elem.setToolTip(tooltip)
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

    def sEmpty(self):
        self.setIcon(_icons['free'])
        self.showMessage(self.tr('Status'), self.tr('The computer is free!'))

    def sStart(self, target='current'):
        self.setIcon(_icons['run'])
        fromqueue = self.lmenu.queue.actions()[0]
        self.lmenu.queue.removeAction(fromqueue)
        started = fromqueue.menu()
        if target != 'current':
            started.setTitle(target + ': ' + started.title())
        started.setIcon(_icons['run'])
        #TODO: Stream log file action
        started.actions()[0].triggered.disconnect()
        started.actions()[0].triggered.connect(
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

    def sDone(self, target, mode):
        if target.isdigit():
            self.lmenu.queue.removeAction(
                self.lmenu.queue.actions()[int(target)]
                )
        if not target in self.lmenu.now:
            return
        act = self.lmenu.now[target]
        self.lmenu.now.pop(target, act)
        self.lmenu.working.removeAction(act)
        menu = act.menu()
        menu.clear()
        if mode == 'error':
            self.sAdd(menu.title(), menu.toolTip())
        else:
            self.showMessage(
                self.tr('Assignment completed'),
                self.tr('The assignment') +
                menu.title() + self.tr(' is completed!')
                )
            #TODO: Open log file action
            menu.addAction(
                _icons['delete'],
                self.tr('Delete')
                ).triggered.connect(
                    lambda: self.lmenu.recent.removeAction(menu.menuAction())
                    )
            self.lmenu.recent.addMenu(menu)


###############################################################################
# Backend
###############################################################################
class Backend():

    def __init__(self, settings):
        super(Backend, self).__init__()
        self.settings = settings

        self._app = QApplication([])
        self.loadicons()
        QTextCodec.setCodecForTr(QTextCodec.codecForName("UTF-8"))
        self._tray = TrayIcon()
        self._tray.backend = self
        self._tray.setIcon(_icons['wait'])
        self.signals = {
            'add': self.sAdd,
            'empty': lambda x: self._tray.emit(SIGNAL('empty()')),
            'start': self.sStart,
            'error': self.sDone,
            'done': self.sDone,
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

    def sDone(self, func, target):
        self._tray.emit(SIGNAL('done(QString, QString)'), target, func)

    def sStart(self, func, target='current'):
        self._tray.emit(SIGNAL('start(QString)'), target)
