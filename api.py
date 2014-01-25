# -*- coding: utf-8 -*-

from threading import Thread
from logging import exception


class LoggableThread(Thread):

    def __init__(self):
        super(LoggableThread, self).__init__()
        self.daemon = True
        self._alive = True
        self._real_run = self.run
        self.run = self._wrap_run

    def _wrap_run(self):
        try:
            self._real_run()
        except:
            exception('Uncaught exception was occured!')