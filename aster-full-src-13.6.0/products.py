# -*- coding: utf-8 -*-
# ==============================================================================
# COPYRIGHT (C) 1991 - 2003  EDF R&D                  WWW.CODE-ASTER.ORG
# THIS PROGRAM IS FREE SOFTWARE; YOU CAN REDISTRIBUTE IT AND/OR MODIFY
# IT UNDER THE TERMS OF THE GNU GENERAL PUBLIC LICENSE AS PUBLISHED BY
# THE FREE SOFTWARE FOUNDATION; EITHER VERSION 2 OF THE LICENSE, OR
# (AT YOUR OPTION) ANY LATER VERSION.
#
# THIS PROGRAM IS DISTRIBUTED IN THE HOPE THAT IT WILL BE USEFUL, BUT
# WITHOUT ANY WARRANTY; WITHOUT EVEN THE IMPLIED WARRANTY OF
# MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE. SEE THE GNU
# GENERAL PUBLIC LICENSE FOR MORE DETAILS.
#
# YOU SHOULD HAVE RECEIVED A COPY OF THE GNU GENERAL PUBLIC LICENSE
# ALONG WITH THIS PROGRAM; IF NOT, WRITE TO EDF R&D CODE_ASTER,
#    1 AVENUE DU GENERAL DE GAULLE, 92141 CLAMART CEDEX, FRANCE.
# ==============================================================================

"""This module defines SETUP instances for each products.

Functions are named : setup_`product`,
and have two main arguments : DEPENDENCIES and SUMMARY objects,
and additionnal arguments through 'kargs'.
"""

# Of course the order is not important... but it's easier to understand
# dependencies in the right order !

import sys
import os
import os.path as osp
import shutil
import re
from glob import glob
from __pkginfo__ import dict_prod, dict_prod_param
from products_data import (
    shell_escape,
    waf_template,
    mfront_env_template
)

from as_setup import (
    SETUP,
    GetSitePackages,
    less_than_version,
    export_parameters,
    relative_symlink,
    SetupInstallError,
    unexpandvars,
)

# ----- differ messages translation
def _(mesg): return mesg

# set/unset a value in a dict (cfg)
def set_cfg(setup_object, dico, var, value, **kargs):
   if not type(var) in (list, tuple):
      var = [var,]
   if not type(value) in (list, tuple):
      value = [value,]
   assert len(var) == len(value), 'ERROR in set_var : %r / %r' % (var, value)
   for k, v in zip(var, value):
      dico[k] = v
      setup_object._print('Setting %s=%s' % (k, v))


def add_flags(cfg, options):
    """Add compilation flags corresponding to the options."""
    if not type(options) in (list, tuple):
        options = [options,]
    _cmp_opts = ('CFLAGS', 'F90FLAGS',)
    _all_opts = _cmp_opts + ('LDFLAGS',)
    for opt in options:
        assert opt in ('OPENMP', 'I8'), "unsupported option!"
        for flag in _all_opts:
            flopt = flag + '_' + opt
            cfg[flag] = (cfg[flag] + ' ' + cfg.get(flopt, '')).strip()
        for flag in _cmp_opts:
            fldbg = flag + '_DBG'
            flopt = flag + '_' + opt
            cfg[fldbg] = (cfg[fldbg] + ' ' + cfg.get(flopt, '')).strip()
    for var in _all_opts:
        os.environ[var] = cfg[var]

def lib64_symlink(self, **kwargs):
    """Create a symlink lib to lib64."""
    if not osp.exists('lib'):
        relative_symlink('lib64', 'lib')

