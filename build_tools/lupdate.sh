#!/bin/bash

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