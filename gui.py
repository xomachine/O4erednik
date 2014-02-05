# -*- coding: utf-8 -*-

from PyQt4.QtGui import QApplication, QSystemTrayIcon, QIcon, QPixmap, QMenu
from PyQt4.QtGui import QCursor, QFileDialog, QDialog, QWidget, QGroupBox
from PyQt4.QtGui import QVBoxLayout, QIntValidator, QScrollArea
from PyQt4.uic import loadUi
from PyQt4.QtCore import QTextCodec, SIGNAL
from os import _exit
from os.path import basename, dirname
from json import dumps
from subprocess import Popen
import icons

_icons = dict()


class SettingsDialog(QDialog):

    def __init__(self, backend):
        super(SettingsDialog, self).__init__()
        self.backend = backend
        loadUi('GUI/settings_form.ui', self)

        self.buildUp()

    def buildUp(self):
        for sect in list(self.backend.shared.settings.keys()):
            scroll = QScrollArea(self.tabWidget)
            widget = QWidget(self.tabWidget)
            layout = QVBoxLayout(widget)
            for key, value in list(self.backend.shared.settings[sect].items()):
                if not type(key) is str:
                    continue
                groupbox = QGroupBox(widget)
                loadUi('GUI/settings_element.ui', groupbox)
                if type(value) is str:
                    groupbox.comboBox.lineEdit().setText(value)
                    if key.endswith('directory'):
                        groupbox.toolButton.clicked.connect(
                            lambda y, x=groupbox.comboBox.lineEdit(): x.setText(
                                QFileDialog.getExistingDirectory(
                                    self,
                                    self.tr('Select path'),
                                    options=QFileDialog.DontUseNativeDialog |
                                    QFileDialog.ShowDirsOnly
                                    )
                                )
                            )
                    elif key.endswith('file'):
                        groupbox.toolButton.clicked.connect(
                            lambda y, x=groupbox.comboBox.lineEdit(): x.setText(
                                QFileDialog.getOpenFileName(
                                    self,
                                    self.tr('Select file'),
                                    filter=self.tr('All files(*)'),
                                    options=QFileDialog.DontUseNativeDialog
                                    )
                                )
                            )
                    else:
                        groupbox.toolButton.setShown(False)
                    self.saveButton.clicked.connect(
                        lambda x, y=key, z=groupbox.comboBox, s=sect:
                            self.backend.shared.settings[s].update({y:
                            z.lineEdit().text()}
                            )
                        )
                elif type(value) is int:
                    groupbox.toolButton.setShown(False)
                    groupbox.comboBox.lineEdit().setValidator(
                        QIntValidator(groupbox))
                    groupbox.comboBox.lineEdit().setText(str(value))
                    self.saveButton.clicked.connect(
                        lambda x, y=key, z=groupbox.comboBox.lineEdit(), s=sect:
                            self.backend.shared.settings[s].update(
                                {y: int(z.text())}
                            )
                        )
                elif type(value) is bool:
                    groupbox.comboBox.setShown(False)
                    groupbox.toolButton.setShown(False)
                    groupbox.setCheckable(True)
                    groupbox.setChecked(value)
                    self.saveButton.clicked.connect(
                        lambda x, y=key, z=groupbox.isChecked, s=sect:
                            self.backend.shared.settings[s].update({y:
                            z()}
                            )
                        )
                elif type(value) is list:
                    groupbox.toolButton.setShown(False)
                    for item in self.backend.shared.settings[sect][tuple(key)](
                        ):
                        groupbox.comboBox.addItem(item[1])
                    groupbox.comboBox.lineEdit().setText(value[0])
                    self.saveButton.clicked.connect(
                        lambda x, y=key, z=groupbox.comboBox, s=sect:
                            self.backend.shared.settings[s].update({y:
                            [z.lineEdit().text()]}
                            )
                        )
                else:
                    groupbox.lineEdit.setText('Incorrect value')
                    groupbox.lineEdit.Enable(False)
                groupbox.setTitle(self.tr(key))
                layout.addWidget(groupbox)

            if sect == 'Main':
                self.tabWidget.insertTab(0, scroll, self.tr(sect))
            else:
                self.tabWidget.addTab(scroll, self.tr(sect))
            scroll.setWidget(widget)
        self.tabWidget.setCurrentIndex(0)
        self.saveButton.clicked.connect(
                        lambda: self.backend.shared.save() or
                        self.backend.shared.load()
                        )


