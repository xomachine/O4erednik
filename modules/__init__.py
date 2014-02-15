# -*- coding: utf-8 -*-

#     This file is part of O4erednik.
#
#     O4erednik is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License or
#     (at your option) any later version.
#
#     Foobar is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with Foobar.  If not, see <http://www.gnu.org/licenses/>.
#
#     Copyright 2014 Fomichev Dmitriy

from os import listdir
from os.path import dirname

__all__ = [f[:-3] for f in listdir(dirname(__file__)) if f.endswith('.py')]