#-------------------------------------------------------------------------------
# 10. ----- hdf5
def setup_hdf5(dep, summary, **kargs):
   cfg=dep.cfg
   product = 'hdf5'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT',],
      set=['HOME_HDF',],
   )
   cfg['HOME_HDF'] = osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)
   ftools=kargs['find_tools']
   ftools.AddToPathVar(cfg, 'PATH', osp.join(cfg['HOME_HDF'], 'bin'))

   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""HDF5 is a Hierarchical Data Format product consisting of a data format
   specification and a supporting library implementation. HDF5 is designed to
   address some of the limitations of the older HDF product and to address current
   and anticipated requirements of modern systems and applications.""",
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=(
         ('IsInstalled', { 'filename' :
             [osp.join('__setup.installdir__', 'lib', 'libhdf5.a'),
              osp.join('__setup.installdir__', 'include', 'hdf5.h')]
         } ),
         ('Extract'  , {}),
         # gcc>=4.9 not supported by configure, should not use -ansi
         # use CFLAGS to force the option
         ('Configure', {
            'command' : 'unset LD ; CFLAGS=-std=gnu9x ./configure --prefix=%s' % cfg['HOME_HDF'],
         }),
         ('Make'     , { 'nbcpu' : ftools.nbcpu }),
         ('Install'  , {}),
         ('Install'  , {
            'external'  : lib64_symlink,
            'path'      : '__setup.installdir__',
         }),
         ('Clean'    , {}),
      ),

      installdir  = cfg['HOME_HDF'],
      sourcedir   = cfg['SOURCEDIR'],
   )
   return setup

#-------------------------------------------------------------------------------
# 12. ----- med
def setup_med(dep, summary, **kargs):
   cfg=dep.cfg
   product='med'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT', 'HOME_HDF', 'OTHERLIB', 'CXXLIB',],
      set=['HOME_MED',],
   )
   cfg['HOME_MED']=osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)
   ftools=kargs['find_tools']
   ftools.AddToPathVar(cfg, 'PATH', osp.join(cfg['HOME_MED'], 'bin'))

   if cfg['PLATFORM'] == 'darwin':
      # OS X linker does not support '--no-as-needed' option
      # plus passing python lib is necessary when using Swig on OS X
      # http://stackoverflow.com/questions/14782925/compiling-c-with-swig-on-mac-os-x
      ldflags='-lpython '
   else:
      ldflags = '-Wl,--no-as-needed '
   ldflags += cfg['OTHERLIB'] + ' ' + cfg['CXXLIB']
   disable_shared = ''

   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""MED-fichier (Modelisation et Echanges de Donnees, in English Modelisation
   and Data Exchange) is a library to store and exchange meshed data or computation results.
   It uses the HDF5 file format to store the data.""",
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=(
         ('IsInstalled', { 'filename' :
             [osp.join('__setup.installdir__', 'lib', 'libmed.a'),
              osp.join('__setup.installdir__', 'include', 'med.h')]
         } ),
         ('Extract'  , {}),
         ('Configure', {      # --with-med_int=long --disable-mesgerr
            'command' : ("unset LD ; export LDFLAGS='{0}' ; export F77=$F90; "
                         "export CXXFLAGS='-std=gnu++98'; "
                         "./configure {1} "
                        "--disable-mesgerr --with-hdf5={2} --prefix={3}")
                        .format(ldflags, disable_shared, cfg['HOME_HDF'], cfg['HOME_MED']),
         }),
         ('Make'     , { 'nbcpu' : ftools.nbcpu }),
         ('Install'  , {}),
         ('Install'  , {
            'external'  : lib64_symlink,
            'path'      : '__setup.installdir__',
         }),
         ('Clean'    , {}),
      ),

      installdir  = cfg['HOME_MED'],
      sourcedir   = cfg['SOURCEDIR'],
   )
   return setup

