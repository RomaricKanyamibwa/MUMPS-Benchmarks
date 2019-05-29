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
import multiprocessing
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
# 40. ----- Metis (standard version)
def setup_metis(dep, summary, **kargs):
   cfg=dep.cfg
   product='metis'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT',],
      set=['HOME_METIS','LIB_METIS','D_METIS',],
   )
   cfg['HOME_METIS'] = osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)
   cfg['LIB_METIS']  = "-lmetis"
   cfg['D_METIS']    = "-Dmetis"

   # metis5
   actions = (
     ('IsInstalled', { 'filename' :
         [osp.join('__setup.installdir__', 'lib', 'libmetis.a'),
          osp.join('__setup.installdir__', 'include', 'metis.h'), ]
     } ),
     ('Extract'  , {}),
     ('Configure', {
        'command': 'make config prefix=%(dest)s openmp=openmp' % { 'dest' : cfg['HOME_METIS'] },
     }),
     ('Make'     , { 'nbcpu' : max(multiprocessing.cpu_count(),kargs['find_tools'].nbcpu) }),
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
         ('Make'     , { 'nbcpu' : max(multiprocessing.cpu_count(),kargs['find_tools'].nbcpu) }),
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

# 40. ----- Metis (standard version)
def setup_parmetis(dep, summary, **kargs):
   cfg=dep.cfg
   product='parmetis'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT',],
      set=['HOME_METIS','LIB_METIS','D_METIS'],
   )
   cfg['HOME_METIS'] = osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)
   cfg['LIB_METIS']  = "-lparmetis -lmetis"
   cfg['D_METIS']    = "-Dmetis -Dparmetis"

   # metis5
   actions = (
     ('IsInstalled', { 'filename' :
         [#osp.join('__setup.installdir__', 'lib', 'libmetis.a'),
          osp.join('__setup.installdir__', 'lib', 'libparmetis.a'),
          # osp.join('__setup.installdir__', 'include', 'metis.h'),
          osp.join('__setup.installdir__', 'include', 'parmetis.h'), ]
     } ),
     ('Extract'  , {}),
     ('Configure', {
        'command': 'make config prefix=%(dest)s' % { 'dest' : cfg['HOME_METIS'] },
     }),
     ('Make'     , { 'nbcpu' : max(multiprocessing.cpu_count(),kargs['find_tools'].nbcpu) }),
     ('Install'  , {}),
     ('Clean',     {}),
   )

   # metis4
   if version.startswith('4'):
      actions = (
         ('IsInstalled', { 'filename' :
             [osp.join('__setup.installdir__', 'lib', 'libmetis.a'),
              osp.join('__setup.installdir__', 'lib', 'libparmetis.a'),
              osp.join('__setup.installdir__', 'include', 'metis.h'),
              osp.join('__setup.installdir__', 'include', 'parmetis.h'), ]
         } ),
         ('Extract'  , {}),
         ('Configure', {
            'command': 'make -j %(nbcpu)s config cc=%(CC)s cxx=%(CXX)s openmp=openmp prefix=%(dest)s'\
             % { 'nbcpu' : multiprocessing.cpu_count(),'CC' : cfg['CC'] ,
             'CXX' : cfg['CXX'] ,'dest' : cfg['HOME_METIS'] },
          }),
         # ('Make'     , { 'nbcpu' : max(multiprocessing.cpu_count(),kargs['find_tools'].nbcpu) }),
         ('Install'  , {
            'command'   : 'make -j %(nbcpu)s install prefix=%(dest)s ;'
            'cp $(find $PWD -iname metis.h) %(dest)s/include;'
            'cp $(find $PWD -iname *libmetis.*) %(dest)s/lib' \
               % { 'nbcpu' : multiprocessing.cpu_count(),'dest' : cfg['HOME_METIS'] },
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
# 43. ----- scotch
def setup_scotch(dep, summary, **kargs):
   cfg=dep.cfg
   product='scotch'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT', 'FLEX', 'RANLIB', 'YACC'],
      set=['HOME_SCOTCH','LIB_SCOTCH','D_SCOTCH',],
   )
   cfg['HOME_SCOTCH']  =osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)
   cfg['LIB_SCOTCH'] ="-lesmumps -lscotch -lscotcherr"
   cfg['D_SCOTCH']     ="-Dscotch"

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
            'nbcpu'  : multiprocessing.cpu_count(),#1, # seems not support "-j NBCPU" option
         }),
         # only if version >= 6
         version.startswith('5') and (None, None) or \
             ('Make',      {
                'command': 'make esmumps',
                'path'   : osp.join('__setup.workdir__', '__setup.content__', 'src'),
                'nbcpu'  : multiprocessing.cpu_count(),#1, # seems not support "-j NBCPU" option
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
# 43.2 ----- ptscotch
def setup_ptscotch(dep, summary, **kargs):
   cfg=dep.cfg
   product='scotch'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT', 'FLEX', 'RANLIB', 'YACC'],
      set=['HOME_SCOTCH','LIB_SCOTCH','D_SCOTCH',],
   )
   cfg['HOME_SCOTCH']=osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)
   cfg['LIB_SCOTCH'] ="-lptesmumps -lscotch -lptscotch -lptscotcherr"
   cfg['D_SCOTCH']     ="-Dscotch -Dptscotch"

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
             [osp.join('__setup.installdir__', 'lib', 'libptesmumps.a'),
              osp.join('__setup.installdir__', 'lib', 'libesmumps.a'),
              osp.join('__setup.installdir__', 'lib', 'libscotch.a'),
              osp.join('__setup.installdir__', 'lib', 'libptscotch.a'),
              osp.join('__setup.installdir__', 'lib', 'libptscotcherr.a'),
              osp.join('__setup.installdir__', 'lib', 'libscotcherrexit.a'),
              osp.join('__setup.installdir__', 'lib', 'libptscotcherrexit.a'),
              osp.join('__setup.installdir__', 'lib', 'libscotchmetis.a'),
              osp.join('__setup.installdir__', 'lib', 'libptscotchparmetis.a'),
              osp.join('__setup.installdir__', 'include', 'scotchf.h'),
              osp.join('__setup.installdir__', 'include', 'ptscotchf.h'),
              osp.join('__setup.installdir__', 'include', 'scotch.h'),
              osp.join('__setup.installdir__', 'include', 'ptscotch.h') ]
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
                'command': 'make ptesmumps',
                'path'   : osp.join('__setup.workdir__', '__setup.content__', 'src'),
                #'nbcpu'  : , # seems not support "-j NBCPU" option
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
def benchcfg(cfg):
   bench_cfg = {}.fromkeys(['CC', 'FCFLAGS', 'CFLAGS', 'RANLIB'
    ,'HOME_METIS', 'HOME_SCOTCH','HOME_MUMPS'
    ,'LIB_SCOTCH','LIB_METIS','D_SCOTCH','D_METIS'], '')
   bench_cfg.update(cfg)

   bench_cfg['AR']='ar'
   bench_cfg['ARFLAGS']='vr'
   bench_cfg['LINK_FC']=bench_cfg['FC']
   bench_cfg['STLIB_METIS']=""
   bench_cfg['STLIB_SCOTCH']=""

   return bench_cfg

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
   bench_cfg=benchcfg(cfg)
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
            'command': 'cp Make/Makefile%(ext)s Makefile.inc'%{'ext':cfg['make_extension']},
         }),
         ('ChgFiles',  {
            'files'     : ['Makefile.inc'],
            'dtrans'    : bench_cfg,
         }),
         ('Make'     , {
            'command' : 'make alllib',
            'capturestderr' : False,
         }),
         ('Install',   {
            'command' : 'cp -r include/ lib/ libseq/ PORD/ Makefile.inc %(dest)s' % {'dest':cfg['HOME_MUMPS']}
            ,
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
# 45. ----- mumps benchmark
def setup_mumps_benchmark(dep, summary, **kargs):
   cfg=dep.cfg
   product='mumps_benchmark'
   version = dict_prod[product]
   pkg_name = '%s-%s' % (product, version)
   # ----- add (and check) product dependencies
   dep.Add(product,
      req=['ASTER_ROOT', 'CC', 'F90', 'LD', 'INCLUDE_MUMPS', 'MATHLIB', 'OTHERLIB',
           'HOME_METIS', 'HOME_SCOTCH','HOME_MPI','HOME_MUMPS'],
      set=['HOME_MUMPS_BENCH',],
   )
   cfg['HOME_MUMPS_BENCH']=osp.join(cfg['ASTER_ROOT'], 'public', pkg_name)

   bench_cfg=benchcfg(cfg)
   mode=cfg['make_extension'].split('.')

   instruct="cp Make/Makefile.in Makefile"

   # ----- setup instance
   setup=SETUP(
      product=product,
      version=version,
      description="""MUMPS Solver Benchmarks.""",
      depend=dep,
      system=kargs['system'],
      log=kargs['log'],
      reinstall=kargs['reinstall'],

      actions=(
         ('Extract'  , {}),
         ('Configure', {
            'command':instruct,
         }),
         ('ChgFiles',  {
            'files'     : ['Makefile'],
            'dtrans'    : bench_cfg,
         }),
         ('Install',   {
            'command' : 'cp determinant_test aster_matrix_input dsimpletest.F'
            ' Makefile %(dest)s/'
            %{'dest':cfg['HOME_MUMPS_BENCH']} ,
            # 'capturestderr' : False,
         }),
         ('Clean',     {}),
         ('Make'     , {
            'path' : cfg['HOME_MUMPS_BENCH'] ,
            'capturestderr' : False,
         }),
      ),
      clean_actions=(
         ('Configure', { # to force 'ld' temporarily to null
            'external'  : set_cfg,
            'dico'      : cfg,
            'var'       : 'HOME_MUMPS_BENCH',
            'value'     : '',
         }),
      ),

      installdir  = cfg['HOME_MUMPS_BENCH'],
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
           # 'HOME_MED', 'HOME_HDF', 'HOME_MFRONT',
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