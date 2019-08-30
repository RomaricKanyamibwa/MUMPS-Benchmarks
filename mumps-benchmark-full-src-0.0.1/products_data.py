# coding=utf-8
# --------------------------------------------------------------------
# Copyright (C) 1991 - 2017 - EDF R&D - www.code-aster.org
# This file is part of code_aster.
#
# code_aster is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# code_aster is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with code_aster.  If not, see <http://www.gnu.org/licenses/>.
# --------------------------------------------------------------------

"""
This module defines some datas/scripts missing in upstream packages
"""

_bash_header_template = """#!/bin/bash

# --------------------------------------------------------------------
# Copyright (C) 1991 - 2017 - EDF R&D - www.code-aster.org
# This file is part of code_aster.
#
# code_aster is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# code_aster is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with code_aster.  If not, see <http://www.gnu.org/licenses/>.
# --------------------------------------------------------------------

set_prefix() {
   local this=`readlink -n -f $1`
   parent=`dirname $this`
   prefix=`dirname $parent`
}

set_prefix $0

# set environment
if [ -f /etc/codeaster/profile.sh ]; then
   . /etc/codeaster/profile.sh
fi
if [ -f $prefix/etc/codeaster/profile.sh ]; then
   . $prefix/etc/codeaster/profile.sh
fi

# start Python interpreter
if [ -z "$PYTHONEXECUTABLE" ]; then
   PYTHONEXECUTABLE=python
fi

"""


import sys
waf_template_addon = ""
if sys.platform != 'darwin':
    # --allow-multiple-definition not supported in OS X linker
    waf_template_addon = """
    # sometimes required
    self.env.append_unique('LINKFLAGS', ['-Wl,--allow-multiple-definition'])
"""

waf_template = """# coding=utf-8

'''Configuration for waf using aster-full prerequisites'''

import os
import os.path as osp
import sys

def configure(self):
    opts = self.options
    if %(OPT_ENV)r.strip():
        self.env.append_value('OPT_ENV', %(OPT_ENV)r.splitlines())

    self.env['FC'] = %(F90)r
    self.env['CC'] = %(CC)r
    # mfront path
    self.env.TFELHOME = '%(HOME_MFRONT)s'
    # to check med libs
    self.env['CXX'] = %(CXX)r
""" + waf_template_addon + """
    self.env.append_value('LIBPATH', [
        '%(HOME_HDF)s/lib',
        '%(HOME_MED)s/lib',
        '%(HOME_MUMPS)s/lib',
        '%(HOME_METIS)s/lib',
        '%(HOME_MFRONT)s/lib',
        '%(HOME_SCOTCH)s/lib',
        # autotools uses lib64 on some platforms
        '%(HOME_HDF)s/lib64',
        '%(HOME_MED)s/lib64',
    ])

    self.env.append_value('INCLUDES', [
        '%(HOME_HDF)s/include',
        '%(HOME_MED)s/include',
        '%(HOME_MUMPS)s/include',
        '%(HOME_MUMPS)s/include_seq',
        '%(HOME_METIS)s/include',
        '%(HOME_SCOTCH)s/include',
        '%(HOME_MFRONT)s/include',
    ])

    self.env['OPTLIB_FLAGS'] = %(MATHLIB)r.split() \
        + %(OTHERLIB)r.split()
    opts.maths_libs = ''

    opts.enable_petsc = False

    # add paths for external programs
    os.environ['METISDIR'] = '%(HOME_METIS)s'
    os.environ['GMSH_BIN_DIR'] = '%(HOME_GMSH)s/bin'
    os.environ['HOMARD_ASTER_ROOT_DIR'] = '%(HOME_HOMARD)s'

"""

mfront_env_template = """
# Environment for MFront needed to build code_aster from sources

HOME_MFRONT=%(HOME_MFRONT)s

if [ -z "${PATH}" ]; then
    export PATH=${HOME_MFRONT}/bin
else
    export PATH=${HOME_MFRONT}/bin:${PATH}
fi

if [ -z "${LD_LIBRARY_PATH}" ]; then
    export LD_LIBRARY_PATH=${HOME_MFRONT}/lib
else
    export LD_LIBRARY_PATH=${HOME_MFRONT}/lib:${LD_LIBRARY_PATH}
fi

if [ -z "${PYTHONPATH}" ]; then
    export PYTHONPATH=${HOME_MFRONT}/lib/python2.7/site-packages
else
    export PYTHONPATH=${HOME_MFRONT}/lib/python2.7/site-packages:${PYTHONPATH}
fi
"""

def shell_escape(script):
    """Escape special characters for shell scripts."""
    dtr = {
        '$' : r'\$',
        '`' : r'\`',
    }
    for str, repl in dtr.items():
        script = script.replace(str, repl)
    return script
