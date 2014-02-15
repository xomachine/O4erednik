#!/bin/bash

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

cd ..
CWD=$(pwd)
mkdir -p $CWD/translations
for file in $(ls modules | grep '\.py$')
do
    echo "Processing $CWD/modules/$file"
    sed -e 's/settings\[\(.*\)\]\[\(.*\)\]/settings\[QT_TRANSLATE_NOOP("SettingsDialog", \1)\]\[QT_TRANSLATE_NOOP("SettingsDialog", \2)\]/g' $CWD/modules/$file > $CWD/translations/$file
done
for file in $(ls | grep '\.py$')
do
    echo "Processing $CWD/$file"
    sed -e 's/settings\[\(.*\)\]\[\(.*\)\]/settings\[QT_TRANSLATE_NOOP("SettingsDialog", \1)\]\[QT_TRANSLATE_NOOP("SettingsDialog", \2)\]/g' $CWD/$file>> $CWD/translations/$file
done
pylupdate4 -verbose -noobsolete $CWD/translations/* $CWD/GUI/* -ts lang.ts
rm -rf $CWD/translations