#!/usr/bin/python3
from cx_Freeze import setup, Executable
from sys import platform
from os.path import realpath, dirname

selfpath = dirname(realpath(__file__))
if platform == 'win32':
    slash = '\\'
    exename = 'queuer.exe'
    basename = 'Win32GUI'
else:
    slash = '/'
    exename = 'queuer'
    basename = None
exe = Executable(selfpath + slash + 'queuer.py', targetName=exename, base=basename, compress = True)
build_opts = dict(
        compressed = True,
        optimize = 2
        )
options = {"build_exe" : build_opts }
setup(name = "O4erednik",
     version = "1.0",
     description = "Queue for Gaussian",
     options = options,
     executables = [exe],
    ) 
