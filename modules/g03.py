# -*- coding: utf-8 -*-
from os.path import isdir, isfile, dirname
from os import setsid, environ
from subprocess import Popen

# Gaussian 03 worker


class Module():

    def __init__(self, settings):
        if not settings.has_section('g03'):
            settings.add_section('g03')
            settings['g03']['g03exe'] = ''
            settings['g03']['g03vis'] = ''
        self.g03set = settings['g03']
        self.nproc = settings['Main']['nproc']
        environ['g03root'] = dirname(dirname(settings['g03']['g03exe']))
        environ['GAUSS_EXEDIR'] = dirname(settings['g03']['g03exe'])
        environ['GAUSS_SCRDIR'] = settings['Main']['tmp']

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
        wlines = ["%nprocshared=" + self.nproc + "\n"]
        # Set number of processors by default
        with open(ifile, 'r') as f:
            lines = f.readlines()
            chknum = 0
            for buf in lines:
                if buf.startswith('%lindaworkers'):
                    buf = "%lindaworkers=\n"
                    #TODO: linda support
                elif buf.startswith('%nprocshared'):
                    buf = '%nprocshared=' + self.nproc + "\n"
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
            [self.g03set['g03exe'], ifile],
            cwd=dirname(ifile),
            preexec_fn=setsid
            )
        return proc