class LeftMenu(QMenu):

    def __init__(self, backend):
        super(LeftMenu, self).__init__()
        self.now = dict()
        self.backend = backend
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
        types = 'Select assignment type'
        for sect in list(self.backend.shared.settings.keys()):
            if sect == 'Main':
                continue
            types += ';;' + sect + '(*.*)'
        filename, jtype = QFileDialog.getOpenFileNameAndFilter(
            None,
            self.tr('Open file'),
            filter=types,
            initialFilter='Select assignment type',
            options=QFileDialog.DontUseNativeDialog
            )
        if filename:
            self.lastpath = dirname(filename)
            self.backend.sendto(
                dumps(['A', [jtype[:-5], 0, {"ifile": filename}, {}]])
                )


class RightMenu(QMenu):

    def __init__(self, backend):
        super(RightMenu, self).__init__()
        self.backend = backend
        self.sdialog = SettingsDialog(backend)
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

        self.sdialog.exec_()


class TrayIcon(QSystemTrayIcon):

    def __init__(self, backend):
        super(TrayIcon, self).__init__()
        self.backend = backend
        # Create right and left click menus
        self.rmenu = RightMenu(backend)
        self.lmenu = LeftMenu(backend)
        self.settings = self.backend.shared.settings

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
        self.connect(
            self,
            SIGNAL('start(QString, QString, QString)'),
            self.sStart
            )
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
                    )
                )
            )

    def sEmpty(self):
        self.setIcon(_icons['free'])
        self.showMessage(self.tr('Status'), self.tr('The computer is free!'))

    def sStart(self, target, ofile, jtype):
        self.setIcon(_icons['run'])
        fromqueue = self.lmenu.queue.actions()[0]
        self.lmenu.queue.removeAction(fromqueue)
        started = fromqueue.menu()
        if target != 'current':
            started.setTitle(target + ': ' + started.title())
        started.setIcon(_icons['run'])

        started.actions()[0].triggered.disconnect()
        started.actions()[0].triggered.connect(
                lambda: self.backend.sendto(
                    dumps(['K', target])
                    )
                )
        if 'Visualiser executable file' in self.settings[jtype]:
                started.addAction(
                    _icons['run'],
                    self.tr('Open in visualiser')
                    ).triggered.connect(
                        lambda: Popen([
                            self.settings[jtype]['Visualiser executable file'],
                            ofile
                            ])
                        )
        started.addAction(
            _icons['run'],
            self.tr('Open in text editor')
            ).triggered.connect(
                lambda: Popen([
                    self.settings['Main']['Text editor executable file'],
                    ofile
                    ])
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
        if mode == 'error':
            self.sAdd(menu.title(), menu.toolTip())
        else:
            self.showMessage(
                self.tr('Assignment completed'),
                self.tr('The assignment') +
                menu.title() + self.tr(' is completed!')
                )
            delaction = menu.actions()[0]
            delaction.triggered.disconnect()
            delaction.setText(self.tr('Delete'))
            delaction.triggered.connect(
                    lambda: self.lmenu.recent.removeAction(menu.menuAction())
                    )
            self.lmenu.recent.addMenu(menu)


###############################################################################
# Backend
###############################################################################
class Backend():

    def __init__(self, shared):
        super(Backend, self).__init__()
        self.shared = shared
        self.sendto = lambda x: shared.udpsocket.sendto(
            x.encode('utf-8'),
            ('127.0.0.1', 50000)
            )
        self._app = QApplication([])
        self._app.setQuitOnLastWindowClosed(False)
        self.loadicons()
        QTextCodec.setCodecForTr(QTextCodec.codecForName("UTF-8"))
        self._tray = TrayIcon(self)
        self._tray.setIcon(_icons['wait'])
        self.signals = {
            'add': self.sAdd,
            'empty': lambda x: self._tray.emit(SIGNAL('empty()')),
            'start': self.sStart,
            'error': self.sDone,
            'done': self.sDone,
            }

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

    def sStart(self, func, ofile, jtype, target='current'):
        self._tray.emit(
            SIGNAL('start(QString, QString, QString)'),
            target,
            ofile,
            jtype
            )
