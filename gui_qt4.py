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


from PyQt4.QtGui import QApplication, QSystemTrayIcon, QIcon, QPixmap, QMenu
from PyQt4.QtGui import QCursor, QFileDialog, QDialog, QWidget, QGroupBox
from PyQt4.QtGui import QVBoxLayout, QIntValidator, QScrollArea, QInputDialog
from PyQt4.uic import loadUi
from PyQt4.QtCore import QTextCodec, SIGNAL, QTranslator, QLocale
from os import sep
from os.path import basename, dirname
from json import dumps
from subprocess import Popen
from time import strftime
import icons
from logging import debug

_icons = dict()


class SettingsDialog(QDialog):

    def __init__(self, backend):
        super(SettingsDialog, self).__init__()
        self.backend = backend
        loadUi('GUI' + sep + 'settings_form.ui', self)
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
                loadUi('GUI' + sep + 'settings_element.ui', groupbox)
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
                    for item in self.backend.shared.settings[sect][tuple(key)]:
                        groupbox.comboBox.addItem(str(item))
                    groupbox.comboBox.lineEdit().setText(value[0])
                    self.saveButton.clicked.connect(
                        lambda x, y=key, z=groupbox.comboBox, s=sect:
                            self.backend.shared.settings[s].update({y:
                            [z.lineEdit().text()]}
                            )
                        )
                else:
                    groupbox.toolButton.setShown(False)
                    groupbox.lineEdit.setText(self.tr('Incorrect value'))
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
            self.tr('Add job')
            ).triggered.connect(self.DoAdd)

        clact = self.addAction(
            _icons['delete'],
            self.tr('Clear recent')
            )

        self.addSeparator()

        self.working = self.addMenu(
            _icons['run'],
            self.tr('In process:')
            )

        self.queue = self.addMenu(
            _icons['wait'],
            self.tr('Queue:')
            )

        self.recent = self.addMenu(
            _icons['free'],
            self.tr('Recent:')
            )

        clact.triggered.connect(self.recent.clear)

    def DoAdd(self):

        types = self.tr('Select job type')
        for sect in list(self.backend.shared.settings.keys()):
            if sect == 'Main':
                continue
            types += ';;' + sect + '(*.*)'
        filename, jtype = QFileDialog.getOpenFileNameAndFilter(
            self,
            self.tr('Select job'),
            filter=types,
#            options=QFileDialog.DontUseNativeDialog
            # Not sure whether it nessesary
            )
        if filename:
            self.lastpath = dirname(filename)
            # There will be procs request
            numproc, ok = QInputDialog. getInteger(self,
                self.tr("How many processors required to job?"),
                self.tr("Number of processors (0 - default):"),
                0,
                0)
            if (ok is False):
                numproc = 0
            self.backend.sendto(
                dumps(['A', [jtype[:-5], {"ifile": filename}, {'reqprocs': int(numproc)}]])
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
        self.backend.sendto(
                dumps(['E', None])
                )

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
            SIGNAL('start(QString, QString, QString, QString)'),
            self.sStart
            )
        self.connect(self, SIGNAL('done(QString, QString)'), self.sDone)

# Signal handlers

    def sAdd(self, name, tooltip):
        elem = self.lmenu.queue.addMenu(_icons['wait'], name)
        elem.setToolTip(tooltip)
        elem.addAction(_icons['delete'], self.tr('Cancel')).triggered.connect(
            lambda: self.backend.sendto(
                dumps(
                    ['K', self.lmenu.queue.actions().index(elem.menuAction())]
                    )
                )
            )

    def sEmpty(self):
        self.setIcon(_icons['free'])
        self.showMessage(
            self.tr('Status'),
            self.tr('The computer is free!'))

    def sStart(self, target, ofile, jtype, uid):
        debug("Setting icon")
        self.setIcon(_icons['run'])
        debug("Extracting from queue")
        fromqueue = self.lmenu.queue.actions()[0]
        self.lmenu.queue.removeAction(fromqueue)
        started = fromqueue.menu()
        if len(target) != 0:
            started.setTitle(target + ':>' + started.title())
        started.setIcon(_icons['run'])
        debug("Extracted with name:" + started.title())
        started.actions()[0].triggered.disconnect()
        started.actions()[0].triggered.connect(
                lambda: self.backend.sendto(
                    dumps(['K', uid])
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
        debug("Inserting to 'In process'")
        if self.lmenu.working.isEmpty:
            self.lmenu.working.addMenu(started)
        else:
            self.lmenu.working.insertMenu(
                self.lmenu.working.actions()[0],
                started
                )
        debug("Recording to array, now array contains:")
        self.lmenu.now[uid] = started.menuAction()
        debug(str(self.lmenu.now))

    def sDone(self, mode, uid):
        debug('GUI done signal mode:' + mode + '; id:' + uid)
        if uid[0] == 'i':
            uid = int(uid[1:])
            debug("Job in queue, removing...")
            self.lmenu.queue.removeAction(
                self.lmenu.queue.actions()[uid]
                )
            return
        if not uid in self.lmenu.now:
            debug("Id '" + str(uid) + "' is not in menu.")
            return
        debug("Extracting '" + str(uid) + "' from 'In process'")
        act = self.lmenu.now[uid]
        self.lmenu.now.pop(uid, act)
        self.lmenu.working.removeAction(act)
        debug("Now array contains:")
        debug(str(self.lmenu.now))
        menu = act.menu()
        if mode == 'error':
            debug('Turning "' + act.title() + '" back to queue')
            self.sAdd(menu.title().split(':>', 1)[-1], menu.toolTip())
            debug(act.title() + ' successfuly added to queue')
        else:
            debug("Pushing job to Recent")
            self.showMessage(self.tr('Job completed!'),
                self.tr('Job for ') + menu.title() + self.tr(' completed!'))
            menu.setTitle(strftime("[%x %X] ") + menu.title())
            delaction = menu.actions()[0]
            delaction.triggered.disconnect()
            delaction.setText(self.tr('Delete'))
            delaction.triggered.connect(
                    lambda: self.lmenu.recent.removeAction(menu.menuAction())
                    )
            self.lmenu.recent.addMenu(menu)
            debug("Job now in Recent")


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
        translator = QTranslator(self._app)
        self._app.setQuitOnLastWindowClosed(False)
        translator.load(
            QLocale.system(), 'lang', '.', shared.path + sep + 'langs')
        self._app.installTranslator(translator)
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
        for job in self.shared.queue:
            self.sAdd("add", job)
        self._app.exec_()
        

    def loadicon(self, icon):
        p = QPixmap()
        p.loadFromData(icon)
        return QIcon(p)

    def signal(self, *signal):
        if signal[0] in self.signals:
            self.signals[signal[0]](*signal)

# Signals

    def sAdd(self, func, job):
        self._tray.emit(
            SIGNAL('add(QString, QString)'),
            basename(job.files['ifile']),
            job.files['ifile']
            )

    def sDone(self, func, uid):
        if type(uid) is int:
            uid = 'i' + str(uid)
        self._tray.emit(
            SIGNAL('done(QString, QString)'), func, str(uid))

    def sStart(self, func, job, target=None):
        self._tray.emit(
            SIGNAL('start(QString, QString, QString, QString)'),
            target,
            job.files["ofile"],
            job.type,
            str(job.id))
