# -*- coding: utf-8 -*-

from os import listdir
from os.path import dirname

__all__ = [f[:-3] for f in listdir(dirname(__file__)) if f.endswith('.py')]