#-------------------------------------------------------------------------------
# 20. ----- gmsh
def setup_gmsh(dep, summary, **kargs):
   cfg=dep.cfg
   product='gmsh'
   version = dict_prod[product]
   pkg_name = '%s-%s-%s' % (product, version, os.uname()[0])
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT',],
      set=['HOME_GMSH',]
   )
   cfg['HOME_GMSH'] = osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)
   ftools=kargs['find_tools']
   ftools.AddToPathVar(cfg, 'PATH', osp.join(cfg['HOME_GMSH'], 'bin'))

   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""Gmsh is an automatic three-dimensional finite element mesh generator,
   primarily Delaunay, with built-in pre- and post-processing
   facilities. Its primal design goal is to provide a simple meshing tool
   for academic test cases with parametric input and up to date
   visualization capabilities.  One of the strengths of Gmsh is its
   ability to respect a characteristic length field for the generation of
   adapted meshes on lines, surfaces and volumes.""",
      content=pkg_name,
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=(
         ('IsInstalled', { 'filename' :
             [osp.join('__setup.installdir__', 'bin', 'gmsh')]
         } ),
         ('Extract'  , {}),
      ),

      installdir  = cfg['HOME_GMSH'],
      workdir     = osp.join(cfg['HOME_GMSH'], os.pardir),
      sourcedir   = cfg['SOURCEDIR'],
   )
   return setup

#-------------------------------------------------------------------------------
# 21. ----- grace
def setup_grace(dep, summary, **kargs):
   cfg=dep.cfg
   product='grace'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT',],
      set=['HOME_GRACE',]
   )
   cfg['HOME_GRACE'] = osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)
   ftools=kargs['find_tools']
   ftools.AddToPathVar(cfg, 'PATH', osp.join(cfg['HOME_GRACE'], 'bin'))

   # ----- check for libXm
   ftools.findlib_and_set(cfg, 'X11LIB', 'Xm',
      append=True, err=False)       # err=False, optional product !

   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""Grace is a WYSIWYG tool to make two-dimensional plots
   of numerical data.""",
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=(
         ('Extract'  , {}),
         ('Configure', {}),
         ('Make'     , { 'nbcpu' : ftools.nbcpu }),
         ('Install'  , {}),
         ('Clean'    , {}),
      ),

      installdir  = cfg['HOME_GRACE'],
      sourcedir   = cfg['SOURCEDIR'],
   )
   return setup

#-------------------------------------------------------------------------------
# 30. ----- astk
def setup_astk(dep, summary, **kargs):
   cfg=dep.cfg
   product='astk'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT', 'ASTER_VERSLABEL',
           'HOME_PYTHON', 'PYTHON_EXE', 'IFDEF',
           'TERMINAL', 'EDITOR', 'SHELL_EXECUTION',
           'PS_COMMAND_CPU', 'PS_COMMAND_PID',
           'DEBUGGER_COMMAND', 'DEBUGGER_COMMAND_POST',
           'SERVER_NAME', 'DOMAIN_NAME', 'FULL_SERVER_NAME', 'NODE' ],
      set=['HOME_TCL_TK', 'WISH_EXE',],
   )
   # should work with most of these versions (note empty string '')
   # (8.5 never tested : at the end)
   ftools=kargs['find_tools']
   if cfg.get('WISH_EXE') is None:
      ftools.find_and_set(cfg, 'WISH_EXE',
         filenames=['wish'+v for v in ['8.4', '84', '8.3', '83', '', '8.5', '85',]],
         paths=cfg.get('HOME_TCL_TK', []),)
      ftools.CheckFromLastFound(cfg, 'HOME_TCL_TK', 'bin')
      if not cfg.has_key('HOME_TCL_TK'):
         cfg['HOME_TCL_TK']=osp.abspath(osp.join(cfg['WISH_EXE'],os.pardir,os.pardir))

   # specific values for 'ASTK_SERV' files
   astk_cfg=cfg.copy()
   astk_cfg['ASTER_VERSION'] = cfg['ASTER_VERSLABEL']
   astk_cfg[cfg['IFDEF']]='\n'
   # patch for zsh in as_serv
   if re.search('zsh$', astk_cfg['SHELL_EXECUTION']):
      astk_cfg['USE_ZSH']=' added for zsh\n'
   if astk_cfg.has_key('OPT_ENV'):
      astk_cfg['OPT_ENV']='\n'+astk_cfg['OPT_ENV']

   # fill PYTHONPATH
   ftools.AddToPathVar(cfg, 'PYTHONPATH', GetSitePackages(cfg['ASTER_ROOT']))

   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""ASTK is the Graphical User Interface to manage Code_Aster calculations.""",
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=(
         ('Extract'  , {}),
         ('Configure', {
            'external' : export_parameters,
            'filename' : 'external_configuration.py',
            'dict_cfg' : astk_cfg,
         }),
         ('PyInstall', { 'cmd_opts' : '--force' }),
         ('Clean',     {}),
      ),

      installdir  = GetSitePackages(cfg['ASTER_ROOT']),
      sourcedir   = cfg['SOURCEDIR'],
   )
   return setup

#-------------------------------------------------------------------------------
# 40. ----- Metis (standard version)
def setup_metis(dep, summary, **kargs):
   cfg=dep.cfg
   product='metis'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT',],
      set=['HOME_METIS',],
   )
   cfg['HOME_METIS'] = osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)

   # metis5
   actions = (
     ('IsInstalled', { 'filename' :
         [osp.join('__setup.installdir__', 'lib', 'libmetis.a'),
          osp.join('__setup.installdir__', 'include', 'metis.h'), ]
     } ),
     ('Extract'  , {}),
     ('Configure', {
        'command': 'make config prefix=%(dest)s' % { 'dest' : cfg['HOME_METIS'] },
     }),
     ('Make'     , { 'nbcpu' : kargs['find_tools'].nbcpu }),
     ('Install'  , {}),
     ('Clean',     {}),
   )

   # metis4
   if version.startswith('4'):
      actions = (
         ('IsInstalled', { 'filename' :
             [osp.join('__setup.installdir__', 'lib', 'libmetis.a'),
              osp.join('__setup.installdir__', 'include', 'metis.h'), ]
         } ),
         ('Extract'  , {}),
         ('ChgFiles' , {
            'files'     : ['Makefile.in'],
            'dtrans'    : cfg,
         }),
         ('Make'     , { 'nbcpu' : kargs['find_tools'].nbcpu }),
         ('Install'  , {
            'command'   : 'make install prefix=%(dest)s ; ' \
                          'cp Makefile.in %(dest)s' \
               % { 'dest' : cfg['HOME_METIS'] },
         }),
         ('Clean',     {}),
      )

   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""METIS is a software package for partitioning unstructured graphs,
   partitioning meshes, and computing fill-reducing orderings of sparse matrices.
   This version is for MUMPS needs.""",
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=actions,

      installdir  = cfg['HOME_METIS'],
      sourcedir   = cfg['SOURCEDIR'],
   )
   return setup

