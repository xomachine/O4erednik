#!/bin/bash
#Script to build queuer executable

nuitka --exe --recurse-all --recurse-directory=/usr/lib/python3.3/site-packages/PyQt4 \
--show-progress -j 3 --lto --python-version=3.3 --improved --output-dir=./linux_$(uname -m) \
--remove-output ./__init__.py
 
