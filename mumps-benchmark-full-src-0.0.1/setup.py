#!/usr/bin/env python
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

# ----- differ messages translation
def _(mesg): return mesg

import sys
# ----- check for Python version
if sys.hexversion < 0x020600F0:
   print _('This script requires Python 2.6 or higher, sorry !')
   sys.exit(4)

from glob import glob
import os
import os.path as osp
import time
import re
import traceback
import shutil
from types import ModuleType
from optparse import OptionParser
import distutils.sysconfig as SC

from as_setup import (
    SUMMARY,
    SYSTEM,
    DEPENDENCIES,
    FIND_TOOLS,
    should_continue,
    should_continue_reg,
    less_than_version,
    get_install_message,
    relative_symlink,
    SetupError,
)

try:
   from __pkginfo__ import dict_prod, dict_prod_param
   short_version = '.'.join(dict_prod['aster'].split('.')[:2])
   available_products = dict_prod_param['__to_install__']
except (ImportError, KeyError), msg:
   print "File not found or invalid : '__pkginfo__.py'"
   print "Error :"
   print msg
   sys.exit(4)

import products
import mprint

python_version    = '.'.join([str(n) for n in sys.version_info[:3]])
pythonXY          = 'python' + '.'.join([str(n) for n in sys.version_info[:2]])

log_file = 'setup.log'
log = mprint.MPRINT(log_file, 'w')


def product_alias(product):
    return re.sub("[\-\+\.]+", "_", product)