#-------------------------------------------------------------------------------
# 41. ----- tfel / mfront
def setup_tfel(dep, summary, **kargs):
   cfg=dep.cfg
   product = 'tfel'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT',],
      set=['HOME_MFRONT',],
   )
   cfg['HOME_MFRONT'] = osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)
   ftools=kargs['find_tools']
   ftools.AddToPathVar(cfg, 'PATH', osp.join(cfg['HOME_MFRONT'], 'bin'))
   ftools.AddToPathVar(cfg, 'LD_LIBRARY_PATH', osp.join(cfg['HOME_MFRONT'], 'lib'))
   ftools.AddToPathVar(cfg, 'PYTHONPATH', GetSitePackages(cfg['HOME_MFRONT']))
   portable = 'OFF'
   if cfg['PLATFORM'] == 'darwin':
      # needed for OS X which does not support optimized build with GNU (only CLANG)
      # http://stackoverflow.com/questions/10327939/erroring-on-no-such-instruction-while-assembling-project-on-mac-os-x-lion
      portable = 'ON'

   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""MFront is a code generator which translates a set of
    closely related domain specific languages into plain C++ on top of the
    TFEL library.""",
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=(
         ('IsInstalled', { 'filename' :
             [osp.join('__setup.installdir__', 'lib', 'libTFELSystem.so'),
              osp.join('__setup.installdir__', 'lib', 'libAsterInterface.so'),
              osp.join('__setup.installdir__', 'include', 'MFront', 'MFront.hxx')]
         } ),
         ('Extract'  , {}),
         ('Configure', {
            'command' : ('mkdir build ; cd build ; '
                'cmake .. -DTFEL_SVN_REVISION=%s -DCMAKE_BUILD_TYPE=Release '
                '-Dlocal-castem-header=ON -Denable-fortran=ON '
                '-DPython_ADDITIONAL_VERSIONS=2.7 -Denable-python=ON '
                '-Denable-broken-boost-python-module-visibility-handling=ON '
                '-Denable-python-bindings=ON '
                '-Denable-cyrano=ON -Denable-aster=ON '
                '-Ddisable-reference-doc=ON -Ddisable-website=ON '
                '-Denable-portable-build=%s -DCMAKE_INSTALL_PREFIX=%s') \
                % (version, portable, cfg['HOME_MFRONT']),
         }),
         ('Make'     , { 'path'    : osp.join('__setup.workdir__', '__setup.content__', 'build'),
                         'nbcpu' : ftools.nbcpu }),
         ('Install'  , { 'path'    : osp.join('__setup.workdir__', '__setup.content__', 'build'), }),
         ('Clean'    , {}),
      ),

      installdir  = cfg['HOME_MFRONT'],
      sourcedir   = cfg['SOURCEDIR'],
   )
   return setup

#-------------------------------------------------------------------------------
# 43. ----- scotch
def setup_scotch(dep, summary, **kargs):
   cfg=dep.cfg
   product='scotch'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT', 'FLEX', 'RANLIB', 'YACC'],
      set=['HOME_SCOTCH',],
   )
   cfg['HOME_SCOTCH']=osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)

   scotch_cfg = {}.fromkeys(['CC', 'CFLAGS', 'FLEX', 'RANLIB', 'YACC'], '')
   scotch_cfg.update(cfg)
   if cfg['PLATFORM'] != 'darwin':
      scotch_cfg['CFLAGS'] += ' -Wl,--no-as-needed'
   else:
      # OS X linker does not support '--no-as-needed'
      # plus it does not provide some *NIX clock timing and we must use an old timing method in Scotch (as used in Make.inc/Makefile.inc.i686_mac_darwin10)
      scotch_cfg['CFLAGS'] += ' -DCOMMON_TIMING_OLD -DCOMMON_PTHREAD_BARRIER'


   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""Static mapping, graph partitioning, and sparse matrix block ordering package.""",
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=(
         ('IsInstalled', { 'filename' :
             [osp.join('__setup.installdir__', 'lib', 'libesmumps.a'),
              osp.join('__setup.installdir__', 'lib', 'libscotch.a'),
              osp.join('__setup.installdir__', 'lib', 'libscotcherr.a'),
              osp.join('__setup.installdir__', 'lib', 'libscotcherrexit.a'),
              osp.join('__setup.installdir__', 'lib', 'libscotchmetis.a'),
              osp.join('__setup.installdir__', 'include', 'scotchf.h'),
              osp.join('__setup.installdir__', 'include', 'scotch.h') ]
         } ),
         ('Extract',   {}),
         ('Configure', {
            'command': 'mv src/Makefile.inc src/Makefile.inc.orig ; '
                       'cp src/Makefile.aster_full src/Makefile.inc',
         }),
         ('ChgFiles',  {
            'files'     : [osp.join('src', 'Makefile.inc'), ],
            'dtrans'    : scotch_cfg,
         }),
         # remove librt on darwin
         cfg['PLATFORM'] != 'darwin' and (None, None) or \
            ('ChgFiles',  {
               'files'     : [osp.join('src', 'Makefile.inc'), ],
               'delimiter' : '',
               'dtrans'    : { re.escape('-lrt'): ''},
            }),
         ('Make',      {
            'path'   : osp.join('__setup.workdir__', '__setup.content__', 'src'),
            'nbcpu'  : 1, # seems not support "-j NBCPU" option
         }),
         # only if version >= 6
         version.startswith('5') and (None, None) or \
             ('Make',      {
                'command': 'make esmumps',
                'path'   : osp.join('__setup.workdir__', '__setup.content__', 'src'),
                'nbcpu'  : 1, # seems not support "-j NBCPU" option
             }),
         ('Install',   {'command' : 'make install prefix=%s' % cfg['HOME_SCOTCH'],
                        'path'    : osp.join('__setup.workdir__', '__setup.content__', 'src') }),
         ('Clean',     {}),
      ),

      installdir  = cfg['HOME_SCOTCH'],
      sourcedir   = cfg['SOURCEDIR'],
   )
   return setup

