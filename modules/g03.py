# -*- coding: utf-8 -*-
from os.path import isdir, isfile, dirname
from os import setsid, environ
from subprocess import Popen
name = 'g03'

# Gaussian 03 worker


class Module():

    def __init__(self, settings):
        if not 'g03exe' in settings:
            settings['g03exe'] = ''
        environ['g03root'] = dirname(dirname(settings['g03exe']))
        environ['GAUSS_EXEDIR'] = dirname(settings['g03exe'])
        environ['GAUSS_SCRDIR'] = settings['tmp']
        self.settings = settings

    def register(self, job):
        ifile = job.files['ifile']
        if not isfile(ifile):
            return False
        if not 'ofile' in job.files:
            job.files['ofile'] = ifile[:-3] + "log"
        with open(ifile, 'r') as f:
            lines = f.readlines()
            chknum = 0
            for buf in lines:
                if buf.startswith('%chk'):
                    cur = buf[5:-1]
                    if isdir(cur) or not isdir(dirname(cur)):
                        cur = ifile[:-3] + "chk"
                    job.files['chkfile' + str(chknum)] = cur
                    chknum += 1
        return job

    def do(self, job):
        ifile = job.files['ifile']
        # Preparation
        wlines = ["%nprocshared=" + str(self.settings['nproc']) + "\n"]
        # Set number of processors by default
        with open(ifile, 'r') as f:
            lines = f.readlines()
            chknum = 0
            for buf in lines:
                if buf.startswith('%lindaworkers'):
                    buf = "%lindaworkers=\n"
                    #TODO: linda support
                elif buf.startswith('%nprocshared'):
                    buf = '%nprocshared=' + str(self.settings['nproc']) + "\n"
                    # Overwrite number of processors and remove default
                    # as annessesery
                    wlines[0] = ""
                elif buf.startswith('%chk'):
                    buf = "%chk=" + job.files['chkfile' + str(chknum)] + "\n"
                    chknum += 1
                wlines.append(buf)
        with open(ifile, 'w') as f:
            for buf in wlines:
                f.write(buf)
        # Execution
        proc = Popen(
            [self.settings['g03exe'], ifile],
            cwd=dirname(ifile),
            preexec_fn=setsid
            )
        return proc
