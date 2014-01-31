# -*- coding: utf-8 -*-

from PyQt4.QtGui import QApplication, QSystemTrayIcon, QIcon, QPixmap, QMenu
from PyQt4.QtGui import QCursor, QToolTip
from PyQt4.QtCore import QTextCodec, SIGNAL
from os import _exit
from logging import debug
import icons

_icons = dict()


class LeftMenu(QMenu):

    def __init__(self):
        super(LeftMenu, self).__init__()

        # Fill elements of menu
        self.addAction(
            _icons['add'],
            self.tr('Add assignment')
            ).triggered.connect(self.DoAdd)

        self.addSeparator()

        self.local = self.addMenu(
            _icons['run'],
            self.tr('Local assignments')
            )
        self.remote = self.addMenu(
            _icons['remote'],
            self.tr('Remote assignments')
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
        self.connect(self, SIGNAL('add(QString, QString)'), self.SigAdd)

    def DoActivate(self, reason):
        if reason == self.Trigger:
            self.lmenu.exec_(QCursor.pos())

    def SigAdd(self, name, tooltip):
        elem = self.lmenu.local.addMenu(_icons['wait'], name)
        elem.setToolTip(tooltip)
        elem.enterEvent = lambda x: QToolTip.showText(QCursor.pos(), name)
        elem.leaveEvent = lambda x: QToolTip.hideText()


class Backend():

    def __init__(self):
        super(Backend, self).__init__()

        self._app = QApplication([])
        self.loadicons()
        QTextCodec.setCodecForTr(QTextCodec.codecForName("UTF-8"))
        self._tray = TrayIcon()
        self._tray.setIcon(_icons['wait'])

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
        self._tray.emit(
            SIGNAL('add(QString, QString)'),
            'testname',
            'testtooltip')
