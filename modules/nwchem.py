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

from logging import error, debug
from os.path import isfile, dirname, sep, basename
from subprocess import Popen
from os import name as osname
from socket import gethostname

if osname == 'posix':
    from os import setsid


class Module():

    def __init__(self, settings):
        if osname != 'posix':
            error("NWChem module is currently supported only on posix system")
            raise ImportError
        if not 'nwchem' in settings:
            settings['nwchem'] = dict()
            settings['nwchem']['nwchem executable file'] = ''
            settings['nwchem']['MPI executable file'] = ''
            settings['nwchem']['Visualiser executable file'] = ''
            settings['nwchem']['Addition environment variables'] = ''
        self.nwset = settings['nwchem']
        self.tmp = settings['Main']['Temporary directory']
        self.nproc = settings['Main']['Number of processors']

    def register(self, job):
        ifile = job.files['ifile']
        idir = dirname(job.files['ifile'])
        let = "f"
        job.params["prefix"] = ifile[:-2] # Prefix contains "."
        if not isfile(ifile):
            return False
        out_i = 0
        with open(ifile, 'r') as f:
            lines = f.readlines()
            for buf in lines:
                sbuf = buf.lstrip()
                if sbuf.lower().startswith('start') or sbuf.lower().startswith('restart'):
                    tokens = sbuf.split()
                    if len(tokens) == 2:
                        job.params['prefix'] = tokens[1] + "."
                elif sbuf.lower().startswith('backward'):
                    let = "b"
                elif sbuf.lower().startswith('xyz'):
                    tokens = sbuf.split()
                    if len(tokens) < 2:
                        continue
                    xyz = tokens[1]
                    if len(tokens[0]) > 3:
                        job.files['xyz_path'] = idir + sep + xyz
                    elif len(xyz) > 0:
                        job.files['xyz'] = idir + sep + xyz + "."+let+"xyz"
                    else:
                        if 'prefix' in job.params:
                            job.files['xyz'] = job.params['prefix'] +let+"xyz"
                elif sbuf.lower().startswith('output'):
                    output = sbuf[6:-1].lstrip().rstrip()
                    job.files['out'+ str(out_i)] = idir + sep + output
                    out_i += 1
                elif sbuf.lower().startswith('vectors'):
                    tokens = sbuf.split()
                    if len(tokens) == 2:
                        job.files['movecs'] = idir + sep + tokens[1]
        if not 'ofile' in job.files:
            job.files['ofile'] = job.params["prefix"] + "out"
        if not 'movecs' in job.files:
            job.files['movecs'] = job.params['prefix'] + 'movecs'
        if not 'db' in job.files:
            job.files['db'] = job.params['prefix'] + 'db'
        if not 'hess' in job.files:
            job.files['hess'] = job.params['prefix'] + 'hess'
        return job
        #TODO: add register temp files if needed

    def do(self, job):
        ifile = job.files['ifile']
        # Preparation
        # Set number of processors by default
        if not isfile(ifile):
            return Popen(['sleep', '1'], preexec_fn=setsid)
        nodes = ""
        procs = str(self.nproc)
        # Command preparation
        if 'nodelist' in job.params:
            procs = str(self.nproc + job.params['reqprocs'])
            nodes += gethostname() + ','
            for node, nproc in job.params['nodelist']:
                for i in range(0, nproc):
                    nodes += node + ','
            if len(nodes) > 0:
                nodes = '-H ' + nodes[:-1]
        # TODO: Attach self.nwset['Addition environment variables'] + ' ' +
        # CHECKME test mpi sharing
        cmd = self.nwset['MPI executable file'] +\
        ' -n ' + procs + ' ' + nodes + ' --hetero-nodes' +\
        ' ' + self.nwset['nwchem executable file'] + ' "' + ifile + '" > "' +\
        job.files['ofile'] + '"'
        debug("Executing: " + cmd)
        # Execution
        proc = Popen(
            [cmd],
            cwd=dirname(ifile),
            executable='bash',
            shell=True,
            preexec_fn=setsid
            )
        return proc
