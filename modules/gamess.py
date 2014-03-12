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

from logging import error
from os.path import isfile, dirname, basename
from subprocess import Popen
from os import setsid, environ, makedirs
from shutil import copyfile


class Module():

    def __init__(self, settings):
        if not 'gamess' in settings:
            settings['gamess'] = dict()
            self.settings['gamess']['GAMESS executable file'] = ''
            self.settings['gamess']['Kickoff executable file'] = ''
            self.settings['gamess']['Visualiser executable file'] = ''
            self.settings['gamess']['Kickoff type'] = ['socket']
        self.gmsset = settings['gamess']
        self.gmsset[tuple('Kickoff type')] = ['socket', 'mpi']
        self.tmp = settings['Main']['Temporary directory']
        self.nproc = str(settings['Main']['Number of processors'])
        self.gmspath = dirname(self.gmsset['GAMESS executable file'])
        with open('/proc/sys/kernel/shmmax', 'r') as f:
            if int(f.read()) < 44498944:
                error('''GAMESS jobs will not be executed!
Please set kernel.shmmax>=44498944 and restart me!
E.g.: sudo sysctl -w kernel.shmmax=6269961216''')
                raise
        environ['GMSPATH'] = self.gmspath
        environ['SCR'] = self.tmp

    def register(self, job):
        ifile = job.files['ifile']
        if not isfile(ifile):
            return False
        if not 'ofile' in job.files:
            job.files['ofile'] = ifile[:-3] + "log"
        job.files['punch'] = ifile[:-3] + "dat"
        job.files['traject'] = ifile[:-3] + "trj"
        job.files['restart'] = ifile[:-3] + "rst"
        job.files['makefp'] = ifile[:-3] + "efp"
        return job

    def do(self, job):
        ifile = job.files['ifile']
        # Preparation
        # Set number of processors by default
        if not isfile(ifile):
            return Popen(['sleep', '1'], preexec_fn=setsid)
        usrscr = dirname(ifile) + '/scr'
        makedirs(usrscr, exist_ok=True)
        copyfile(ifile, self.tmp + '/' + basename(ifile)[:-3] + 'F05')
        environ['USERSCR'] = usrscr
        environ['JOB'] = basename(ifile)[:-4]
        nodes = ""
        # Command preparation
        if self.gmsset['Kickoff type'] == ['socket']:
            nnodes = 1
            if 'nodelist' in job.params:
                for node, nproc in job.params['nodelist']:
                    nnodes += 1
                    nodes += node + ':cpus=' + nproc
            cmd = 'source ' + self.gmspath + '/gms-files.csh; ' +\
            self.gmsset['Kickoff executable file'] + ' ' +\
            self.gmsset['GAMESS executable file'] + ' ' + ifile + ' -ddi ' +\
            nnodes + ' ' + self.nproc + ' ' + nodes + ' -scr ' + self.tmp +\
            ' > ' + job.files['ofile']
        elif self.gmsset['Kickoff type'] == ['mpi']:
            if 'nodelist' in job.params:
                for node, nproc in job.params['nodelist']:
                    for i in range(0, nproc):
                        nodes += node + ','
                if len(nodes) > 0:
                    nodes = '-H ' + nodes[:-1] + ' '
            cmd = 'source ' + self.gmspath + '/gms-files.csh; ' +\
            self.gmsset['Kickoff executable file'] + ' -n ' +\
            self.nproc + ' ' + nodes +\
            self.gmsset['GAMESS executable file'] + ' > ' +\
            job.files['ofile']
        # Execution
        proc = Popen(
            [cmd],
            cwd=dirname(ifile),
            executable='csh',
            shell=True,
            preexec_fn=setsid
            )
        return proc