def main():
   #-------------------------------------------------------------------------------
   # 0. initialisation, configuration of the command-line parser
   #-------------------------------------------------------------------------------
   # 0.1. ----- list of products to install (could be skip through cfg)
   t_ini = time.time()
   to_install_ordered=['scotch','ptscotch','metis','parmetis','mumps','mumps_benchmark']
   to_install = [prod for prod in to_install_ordered if prod in available_products]

   __aster_version__ = short_version

   # 0.2. ----- version
   import __pkginfo__

   svers = os.linesep.join(['MUMPS Benchmarks Setup version ' + \
                           __pkginfo__.version + '-' + __pkginfo__.release, __pkginfo__.copyright])

   usage="usage: python %prog [options] [install|test] [arg]\n" + \
   _("""

   Setup script for MUMPS Benchmarks distribution.

   NOTE : MUMPS Benchmarks or eventually other products will be configured with
          the Python you use to run this setup :
            interpreter    : %(interp)s (version %(vers)s)
            prefix         : %(prefix)s

   arguments :
     action : only 'install' or 'test'.

     By default all products are installed, but you can install only one (if a
     first attempt failed). Example : python setup.py install aster.

     Available products (the order is important) :
       %(prod)s.""") % {
      'vers' : python_version,
      'prefix' : os.path.abspath(sys.prefix),
      'interp' : sys.executable,
      'prod' : ', '.join(to_install),
   }

   _separ='\n' + '-'*80 + '\n'
   _fmt_err=_(' *** Exception raised : %s')
   _fmt_search=_('Checking for %s...   ')

   log._print(_separ, svers, _separ)

   scmd = """Command line :
   %s""" % ' '.join([sys.executable] + sys.argv)
   log._print(_separ, scmd, _separ)

   # 0.3. ----- command line parser
   parser = OptionParser(
         usage=usage,
         version='MUMPS Benchmarks Setup version ' + __pkginfo__.version + '-' + __pkginfo__.release)
   parser.add_option("--prefix", dest="prefix", action='store',
         help=_("define toplevel directory for MUMPS Benchmarks (identical to --aster_root)"), metavar="DIR")
   parser.add_option("--aster_root", dest="ASTER_ROOT", action='store',
   #       default='/opt/aster',    not here !
         help=_("define toplevel directory for MUMPS Benchmarks (default '/opt/aster')"), metavar="DIR")
   parser.add_option("--sourcedir", dest="SOURCEDIR", action='store',
   #       default='./SRC',         not here !
         help=_("directory which contains archive files (default './SRC')"),
         metavar="DIR")
   parser.add_option("--cfg", dest="fcfg", action='store', metavar="FILE",
         help=_("file which contains the installation parameters"),)
   parser.add_option("--nocache", dest="cache", action='store_false',
         default=True,
         help=_("delete cache file before starting (it's default if you do not specify a product name)"),)
   parser.add_option("--ignore_error", dest="ign_err", action='store_true',
         default=False,
         help=_("ignore error when checking prerequisites"),) # same as the old --force option
   parser.add_option("--reinstall", dest="reinstall", action='store',
         default='ask',
         help=_("tell what to do if a product is already installed: force, ignore, ask "
                "('force' reinstalls the product, 'ignore' keeps the current one, 'ask' prompts "
                "for each product)"),)
   parser.add_option("-q", "--quiet", dest="verbose", action='store_false',
         default=True,
         help=_("turn off verbose mode"),)
   parser.add_option("-g", "--debug", dest="debug", action='store_true',
         default=False,
         help=_("turn on debug mode"),)
   parser.add_option("--noprompt", dest="noprompt", action='store_true',
         default=False,
         help=_("do not ask any questions"),)
   parser.add_option("--parallel", dest="parallel", action='store_true',
         default=False,
         help=_("run on parallel mode"),)

   opts, args = parser.parse_args()
   fcfg     = opts.fcfg
   verbose  = opts.verbose
   debug    = opts.debug
   noprompt = opts.noprompt
   parallel = opts.parallel
   should_continue_reg(noprompt)

   main_script=sys.argv[0]
   setup_maindir = os.path.normpath(os.path.dirname(os.path.abspath(main_script)))

   default_cfgfile = os.path.join(setup_maindir, 'setup.cfg')
   cache_file      = os.path.join(setup_maindir, 'setup.cache')

   def_opts={
      'ASTER_ROOT' : '/opt/aster',
      'SOURCEDIR'  : os.path.normpath(os.path.join(setup_maindir, 'SRC')),
   }
   if opts.prefix is not None and opts.ASTER_ROOT is None:
      opts.ASTER_ROOT = opts.prefix

   # 0.4. ----- check for argument value
   _install = True
   _test    = False
   if len(args) > 0:
      if args[0] == 'install':
         pass
      elif args[0] == 'test':
         _test = True
      elif args[0] == 'clean':
         for fname in glob(log_file + '*') + glob('setup.dbg*') \
                + glob('*.pyc') + glob(cache_file):
             print _("remove %s") % fname
             os.remove(fname)
         print _("temporary files deleted!")
         return
      else:
         parser.error(_("unexpected argument %s") % repr(args[0]))
   if opts.reinstall not in ('force', 'ignore', 'ask'):
       parser.error(_("--reinstall must be one of 'force', 'ignore' or 'ask'. "
                      "'%s' is not allowed") % opts.reinstall)

   # 0.5. ----- adjust to_install list
   to_install0 = to_install[:]
   if len(args) > 1:
      arg0 = args.pop(0)
      for p in to_install[:]:
         if not p in args:
            to_install.remove(p)

   # 0.6. ----- list of exceptions to handle during installation
   if not debug:
      safe_exceptions=(SetupError,)
   else:
      safe_exceptions=None

   #-------------------------------------------------------------------------------
   # 1. fill cfg reading setup.cfg + setup.cache files
   #-------------------------------------------------------------------------------
   cfg={}
   cfg_init_keys=[]
   # 1.1.1. ----- read parameters from 'fcfg'
   if fcfg==None and os.path.isfile(default_cfgfile):
      fcfg=default_cfgfile
   if fcfg<>None:
      fcfg=os.path.expanduser(fcfg)
      if not os.path.isfile(fcfg):
         log._print(_('file not found %s') % fcfg)
         sys.exit(4)
      else:
         log._print(_separ,_('Reading config file %s...' % repr(fcfg)))
         context={}
         try:
            execfile(fcfg, context)
         except:
            traceback.print_exc()
            log._print(_separ, term='')
            raise SetupError(_("reading '%s' failed (probably syntax" \
                  " error occured, see traceback above)") % fcfg)
         for k,v in context.items():
            if re.search('^__',k)==None and not type(v) is ModuleType:
               cfg[k]=v
               cfg_init_keys.append(k)
               log._print(_(' %15s (from cfg) : %s') % (k, repr(v)))

   # 1.1.2. ----- read cache file
   # delete it if --nocache or to_install list is full.
   if (not opts.cache or to_install==to_install0) and os.path.exists(cache_file):
      log._print(_separ,_('Deleting cache file %s...' % repr(cache_file)))
      os.remove(cache_file)
   if os.path.exists(cache_file):
      if fcfg<>None and os.stat(fcfg).st_ctime > os.stat(cache_file).st_ctime:
         log._print(_separ, _(""" WARNING : %(cfg)s is newer than %(cache)s.
              The modifications you made in %(cfg)s might be overriden with
              cached values. If errors occur delete %(cache)s and restart at
              the beginning !""") \
            % { 'cfg' : repr(fcfg), 'cache' : repr(cache_file)}, _separ)
         should_continue()
      log._print(_separ,_('Reading cache file %s...' % repr(cache_file)))
      context={}
      try:
         execfile(cache_file, context)
      except:
         traceback.print_exc()
         log._print(_separ, term='')
         raise SetupError(_("reading '%s' failed (probably syntax error occured)") % cache_file)
      os.remove(cache_file)
      lk = context.keys()
      lk.sort()
      for k in lk:
         v = context[k]
         if re.search('^__',k)==None and not type(v) is ModuleType:
            cfg[k]=v
            if not k in cfg_init_keys:
               cfg_init_keys.append(k)
            log._print(_(' %15s (from cache) : %s') % (k, repr(v)))

   # 1.1.3. ----- list of options to put in cfg
   for o in ('ASTER_ROOT', 'SOURCEDIR',):
      if getattr(opts, o) is not None:
         cfg[o]=os.path.normpath(os.path.abspath(getattr(opts, o)))
         log._print(_separ,_(' %15s (from arguments) : %s') % (o, cfg[o]))
      elif not cfg.has_key(o):
         cfg[o]=def_opts[o]
      # if all options are not directories write a different loop
      cfg[o]=os.path.abspath(os.path.expanduser(cfg[o]))
   
   if cfg['PREFER_COMPILER'] == 'GNU':
      cfg['make_extension']=".debian"
   else:
      cfg['make_extension']=".INTEL"

   # print("=================================================================================")
   # print(cfg['PREFER_COMPILER'])
   # print("=================================================================================")

   if parallel :
      cfg['make_extension']+=".PAR"
      log._print(">>>>>>>>>>>>> Executing in Parallel mode.... <<<<<<<<<<<<<")
   else:
      cfg['make_extension']+=".SEQ"

   # print("=================================================================================")
   # print(cfg['make_extension'])
   # print("=================================================================================")

   # 1.2. ----- start a wizard
   # ... perhaps one day !
   os.environ['ASTER_ROOT'] = cfg['ASTER_ROOT']

   # 1.3.1. ----- configure standard directories
   # {bin,lib,inc}dirs are used to search files
   # Search first from ASTER_ROOT/public/{bin,lib,include}
   # and ASTER_ROOT/public is added for recursive search.
   bindirs=[os.path.join(cfg['ASTER_ROOT'],'public','bin'),
            os.path.join(cfg['ASTER_ROOT'],'public'),]
   bindirs.extend(os.environ.get('PATH', '').strip(':').split(':'))
   bindirs.extend(['/usr/local/bin', '/usr/bin', '/bin',
                   '/usr/X11R6/bin', '/usr/bin/X11', '/usr/openwin/bin',])

   libdirs=[os.path.join(cfg['ASTER_ROOT'],'public','lib'),
            os.path.join(cfg['ASTER_ROOT'],'public'),]
   libdirs.extend(os.environ.get('LD_LIBRARY_PATH', '').strip(':').split(':'))
   libdirs.extend(['/usr/local/lib', '/usr/lib', '/lib',
                   '/usr/lib/x86_64-linux-gnu',
                   '/usr/X11R6/lib', '/usr/lib/X11', '/usr/openwin/lib',])

   incdirs=[os.path.join(cfg['ASTER_ROOT'],'public','include'),
            os.path.join(cfg['ASTER_ROOT'],'public'),]
   incdirs.extend(os.environ.get('INCLUDE', '').split(':'))
   incdirs.extend(['/usr/local/include', '/usr/include', '/include',
                   '/usr/X11R6/include', '/usr/include/X11', '/usr/openwin/include',])

   # 1.3.2. ----- convert uname value to MUMPS Benchmarks terminology...
   sysname, nodename, release, version, machine = os.uname()
   log._print('Architecture : os.uname = %s' % str(os.uname()), DBG=True)
   plt = sys.platform
   log._print('Architecture : sys.platform = %s    os.name = %s' % (plt, os.name), DBG=True)

   sident = ' '.join(os.uname())
   if os.path.isfile('/etc/issue'):
      sident = re.sub(r'\\.', '', open('/etc/issue', 'r').read()) + sident
   log._print(_separ, """Installation on :
%s""" % sident, _separ)

   common_libs = ['pthread', 'z']
   cfg['PLATFORM'] = plt
   if plt.startswith('linux'):
       plt = 'linux'
   if plt == 'win32':
      cfg['IFDEF'] = 'WIN32'
   elif plt in ('linux', 'cygwin'):
      cfg['ARCH'] = 'x86'
      if machine.endswith('64'):
         cfg['IFDEF'] = 'LINUX64'
         if machine in ('x86_64', 'ia64', 'ppc64'):
            cfg['ARCH'] = machine
         else: # force to x86_64
            cfg['ARCH'] = 'x86_64'
      else:
         cfg['IFDEF'] = 'LINUX'
   elif plt == 'darwin':
      cfg['ARCH'] = 'x86'
      if machine.endswith('64'):
         cfg['IFDEF'] = 'DARWIN64'
         if machine in ('x86_64', 'ia64', 'ppc64'):
            cfg['ARCH'] = machine
         else: # force to x86_64
            cfg['ARCH'] = 'x86_64'
      else:
         cfg['IFDEF'] = 'DARWIN'
   elif plt.startswith('freebsd'):
      common_libs = []
      cfg['IFDEF']='FREEBSD'
      cfg['ARCH'] = 'x86'
      if machine.endswith('64'):
         if machine in ('x86_64', 'ia64', 'ppc64'):
            cfg['ARCH'] = machine
         else: # force to x86_64
            cfg['ARCH'] = 'x86_64'
   elif plt.startswith('osf1'):
      cfg['IFDEF']='TRU64'
   elif plt == 'sunos5':
      cfg['IFDEF'] = 'SOLARIS'
   # elif plt.startswith('irix64'):
   #    cfg['IFDEF']='IRIX64'
   elif plt.startswith('irix'):
      cfg['IFDEF'] = 'IRIX'
   else:
       raise SetupError(_("Unsupported platform : sys.platform=%s, os.name=%s") % \
             (sys.platform, os.name))
   if cfg.get('_solaris64', False) and plt == 'sunos5':
      cfg['IFDEF'] = 'SOLARIS64'
   cfg['DEFINED'] = cfg['IFDEF']

   # ----- insert 'lib64' at the beginning on 64 bits platforms
   if cfg['IFDEF'].endswith('64'):
      libdirs = [path.replace('lib', 'lib64') for path in libdirs \
                    if path.find('lib') > -1 and path.find('lib64') < 0 ] + libdirs
   bindirs = cfg.get('BINDIR', []) + bindirs
   libdirs = cfg.get('LIBDIR', []) + libdirs
   incdirs = cfg.get('INCLUDEDIR', []) + incdirs

   # 1.3.3. ----- variables with predefined value
   cfg['ASTER_VERSION']   = cfg.get('ASTER_VERSION', __aster_version__)
   cfg['ASTER_VERSLABEL'] = cfg.get('ASTER_VERSLABEL', dict_prod_param['mumps-bench-verslabel'])

   cfg['NODE']       =cfg.get('NODE', nodename.split('.')[0])

   cfg['HOME_PYTHON']=cfg.get('HOME_PYTHON', os.path.abspath(sys.prefix))
   cfg['PYTHON_EXE'] =cfg.get('PYTHON_EXE', sys.executable)
   # these directories should respectively contain shared and static librairies
   pylib = SC.get_python_lib(standard_lib=True)
   prefixlib = osp.dirname(pylib)
   cfg['PYTHONLIB']  ='-L' + prefixlib + ' -L'+osp.join(pylib, 'config') + \
      ' -l' + pythonXY
   # python modules location
   cfg['PYTHONPATH'] = cfg.get('PYTHONPATH', '')
   cfg['OPT_ENV'] = cfg.get('OPT_ENV', '')

   #-------------------------------------------------------------------------------
   # 1.4. ----- auto-configuration
   #-------------------------------------------------------------------------------
   log._print(_separ, term='')

   # 1.4.0. ----- checking for maximum command line length (as configure does)
   log._print(_fmt_search % _('max command length'), term='')
   system=SYSTEM({ 'verbose' : verbose, 'debug' : False },
         **{'maxcmdlen' : 2**31, 'log':log})
   system.AddToEnv(cfg['OPT_ENV'], verbose=False)
   default_value=1024
   lenmax=0
   i=0
   teststr='ABCD'
   iret=0
   while iret==0:
      i+=1
      cmd='echo '+teststr
      iret, out = system.local_shell(cmd, verbose=False)
      out=out.replace('\n','')
      if len(out)<>len(teststr) or len(teststr)>2**16:
         lenmax=len(teststr)/2
         break
      teststr=teststr*2
   # Add a significant safety factor because C++ compilers can tack on massive
   # amounts of additional arguments before passing them to the linker.
   # It appears as though 1/2 is a usable value.
   system.MaxCmdLen=max(default_value, lenmax/2)
   log._print(system.MaxCmdLen)
   cfg['MAXCMDLEN']=system.MaxCmdLen
   system.debug = debug

   # ----- initialize DEPENDENCIES object
   dep=DEPENDENCIES(
      cfg=cfg,
      cache=cache_file,
      debug=debug,
      system=system,
      log=log)

   # ----- initialize FIND_TOOLS object
   ftools=FIND_TOOLS(log=log,
         maxdepth=cfg.get('MAXDEPTH', 5),
         use_locate=cfg.get('USE_LOCATE', False),
         prefshared=cfg.get('PREFER_SHARED_LIBS', False),
         debug=debug,
         system=system,
         arch=cfg.get('ARCH'),
         bindirs=bindirs,
         libdirs=libdirs,
         incdirs=incdirs,
         noerror=_test)

   # 1.4.0a. ----- system info
   ftools.check(' '.join([sysname, '/', os.name, '/', cfg['ARCH']]), 'architecture')
   ftools.get_cpu_number()
   ftools.check(cfg['IFDEF'], 'MUMPS Benchmarks platform type')

   # 1.4.1a. ----- checking for shell script interpreter
   ftools.find_and_set(cfg, 'SHELL_EXECUTION', ['bash', 'ksh', 'zsh'], err=False)
   ftools.check(python_version, 'Python version')

   # 1.4.1b. ----- check for popen/threading bug :
   if sys.hexversion >= 0x020700F0:
       response = True
   else:
       from check_popen_thread import main
       response = ftools.check(main, 'Python multi-threading')
   cfg['MULTITHREADING'] = response

   # 1.4.1d. ----- check for mpirun command
   #ftools.find_and_set(cfg, 'MPIRUN', ['mpirun', 'prun'], err=False)
   cfg['MPIRUN'] = cfg.get('MPIRUN', 'mpirun')

   # 1.4.1e. ----- check for gcc libraries path
   cc = cfg.get('CC')
   if cc is None or not ftools.check_compiler_name(cc, 'GCC'):
      cc = 'gcc'
   ftools.find_and_set(cfg, 'gcc', cc)
   if cfg.get('gcc'):   # for 'test' mode
      ftools.GccPrintSearchDirs(cfg['gcc'])

   # 1.4.1f. ----- check for system libraries
   math_lib = cfg.get('MATH_LIST', [])
   if not type(math_lib) in (list, tuple):
      math_lib = [math_lib,]
   sys_lib = []
   for glob_lib in common_libs:
      cfg['__tmp__'] = ''
      del cfg['__tmp__']
      ftools.findlib_and_set(cfg, '__tmp__', glob_lib, prefshared=True, err=False, silent=False)
      if cfg.get('__tmp__'):
         ftools.AddToCache('lib', glob_lib, cfg['__tmp__'])
         sys_lib.append(glob_lib)

   # 1.4.1g. ----- check for system dependent libraries (and only used by MUMPS Benchmarks)
   cfg['SYSLIB'] = cfg.get('SYSLIB', '')
   aster_sys_lib = []
   if cfg['IFDEF'] in ('LINUX', 'P_LINUX', 'LINUX64'):
      cfg['SYSLIB'] += ' -Wl,--allow-multiple-definition -Wl,--export-dynamic'
      aster_sys_lib.extend(['dl', 'util', 'm'])
   elif cfg['IFDEF'] == 'TRU64':
      aster_sys_lib.extend('/usr/lib/libots3.a /usr/lib/libpthread.a /usr/lib/libnuma.a ' \
                           '/usr/lib/libpset.a  /usr/lib/libmach.a -lUfor -lfor -lFutil -lm ' \
                           '-lots -lm_c32 -lmld /usr/ccs/lib/cmplrs/cc/libexc.a'.split())
   elif cfg['IFDEF'] == 'SOLARIS':
      aster_sys_lib.extend(['socket', 'nsl', 'm', '/usr/lib/libintl.so.1', 'dl', 'c'])
   elif cfg['IFDEF'] == 'SOLARIS64':
      aster_sys_lib.extend(['socket', 'nsl', 'm', 'dl', 'c', 'm'])
   elif cfg['IFDEF'] == 'IRIX':
      aster_sys_lib.extend(['fpe', 'm'])
   else:
      pass
   list_lib = []
   for glob_lib in aster_sys_lib:
      cfg['__tmp__'] = ''
      del cfg['__tmp__']
      ftools.findlib_and_set(cfg, '__tmp__', glob_lib, prefshared=True,
                             err=not opts.ign_err, silent=False)
      if cfg.get('__tmp__'):
         ftools.AddToCache('lib', glob_lib, cfg['__tmp__'])
         list_lib.append(cfg['__tmp__'])
   cfg['SYSLIB'] += ' ' + ' '.join(list_lib)
   cfg['SYSLIB'] = cfg['SYSLIB'].strip()

   # 1.4.2. ----- check for compilers
   cfg_ini = cfg.copy()
   dict_pref = dict([(k.replace('PREFER_COMPILER_', ''), v) \
                        for k, v in cfg.items() if k.startswith('PREFER_COMPILER')])
   if not dict_pref.get('PREFER_COMPILER'):
      dict_pref['PREFER_COMPILER'] = 'GNU'

   from check_compilers import COMPILER_MANAGER
   compiler_manager = COMPILER_MANAGER(debug, print_func=log._print)
   lkeys = dict_pref.keys()
   lkeys.sort()
   log._print('PREFER_COMPILER keys : %s' % lkeys, DBG=True)

   # general compiler options
   compiler_option = []
   if cfg.get('USE_FPIC', True):
      compiler_option.append('-fPIC')

   for prod in lkeys:
      prefcompiler = dict_pref[prod]
      log._print(_separ, term='')
      if prod == 'PREFER_COMPILER':
         lprod = [p for p in dict_pref.keys() if p != prod]
         if len(lprod) > 0:
            sprod = ' except %s' % ', '.join(lprod)
         else:
            sprod = ''
         ftools.check(None, 'default compiler (for all products%s)' % sprod)
         prod = '__main__'
      else:
         ftools.check(None, 'compiler for "%s"' % prod)
      success = compiler_manager.check_compiler(name=prefcompiler,
                               product=prod,
                               system=system, ftools=ftools,
                               necessary=('CC', 'CXX', 'F90'),
                               init=cfg_ini,
                               platform=cfg['IFDEF'],
                               arch=cfg.get('ARCH', ''),
                               math_lib=math_lib,
                               sys_lib=sys_lib,
                               add_option=compiler_option)
      if not success:
         log._print(_separ, term='')
         log._print(_('Unable to configure automatically %s compiler for "%s" product.') % (prefcompiler.upper(), prod))
         return
      else:
         txt = compiler_manager.switch_in_dep(dep, prod, system=system, verbose=True)
         log._print(os.linesep, 'Compiler variables (set as environment variables):', os.linesep)
         log._print(txt)
      if debug:
         from pprint import pprint
         pprint(compiler_manager.get_config(prod))

   # activate main compiler
   compiler_manager.switch_in_dep(dep, product='__main__', system=system, verbose=False)

   # 1.4.3. ----- check for ps commands :
   #  PS_COMMAND_CPU returns (field 1) cputime and (field 2) command line
   #  PS_COMMAND_PID returns (field 1) pid and (field 2) command line
   log._print(_separ, term='')
   ftools.find_and_set(cfg, 'PS_COMMAND', 'ps',  err=False)
   ps_command = cfg.get('PS_COMMAND')
   if ps_command != None:
      if cfg['IFDEF'].find('SOLARIS') > -1:
         cfg['PS_COMMAND_CPU'] = '%s -e -otime -oargs' % ps_command
         cfg['PS_COMMAND_PID'] = '%s -e -opid -oargs' % ps_command
      elif cfg['IFDEF'].find('IRIX') > -1 or cfg['IFDEF'] == 'TRU64':
         cfg['PS_COMMAND_CPU'] = '%s -e -ocputime -ocommand' % ps_command
         cfg['PS_COMMAND_PID'] = '%s -e -opid -ocommand' % ps_command
      elif plt == 'darwin':
         # per man page for Mac OS X (darwin) ps command
         # if -w option is specified more than once, ps will use as many columns as necessary without
         # regard for your window size.  When output is not to a terminal, an unlimited number of
         # columns are always used.
         cfg['PS_COMMAND_CPU'] = '%s -e -w -w -ocputime -ocommand' % ps_command
         cfg['PS_COMMAND_PID'] = '%s -e -w -w -opid -ocommand' % ps_command
      else:
         cfg['PS_COMMAND_CPU'] = '%s -e --width=512 -ocputime -ocommand' % ps_command
         cfg['PS_COMMAND_PID'] = '%s -e --width=512 -opid -ocommand' % ps_command

   # 1.4.4. ----- check for a terminal
   ListTerm=[
      ['xterm' , 'xterm -e @E',],
      ['gnome-terminal' , 'gnome-terminal --command=@E',],
      ['konsole', 'konsole -e @E'],]
   for prg, cmd in ListTerm:
      term = ftools.find_file(prg, typ='bin')
      if term != None:
         term = cmd.replace(prg, term)
         break
   cfg['TERMINAL'] = cfg.get('TERMINAL', term)
   if cfg['TERMINAL'] is None:
      del cfg['TERMINAL']

   # 1.4.5. ----- check for a text editor
   ListEdit=[
      ['nedit' , 'nedit',],
      ['geany' , 'geany',],
      ['gvim'  , 'gvim',],
      ['gedit' , 'gedit',],
      ['kwrite', 'kwrite',],
      ['xemacs', 'xemacs',],
      ['emacs' , 'emacs',],
      ['xedit' , 'xedit',],
      ['vi'    , cfg.get('TERMINAL', 'xterm')+' -e vi',],]
   for prg, cmd in ListEdit:
      edit = ftools.find_file(prg, typ='bin')
      if edit != None:
         edit = cmd.replace(prg, edit)
         break
   cfg['EDITOR'] = cfg.get('EDITOR', edit)
   if cfg['EDITOR'] == None:
      del cfg['EDITOR']

   # 1.4.6. ----- check for debugger
   #  DEBUGGER_COMMAND runs an interactive debugger
   #  DEBUGGER_COMMAND_POST dumps a post-mortem traceback
   #     @E will be remplaced by the name of the executable
   #     @C will be remplaced by the name of the corefile
   #     @D will be remplaced by the filename which contains "where+quit"
   #     @d will be remplaced by the string 'where ; quit'
   cfg['DEBUGGER_COMMAND'] = ''
   cfg['DEBUGGER_COMMAND_POST'] = ''
   ListDebbuger=[
      ['gdb',     '%s -batch --command=@D @E @C',],
      ['dbx',     '%s -c @D @E @C',],
      ['ladebug', '%s -c @D @E @C',],]
   for debugger, debugger_command_format in ListDebbuger:
      debugger_command = ftools.find_file(debugger, typ='bin')
      if debugger_command != None:
         cfg['DEBUGGER_COMMAND_POST'] = debugger_command_format % debugger_command
         break

   if debugger_command != None:
      ddd = ftools.find_file('ddd', typ='bin')
      if ddd != None:
         cfg['DEBUGGER_COMMAND'] = '%s --%s --debugger %s --command=@D @E @C' \
            % (ddd, debugger, debugger_command)

   # 1.4.7. ----- check for utilities (for scotch/ptscotch)
   ftools.find_and_set(cfg, 'FLEX', 'flex', err=False)
   ftools.find_and_set(cfg, 'RANLIB', 'ranlib', err=False)
   ftools.find_and_set(cfg, 'YACC', 'bison', err=False)
   if cfg.get('YACC') and cfg.get('YACC', '').find('-y') < 0:
      cfg['YACC'] += ' -y'
   if not opts.ign_err and 'scotch' in to_install \
      and (not cfg.get('FLEX') or not cfg.get('RANLIB') or not cfg.get('YACC')):
      to_install.remove('scotch')

   if not opts.ign_err and 'ptscotch' in to_install \
      and (not cfg.get('FLEX') or not cfg.get('RANLIB') or not cfg.get('YACC')):
      to_install.remove('ptscotch')


   #-------------------------------------------------------------------------------
   # 1.5. ----- products configuration
   #-------------------------------------------------------------------------------
   log._print(_separ, term='')

   # 1.5.1. ----- check for hostname (for client part of astk)
   log._print(_fmt_search % _('host name'), term='')
   host=system.GetHostName()
   # deduce domain name
   tmp=host.split('.')
   if len(tmp)>1:
      host=tmp[0]
      domain='.'.join(tmp[1:])
   else:
      domain=''
   cfg['SERVER_NAME']=cfg.get('SERVER_NAME', host)
   cfg['DOMAIN_NAME']=cfg.get('DOMAIN_NAME', domain)
   cfg['FULL_SERVER_NAME']=cfg.get('FULL_SERVER_NAME', '.'.join(tmp))
   domain=cfg['DOMAIN_NAME']
   if domain=='':
      domain='(empty)'
   log._print(cfg['SERVER_NAME'])
   log._print(_fmt_search % _('network domain name'), domain)
   log._print(_fmt_search % _('full qualified network name'), cfg['FULL_SERVER_NAME'])

   #-------------------------------------------------------------------------------
   # 1.6. ----- optional tools/libs
   #-------------------------------------------------------------------------------
   # 1.6.1. ----- check for F90 compiler : is now compulsory

   # 1.6.2. ----- optional packages for aster
   # hdf5
   # cfg['HOME_HDF']    = cfg.get('HOME_HDF', '')
   # med
   # cfg['HOME_MED']    = cfg.get('HOME_MED', '')
   # MUMPS
   cfg['HOME_MUMPS']  = cfg.get('HOME_MUMPS', '')
   # MFRONT
   # cfg['HOME_MFRONT']   = cfg.get('HOME_MFRONT', '')
   # SCOTCH
   cfg['HOME_SCOTCH'] = cfg.get('HOME_SCOTCH', '')
   # MPI
   cfg['HOME_MPI']    = cfg.get('HOME_MPI', '')

   # 1.6.4. ----- mumps
   cfg['INCLUDE_MUMPS'] = cfg.get('INCLUDE_MUMPS',
                                  'include_mumps-%s' % dict_prod['mumps'])

   # 1.6.5. ----- grace 5
   grace_add_symlink = False
   if not opts.ign_err and 'grace' in to_install:
      ftools.find_and_set(cfg, 'XMGRACE', ['xmgrace', 'grace'], err=False)
      if cfg.get('XMGRACE'):
         # try to use grace instead of xmgrace that does not work without DISPLAY
         ftools.find_and_set(cfg, 'GRACEBAT', ['grace', 'gracebat'], err=False)
         grace = cfg.get('GRACEBAT', cfg['XMGRACE'])
         iret, out, outspl = ftools.get_product_version(grace, '-version')
         vers = None
         svers = '?'
         mat = re.search('(Grace.*?)([0-9\.]+)', out, re.MULTILINE)
         if mat is not None:
            vers = mat.group(2).strip('.').split('.')
            try:
               vers = [int(v) for v in vers]
               svers = '.'.join([str(i) for i in vers])
            except:
               vers = None
            log._print('XMGRACE', ''.join(mat.groups()), ': version', vers, DBG=True)
         if vers is not None and vers < [5, 90]:
            res = 'version is %s : ok. Do not need compile grace from sources.' % svers
            to_install.remove('grace')
            grace_add_symlink = True
         else:
            res = 'version is %s. Trying to compile grace from sources.' % svers
         ftools.check(res, 'Grace version < 5.99')

   # 1.6.6. ----- OS X
   if plt == 'darwin':
      # gmsh and homard are x86 binaries
      for prod in ('gmsh', 'homard'):
          if prod in to_install:
             to_install.remove(prod)

   #-------------------------------------------------------------------------------
   # 2. dependencies
   #-------------------------------------------------------------------------------
   # 2.1. ----- add in DEPENDENCIES instance values set by __main__...
   dep.Add(product='__main__',
           set=[k for k in cfg.keys() if not k in cfg_init_keys],)

   # 2.2. ----- ... and during configuration step
   dep.Add(product='__cfg__',
      set=cfg_init_keys)
   dep.FillCache()

   #-------------------------------------------------------------------------------
   # 2.99. ----- stop here if 'test'
   err = False
   if not os.path.exists(cfg['ASTER_ROOT']):
      try:
         os.makedirs(cfg['ASTER_ROOT'])
      except OSError:
         err = True
   if not os.path.exists(osp.join(cfg['ASTER_ROOT'], 'bin')):
      try:
         os.makedirs(osp.join(cfg['ASTER_ROOT'], 'bin'))
      except OSError:
         err = True
   err = err or not os.access(cfg['ASTER_ROOT'], os.W_OK)
   if err:
      log._print(_separ, term='')
      log._print(_('No write access to %s.\nUse --aster_root=XXX to change destination directory.') % cfg['ASTER_ROOT'])
      return

   t_ini = time.time() - t_ini
   if _test:
      print
      print 'Stop here !'
      print 'Settings are saved in setup.cache. Remove it if you change something.'
      return
   else:
      print
      log._print(_separ, term='')
      if cfg['F90'] == '':
          log._print(get_install_message('gfortran', 'a fortran 90 compiler'))
          raise SetupError(_("Error: no fortran90 compiler found !"))

      if noprompt:
         log._print('Continue without prompting.')
      else:
         log._print(_("Check if found values seem correct. If not you can change them using 'setup.cfg'."))
         should_continue()

   t_ini = time.time() - t_ini

   #-------------------------------------------------------------------------------
   # 4. products installation
   #-------------------------------------------------------------------------------

   #-------------------------------------------------------------------------------
   # product for which full installation is required
   summary=SUMMARY(to_install, system=system, log=log, t_ini=t_ini)
   summary.SetGlobal(cfg['ASTER_ROOT'], '')

   for product in to_install:
      alias = product_alias(product)
      if cfg.get('_install_' + alias, product in to_install):
         t0=time.time()
         setup=None
         if hasattr(products, 'setup_%s' % alias):
            txt = compiler_manager.switch_in_dep(dep,
                     product=alias,
                     system=system,
                     verbose=True)
            log._print(_separ, _('Compiler variables for %s (set as environment variables):') % product)
            log._print(txt)
            log._print()
            # export environment
            ftools.AddToPathVar(dep.cfg, 'PATH', None)
            ftools.AddToPathVar(dep.cfg, 'LD_LIBRARY_PATH', None)
            system.AddToEnv(dep.cfg['OPT_ENV'], verbose=False)
            #
            setup=getattr(products, 'setup_%s' % alias)(**{
               'dep'             : dep,
               'summary'         : summary,
               'verbose'         : verbose,
               'debug'           : debug,
               'system'          : system,
               'find_tools'      : ftools,
               'log'             : log,
               'reinstall'       : opts.reinstall,
            })
         else:
            raise SetupError(_('Setup script for %s not available.') % product)
         try:
            if not _test:
               setup.Go()
            else:
               setup.PreCheck()
         except safe_exceptions, msg:
            log._print(_fmt_err % msg)
         # how to continue if failed
         if setup.exit_code != 0:
            setup.IfFailed()
         dt=time.time()-t0
         summary.Set(product, setup, dt, sys.exc_info()[:2])

   #-------------------------------------------------------------------------------
   # 5. Summary
   #-------------------------------------------------------------------------------
   summary.Print()

   # 6. Clean up
   ftools.clear_temporary_folder()


def seedetails():
   print '\n'*2 + \
      _('Exception raised. See %s file for details.') % repr(log_file)


#-------------------------------------------------------------------------------
if __name__ == '__main__':
   try:
      main()
   except SystemExit, msg:
      log._print(msg)
      seedetails()
      sys.exit(msg)
   except:
      traceback.print_exc()
      seedetails()
   log.close()