#-------------------------------------------------------------------------------
# 44. ----- mumps
def setup_mumps(dep, summary, **kargs):
   cfg=dep.cfg
   product='mumps'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT', 'CC', 'F90', 'LD', 'INCLUDE_MUMPS', 'MATHLIB', 'OTHERLIB',
           'HOME_METIS', 'HOME_SCOTCH'],
      set=['HOME_MUMPS',],
   )
   cfg['HOME_MUMPS']=osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)
   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""MUMPS: a MUltifrontal Massively Parallel sparse direct Solver.""",
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=(
         ('IsInstalled', { 'filename' :
             [osp.join('__setup.installdir__', 'lib', 'libcmumps.a'),
              osp.join('__setup.installdir__', 'lib', 'libdmumps.a'),
              osp.join('__setup.installdir__', 'lib', 'libmpiseq.a'),
              osp.join('__setup.installdir__', 'lib', 'libmumps_common.a'),
              osp.join('__setup.installdir__', 'lib', 'libpord.a'),
              osp.join('__setup.installdir__', 'lib', 'libsmumps.a'),
              osp.join('__setup.installdir__', 'lib', 'libzmumps.a')]
         } ),
         ('Extract'  , {}),
         ('Configure', {
            'command'   : 'CC=%(CC)s FC=%(F90)s '
                          'LIBPATH="%(HOME_SCOTCH)s/lib %(HOME_METIS)s/lib" '
                          'INCLUDES="%(HOME_SCOTCH)s/include %(HOME_METIS)s/include" '
                          'OPTLIB_FLAGS="%(MATHLIB)s %(OTHERLIB)s" '
                          './waf configure --maths-libs="" --prefix=%(HOME_MUMPS)s --install-tests' % cfg,
            'capturestderr' : False,
         }),
         ('Make'     , {
            'command' : './waf build --jobs=1',
            'capturestderr' : False,
         }),
         ('Install',   {
            'command' : './waf install --jobs=1',
            'capturestderr' : False,
         }),
         ('Clean',     {}),
      ),
      clean_actions=(
         ('Configure', { # to force 'ld' temporarily to null
            'external'  : set_cfg,
            'dico'      : cfg,
            'var'       : 'HOME_MUMPS',
            'value'     : '',
         }),
      ),

      installdir  = cfg['HOME_MUMPS'],
      sourcedir   = cfg['SOURCEDIR'],
   )
   return setup

#-------------------------------------------------------------------------------
# 50. ----- Code_Aster
def write_waf_cfg(self, filename, config, template, **kwargs):
    """Fille and write template into filename"""
    # remove mumps includes
    if config['ASTER_VERSION'].startswith('12.'):
        lines = [i for i in template.splitlines() \
                    if not '%(HOME_MUMPS)s/include' in i]
        template = os.linesep.join(lines)
    open(filename, 'wb').write(template % config)

def write_aster_conf(self, filename, config, **kwargs):
    """Write the version info"""
    template = 'vers : %(ASTER_VERSION)s:%(ASTER_VERSION_DIR)s/share/aster\n'
    open(filename, 'wb').write(template % config)

def setup_aster(dep, summary, **kargs):
   cfg=dep.cfg
   product='aster'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   short_version = '.'.join(version.split('.')[:2])
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT', 'ASTER_VERSION',
           'HOME_PYTHON', 'PYTHON_EXE', 'PYTHONLIB',
           'HOME_MUMPS', 'HOME_MPI', 'INCLUDE_MUMPS', 'HOME_METIS',
           'HOME_MED', 'HOME_HDF', 'HOME_MFRONT',
           #'HOME_GMSH', 'HOME_HOMARD', optional
           'LD', 'CC', 'F90', 'CXXLIB', 'OTHERLIB', 'SYSLIB', ],
      reqobj=['file:?ASTER_ROOT?/bin/as_run',
              'file:?ASTER_ROOT?/etc/codeaster/profile.sh'],
   )
   cfg['ASTER_VERSION_DIR'] = osp.join(cfg['ASTER_ROOT'], cfg['ASTER_VERSION'])
   os.environ['ASTER_VERSION_DIR'] = cfg['ASTER_VERSION_DIR']
   cfg['OPT_ENV']  = cfg.get('OPT_ENV', '')
   ftools=kargs['find_tools']

   unexpanded_cfg = unexpandvars(cfg,
                        vars=('ASTER_VERSION_DIR', 'ASTER_ROOT'))
   # ensure not to automatically load additional environment in waf
   os.environ['DEVTOOLS_COMPUTER_ID'] = 'aster_full'

   # for external programs (see data/wscript)
   os.environ['METISDIR'] = cfg['HOME_METIS']
   # optional paths
   if cfg.get('HOME_GMSH'):
       os.environ['GMSH_BIN_DIR'] = osp.join(cfg['HOME_GMSH'], 'bin')
   if cfg.get('HOME_HOMARD'):
       os.environ['HOMARD_ASTER_ROOT_DIR'] = cfg['HOME_HOMARD']

   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""Code_Aster finite element method solver.""",
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=(
         ('IsInstalled', { 'filename' :
             [osp.join('__setup.installdir__', cfg['ASTER_VERSION'], 'bin', 'aster'),
              osp.join('__setup.installdir__', cfg['ASTER_VERSION'], 'include', 'aster', 'aster.h'),
              osp.join('__setup.installdir__', cfg['ASTER_VERSION'], 'lib', 'aster', 'aster_core.py'),
              osp.join('__setup.installdir__', cfg['ASTER_VERSION'], 'share', 'aster', 'config.txt'), ]
         } ),
         ('Extract'  , {}),
         ('Configure', {
            'external' : write_waf_cfg,
            'template' : waf_template,
            'filename' : 'wafcfg/aster_full_config.py',
            'config'   : cfg,
         }),
         ('Configure', {
            'command'   : './waf configure --use-config=aster_full_config '
                          '  --install-tests --prefix=%(ASTER_VERSION_DIR)s' % cfg,
            'capturestderr' : False,
         }),
         ('Make'  , {
            'command'   : './waf build',
            'capturestderr' : False,
         }),
         ('Install'  , {
            'command'   : './waf install',
            'capturestderr' : False,
         }),
         ('Configure', {
            'external' : write_waf_cfg,
            'template' : waf_template,
            'filename' : osp.join(cfg['ASTER_VERSION_DIR'], 'share', 'aster',
                                  'aster_full_config.py'),
            'config'   : cfg,
         }),
         ('Configure', {
            'external' : write_waf_cfg,
            'template' : mfront_env_template,
            'filename' : osp.join(cfg['ASTER_VERSION_DIR'], 'share', 'aster',
                                  'profile_mfront.sh'),
            'config'   : cfg,
         }),
         # remove version with same name
         ('ChgFiles' , {
            'files'     : ['aster'],
            'path'      : osp.join(cfg['ASTER_ROOT'],'etc','codeaster'),
            'dtrans'    : {'^ *vers : %s(|:.*)\n' % cfg['ASTER_VERSLABEL'] : '',
                           },
            'delimiter' : '',
            'keep'      : True,
            'ext'       : '.install_'+cfg['ASTER_VERSION'],
         }),
         # add testing/stable version in the aster version file
         ('ChgFiles' , {
            'files'     : ['aster'],
            'path'      : osp.join(cfg['ASTER_ROOT'],'etc','codeaster'),
            'dtrans'    : {
                          re.escape('?vers : VVV?') : \
                            '?vers : VVV?\n'
                            'vers : %(ASTER_VERSLABEL)s:%(ASTER_VERSION_DIR)s/share/aster' % cfg,
                           },
            'delimiter' : '', # that's why some ? have been added above
            'keep'      : False,
         }),
         # add numbered version in the aster.conf file
         ('ChgFiles'  , {
            'external' : write_aster_conf,
            'filename' : osp.join(cfg['ASTER_VERSION_DIR'], 'aster.conf'),
            'config'   : cfg,
         }),
         ('Clean',     {}),
      ),

      installdir  = cfg['ASTER_ROOT'],
      sourcedir   = cfg['SOURCEDIR'],
   )
   return setup

#-------------------------------------------------------------------------------
# 59. ----- homard
def setup_homard(dep, summary, **kargs):
   cfg=dep.cfg
   product='homard'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT', 'PYTHON_EXE'],
      set=['HOME_HOMARD'],
   )
   cfg['HOME_HOMARD'] = osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)

   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""The HOMARD software carries out the adaptation of 2D/3D finite element or
   finite volume meshes by refinement and unrefinement techniques.""",
      #content='HOMARD',
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=(
         ('IsInstalled', { 'filename' :
           [osp.join('__setup.installdir__', 'ASTER_HOMARD', 'homard'),
            osp.join('__setup.installdir__', 'ASTER_HOMARD', 'homard.py'), ]
         }),
         ('Extract'  , {}),
         ('Install'  , { 'command' :
            '%(PYTHON_EXE)s setup_homard.py --prefix=%(HOME_HOMARD)s' % cfg
            }),
         ('Clean'    , {}),
      ),

      installdir  = cfg['HOME_HOMARD'],
      sourcedir   = cfg['SOURCEDIR'],
   )
   return setup
