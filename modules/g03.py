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


from os.path import isdir, isfile, dirname
from os import setsid, environ
from subprocess import Popen

# Gaussian 03 worker


class Module():

    def __init__(self, settings):
        if not 'g03' in settings:
            settings['g03'] = dict()
            settings['g03']['G03 executable file'] = ''
            settings['g03']['Visualiser executable file'] = ''
        self.g03set = settings['g03']
        self.nproc = str(settings['Main']['Number of processors'])
        environ['g03root'] = dirname(
            dirname(settings['g03']['G03 executable file']))
        environ['GAUSS_EXEDIR'] = dirname(
            settings['g03']['G03 executable file'])
        environ['GAUSS_SCRDIR'] = settings['Main']['Temporary directory']

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
                elif buf.startswith('%lindaworkers'):
                    ls = buf[14:-1].split(',')
                    job.params['reqprocs'] = 0
                    for i in ls:
                        job.params['reqprocs'] += int(i.split(':')[1])
                    #TODO: test linda support
        return job

    def do(self, job):
        ifile = job.files['ifile']
        # Preparation
        wlines = ["%nprocshared=" + self.nproc + "\n"]
        # Set number of processors by default
        if not isfile(ifile):
            return Popen(['sleep', '1'], preexec_fn=setsid)
        with open(ifile, 'r') as f:
            lines = f.readlines()
            chknum = 0
            for buf in lines:
                if buf.startswith('%lindaworkers'):
                    buf = "%lindaworkers="
                    for i in job.params['nodelist']:
                        buf += i[0] + ':' + i[1] + ','
                    buf = buf[:-1] + "\n"
                    #TODO: test linda support
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
            [self.g03set['G03 executable file'], ifile],
            cwd=dirname(ifile),
            preexec_fn=setsid
            )
        return proc
