"""
Configure compilers
"""

import sys
import os
import shutil
import popen2
import re
from glob   import glob
from pprint import pprint, pformat
from as_setup import SetupError, SetupConfigureError, should_continue

# ----- differ messages translation
def _(mesg): return mesg


trivial_src = {
   'CC'  : """void trivial() {}
""",
   'F90' : """
program trivial
end
"""
}

dict_ext = {
   'CC'  : 'c',
   'F90' : 'F90',
}

dict_info = {
   '.c'    : { 'compiler' : 'CC',  'flags' : 'CFLAGS',   },
   '.F90'  : { 'compiler' : 'F90', 'flags' : 'F90FLAGS', },
   'a.out' : { 'compiler' : 'LD',  'flags' : 'LDFLAGS',  },
}

d_name = { 'math' : 'MATHLIB', 'cxx' : 'CXXLIB', 'sys' : 'OTHERLIB' }


class CheckCompilerError(SetupError):
   pass


class CONFIGURE_COMPILER:
   """Search for compilers."""

   def __init__(self, **kargs):
      """Initialization."""
      self.compilers = ['CC', 'CXX', 'F90']
      self.profiles  = []
      self.libs      = []                             # list of (label, lib, necessary=True)
      for typ in ('sys', 'math'):
         for lib in kargs.get('%s_lib' % typ, []):
            self.libs.append((typ, lib))
#      self.necessary = kargs.get('necessary', self.compilers[:] + [k for k, v in self.libs])
      self.necessary = kargs['necessary']

      self._ext_static  = '.a'
      self._ext_shared  = '.so'
      if sys.platform in ("win32", "cygwin"):
          self._ext_static = self._ext_shared = '.lib'  # but not yet supported!
      elif sys.platform == 'darwin':
          self._ext_shared = '.dylib'

      # external methods
      system = kargs.get('system')
      if system is None:
         raise CheckCompilerError(_("Argument not found 'system'"))
      self.debug      = system.debug
      self.Shell      = system.local_shell
      self.AddToEnv   = system.AddToEnv

      self.ftools = kargs.get('ftools')
      if self.ftools is None:
         raise CheckCompilerError(_("Argument not found 'ftools'"))
      self.prefshared      = self.ftools.prefshared
      self._print          = self.ftools._print
      self.fcheck          = self.ftools.check
      self.maxdepth        = self.ftools.maxdepth

      # platform
      self.platform = kargs['platform']
      self.arch     = kargs['arch']
      tmpdir = kargs.get('tmpdir', os.environ.get('TMPDIR', '/tmp'))
      self.tmpdir = os.path.join(tmpdir, 'check_compilers.%s' % os.getpid())
      if not os.path.exists(self.tmpdir):
         os.makedirs(self.tmpdir)

      self.cfg = {}
      # values (libs) used with all compilers
      self.cfg_add_global = {}
      self.init_cfg = self.compilers + \
            ['LD', 'DEFINED',
             'CFLAGS',     'F90FLAGS',     'CXXFLAGS',
             'CFLAGS_DBG', 'F90FLAGS_DBG', 'CXXFLAGS_DBG',
             'LDFLAGS',    'F90FLAGS_I8']
      # initial configuration (from setup.cfg)
      self.init_value = kargs['init'].copy()

      # compiler options to add
      self.add_option = kargs.get('add_option', [])

      self.count_error = 0
      self.env_files = []
      self.__numlib = 0
      self.compiler_version = {}

   def is_64bits(self):
       return self.platform and self.platform.find('64') > -1

   def clean(self):
      os.system('rm -rf %s' % self.tmpdir)

   def find_compilers(self):
      """Find compilers."""
      for var in self.compilers:
         # set in setup.cfg ?
         ini = self.check_init_value(var)
         # if ini is not None:
         if ini is None:
            continue
         searched = getattr(self, var)
         try:
            self.ftools.find_and_set(self.cfg, var, searched, typ='bin',
                                     err=True, append=False, maxdepth=self.maxdepth)
            l1, lspl = self.ftools.check_compiler_version(self.cfg[var])
            self.set_compiler_version(var, lspl)
         except SetupConfigureError, reason:
            if var in self.necessary:
               self.count_error += 1
               self._print(_('ERROR #%d:') % self.count_error, reason)
            else:
               self._print(_('WARNING :'), reason)

   def set_compiler_version(self, var, fields):
      """Stores compiler version."""
      vers = None
      if len(fields) >= 3:
         val = fields[2]
         vers = ''.join([c for c in val if c == '.' or c.isdigit()])
         vers = vers.strip('.').strip().split('.')
         try:
            vers = [int(v) for v in vers]
         except:
            vers = None
         self._print('compiler_version', var, repr(fields), vers, DBG=True)
      self.compiler_version[var] = vers

   def check_init_value(self, var, set_in=None):
      """Check for initial values given through setup.cfg.
      """
      ini = self.init_value.get(var)
      if ini is not None:
         if set_in is None:
            self.cfg[var] = ini
         else:
            set_in[var] = ini
         self.fcheck(ini, '%s from setup.cfg' % var)
      self._print('Checking for initial value for %s... %s' % (var, ini or 'empty'), DBG=True)
      return ini

   def create_key_from(self, what):
      """Produce a clean key from a list of libs to search.
      """
      key = what
      if type(key) in (list, tuple):
         key = key[0].split('.')[0]
      key = re.sub('[\-\+\*/@+\.]+', '', key)
      return key

   def find_libs(self, lib=None):
      """Find libraries."""
      search_libs = self.libs
      if lib:
         search_libs = [lib,]
      vus = {}
      for name in d_name.keys():
         # set in setup.cfg ?
         if vus.get(name) is None:
            ini = self.check_init_value(d_name.get(name))
            if ini is not None:
               vus[name] = True
               self.cfg['__LIBS_%s_%03d_%s' % (name, 0, 'init_value')] = ini
               continue
         else:
            continue

      for args in search_libs:
         necessary = True
         name, what = args[:2]
         if len(args) > 2:
            necessary = args[2]
         # set in setup.cfg ?
         if vus.get(name) is not None:
            continue
         self.__numlib += 1
         what_key = self.create_key_from(what)
         cfg_key = '__LIBS_%s_%03d_%s' % (name, self.__numlib, what_key)
         try:
            self.ftools.findlib_and_set(self.cfg, cfg_key, what,
                     err=True, append=True, maxdepth=self.maxdepth,
                     prefshared=self.prefshared)
         except SetupConfigureError, reason:
            if necessary:
               self.count_error += 1
               self._print(_('ERROR #%d:') % self.count_error, reason)
            else:
               self._print(_('WARNING (optional):'), reason)

   def check_env(self):
      """Check for environment profiles."""
      # OPT_ENV
      opt_env = [self.cfg.get('OPT_ENV', '')]
      for prof in self.env_files:
         opt_env.append('. %s' % prof)
      opt_env.append('')

      self.cfg['OPT_ENV'] = os.linesep.join(opt_env)
      self.AddToEnv(self.cfg['OPT_ENV'], verbose=False)

   def after_compilers(self):
      """After searching compilers, this allows to add libs to search
      according to compiler version..."""
      pass

   def after_libs(self):
      """After searching libs, this allows to add a flag to ld or..."""
      pass

   def add_on(self):
      """After searching compilers, libs... search again other bin or lib."""
      pass

   def init_flags(self):
      """Init compiler options."""
      for key in self.init_cfg:
         self.cfg[key]             = self.cfg.get(key, '')
      ini = self.check_init_value('LD')
      if ini is None:
         self.cfg['LD'] = self.cfg['F90']

   def insert_option(self, option):
      """Insert option string in CFLAGS, F90FLAGS if where is True
      or only one of these.
      """
      if not option in self.add_option:
         return
      lkey = ('CFLAGS', 'F90FLAGS')
      for k in lkey:
         self.cfg[k] += ' ' + option

   def set_flags(self):
      """Set compiler options."""
      pass

   def check_init_flags(self):
      """Overwrites compiler options by setup.cfg."""
      for key in ('CFLAGS', 'F90FLAGS',
                  'CFLAGS_DBG', 'F90FLAGS_DBG',
                  'LDFLAGS'):
         ini = self.check_init_value(key)

   def check_ok(self):
      """Returns False if an error occurred."""
      ok = True
      for attr in self.necessary:
         val = self.cfg.get(attr)
         if not val:
            ok = False
            break
      if self.count_error > 0:
         ok = False
      return ok

   def final(self):
      """The end."""
      # test blas/lapack
      from check_compilers_src import blas_lapack
      result, errmsg = self.run_test(blas_lapack)
      result = self.fcheck(result, 'C/fortran program using blas/lapack')
      if not result:
         self._print('---------- ERROR MESSAGE ----------', os.linesep, errmsg)
         self._print(blas_lapack['__error__'])
         should_continue()
      # add to global (g2c/gfortran must be used by aster compiled with Intel)
      for k, v in self.cfg.items():
         if    re.search('__LIBS_math_[0-9]+_g2c',      k) is not None \
            or re.search('__LIBS_math_[0-9]+_gfortran', k) is not None:
            self.cfg_add_global[k] = v

   def run(self):
      """Runs the configure."""
      self.fcheck(None, self.__doc__)
      self.find_compilers()
      if not self.check_ok():
         return
      self.after_compilers()
      if not self.check_ok():
         return
      self.find_libs()
      if not self.check_ok():
         return
      self.after_libs()
      if not self.check_ok():
         return
      self.check_env()
      if not self.check_ok():
         return
      self.add_on()
      if not self.check_ok():
         return
      self.init_flags()
      self.set_flags()
      if not self.check_ok():
         return
      self.check_init_flags()
      self.final()
      self.clean()

   def diag(self):
      diag = self.check_ok()
      if not diag:
         diag = '%d error(s) (see previous ERROR)' % self.count_error
      self.fcheck(diag, self.__doc__)

   def test_compil(self, lang, args='', src=None, verbose=None):
      """Test a compiler."""
      if verbose is None:
         verbose = self.debug
      ext = dict_ext[lang]

      prev = os.getcwd()
      tmp = os.path.join(self.tmpdir, 'test_compil')
      os.mkdir(tmp)
      os.chdir(tmp)

      fsrc = 'test_compil.%s.%s' % (os.getpid(), ext)
      open(fsrc, 'w').write(src or trivial_src[lang])
      cmd = '%s -c %s %s' % (self.cfg[lang], args, fsrc)
      iret, out = self.Shell(cmd, verbose=verbose)
      self._print('command line: %s' % cmd, 'output :', out, DBG=True)

      os.chdir(prev)
      shutil.rmtree(tmp)
      return iret == 0

   def get_cmd_compil(self, fsrc, integer8):
      """Returns command line for compiling 'fsrc'."""
      di = {}
      if fsrc != 'a.out':
         root, ext = os.path.splitext(fsrc)
         di['src'] = '-c %s' % fsrc
         di['res'] = root + '.o'
         sdefs = ['', self.platform,] + self.cfg['DEFINED'].split()
         di['defs'] = ' -D'.join(sdefs)
      else:
         ext = 'a.out'
         di['src'] = ' '.join(glob('*.o'))
         di['res'] = 'a.out'
         sorted_keys = self.cfg.keys()      # to preserve libs order
         sorted_keys.sort()
         for k in sorted_keys:
            if k.startswith('__LIBS_'):
               di['src'] += ' ' + self.cfg[k]
         di['defs'] = ''
      for what, key in dict_info[ext].items():
         di[what] = self.cfg[key]
         if integer8 and self.cfg.get(key + '_I8'):
            di[what] += self.cfg[key + '_I8']
      cmd = '%(compiler)s -o %(res)s %(defs)s %(flags)s %(src)s' % di
      self._print('get_cmd_compil returns : ', cmd, DBG=True)
      return cmd

   def run_test(self, dict_src):
      """Compiling a program."""
      prev = os.getcwd()
      tmp = os.path.join(self.tmpdir, 'run_test')
      if os.path.exists(tmp):
          shutil.rmtree(tmp)
      os.mkdir(tmp)
      os.chdir(tmp)
      iret = 0
      dkw = { 'INTEGER_SIZE' : 4 }
      integer8 = dict_src.get('__integer8__', False)
      if integer8 and self.is_64bits():
          dkw['INTEGER_SIZE'] = 8
      # compilation of source files
      for fich, src in dict_src.items():
         if fich.startswith('__'):
            continue
         open(fich, 'w').write(src % dkw)
         iret, out = self.Shell(self.get_cmd_compil(fich, integer8), verbose=self.debug)
         if iret != 0:
            break
      # link
      if iret == 0:
         iret, out = self.Shell(self.get_cmd_compil('a.out', integer8), verbose=self.debug)
      # run a.out
      if iret == 0:
         iret, out = self.Shell('./a.out', verbose=self.debug)
      os.chdir(prev)
      if iret == 0:
         shutil.rmtree(tmp)
      else:
         self._print('working directory is :', tmp, DBG=True)
      return iret == 0, out


class GNU_COMPILER(CONFIGURE_COMPILER):
   """GNU compilers"""
   CC  = 'gcc'
   CXX = 'g++'
   F90 = 'gfortran'

   def __init__(self, **kargs):
      """Initialization."""
      CONFIGURE_COMPILER.__init__(self, **kargs)
      self.fortran_supports_openmp = False

   def after_compilers(self):
      """Define libs to search."""
      # prefer always libstdc++.so to the static one
      self.libs.extend([('math', 'lapack'), ('math', 'blas'),
                        ('cxx', ['libstdc++' + self._ext_shared, 'libstdc++' + self._ext_static]),])

   def add_on(self):
      """After searching compilers, libs... search again other bin or lib."""
      self.fortran_supports_openmp = self.test_compil('F90', args='-ffree-form -fopenmp', src=trivial_src['F90'])

   def set_flags(self):
      """Set compiler options."""
      self.cfg['CFLAGS'] = '-O2'
      flagsp = self.test_compil('CC', args='-fno-stack-protector')
      self.fcheck(flagsp, "CC (%s) supports '-fno-stack-protector' option" % self.cfg.get('CC', '?'))
      if flagsp:
         self.cfg['CFLAGS']     += ' -fno-stack-protector'

      self.cfg['F90FLAGS'] = '-O2'
      if self.fortran_supports_openmp:
         self.cfg['DEFINED']  += ' _USE_OPENMP'
         self.cfg['CFLAGS_OPENMP'] = '-fopenmp'
         self.cfg['F90FLAGS_OPENMP'] = ' -fopenmp'
         self.cfg['LDFLAGS_OPENMP'] = ' -fopenmp'

      if self.arch == 'x86_64':
         self.cfg['FFLAGS_I8'] = ' -fdefault-double-8 -fdefault-integer-8 -fdefault-real-8'
         self.cfg['F90FLAGS_I8'] = ' -fdefault-double-8 -fdefault-integer-8 -fdefault-real-8'

      self.insert_option('-fPIC')
      self.cfg['CFLAGS_DBG']   = self.cfg['CFLAGS'].replace('-O2', '-g ')
      self.cfg['F90FLAGS_DBG'] = self.cfg['F90FLAGS'].replace('-O2', '-g ')

      # test loc (GCC bug #51267 seen in 4.6.1)
      from check_compilers_src import gcc51267
      # 1. with standard options
      result, errmsg = self.run_test(gcc51267)
      result = self.fcheck(result, 'fortran program if the gcc bug #51267 is fixed (using VOLATILE)')
      if not result:
         flagdse = self.test_compil('F90', args='-fno-tree-dse')
         self.fcheck(flagdse, "F90 (%s) supports '-fno-tree-dse' option" % self.cfg.get('F90', '?'))
         if flagdse:
            self.cfg['F90FLAGS'] += ' -fno-tree-dse'
            result, errmsg = self.run_test(gcc51267)
            result = self.fcheck(result, 'fortran program if the gcc bug #51267 is fixed with -fno-tree-dse option')
         if not result:
            self._print('---------- ERROR MESSAGE ----------', os.linesep, errmsg)
            self._print(gcc51267['__error__'])
            should_continue()


class GNU_without_MATH_COMPILER(GNU_COMPILER):
   """GNU compilers without mathematical libraries."""

   def after_compilers(self):
      """Define libs to search."""
      # prefer always libstdc++.so to the static one
      self.libs.extend([('cxx', ['libstdc++' + self._ext_shared, 'libstdc++' + self._ext_static]),])


class INTEL_COMPILER(CONFIGURE_COMPILER):
   """Intel compilers"""
   CC  = 'icc'
   CXX = 'icpc'
   F90 = 'ifort'

   def __init__(self, **kargs):
      """Initialization."""
      CONFIGURE_COMPILER.__init__(self, **kargs)
      self.is_v11  = False
      self.is_v12  = False
      self.src_mkl = True

   def after_compilers(self):
      """Define libs to search."""
      # http://software.intel.com/en-us/articles/intel-mkl-link-line-advisor/
      self.is_v11 = (self.compiler_version.get('CC')  != None \
            and [11, 0] <= self.compiler_version['CC']  < [12, 0]) or \
                    (self.compiler_version.get('F90') != None \
            and [11, 0] <= self.compiler_version['F90'] < [12, 0])
      self.is_v12 = (self.compiler_version.get('CC')  != None \
            and self.compiler_version['CC']  >= [12, 0]) or \
                    (self.compiler_version.get('F90') != None \
            and self.compiler_version['F90'] >= [12, 0])
      self.fcheck(self.is_v11, 'Intel Compilers version is 11.x')
      self.fcheck(self.is_v12, 'Intel Compilers version >= 12.0')

      if self.is_v11 or self.is_v12:
         if self.arch == 'x86':
            self.libs.append(('math', 'mkl_intel'))
         else:
            self.libs.append(('math', 'mkl_intel_lp64'))
         self.libs.append(('math', 'mkl_sequential'))
         self.libs.append(('math', 'mkl_core'))
      else:
         # version < 11.0
         if self.prefshared:
            self.libs.append(('math', 'mkl'))
         if self.arch == 'x86':
            self.libs.append(('math', ['mkl_lapack', 'mkl_lapack32']))
            self.libs.append(('math', ['mkl_ia32', 'mkl_ias']))
         elif self.arch == 'ia64':
            self.libs.append(('math', ['mkl_lapack', 'mkl_lapack64']))
            self.libs.append(('math', ['mkl_ipf', 'mkl_ias']))
         else:
            self.libs.append(('math', ['mkl_lapack', 'mkl_lapack64']))
            self.libs.append(('math', ['mkl_em64t', 'mkl_ias']))
         self.libs.append(('sys', 'guide'))

      self.libs.append(('sys', 'pthread'))      # pthread must appear after guide
      # prefer always libstdc++.so to the static one
      self.libs.extend([('cxx', ['libstdc++' + self._ext_shared, 'libstdc++' + self._ext_static]),])

   def after_libs(self):
      """Add start/end group option around mathlib."""
      if self.is_v11 or self.is_v12:
         self.cfg['__LIBS_math_000_start'] = "-Wl,--start-group"
         self.cfg['__LIBS_math_999_end']   = "-Wl,--end-group"

   def check_env(self):
      """Check for environment profiles."""
      add_arch = False
      search_paths = []
      if self.is_v12:
         self.profiles.extend(['compilervars.sh',])
         if self.arch == 'x86':  # 32 bits
            intel_arch   = 'ia32'
            mkl_src_name = 'mklvars_ia32.sh'
         else:
            intel_arch = 'intel64'     # x86_64
            mkl_src_name = 'mklvars_intel64.sh'
      else:
         self.profiles.extend(['iccvars.sh', 'ifortvars.sh',])
         if self.arch == 'x86':  # 32 bits
            intel_arch   = 'ia32'
            mkl_src_name = 'mklvars32.sh'
         elif self.arch == 'x86_64':
            if self.arch == 'ia64':    # ia64
               intel_arch   = 'ia64'
               mkl_src_name = 'mklvars64.sh'
            else:                      # x86_64
               intel_arch   = 'intel64'
               mkl_src_name = 'mklvarsem64t.sh'
         elif self.platform == 'FREEBSD':   # Not yet tested with icc!
            if self.arch == 'ia64':    # ia64
               intel_arch   = 'ia64'
               mkl_src_name = 'mklvars64.sh'
            elif self.arch == 'x86_64':    # x86_64
               intel_arch   = 'ia64'
               mkl_src_name = 'mklvars64.sh'
            else:                      # 32 bits
               intel_arch   = 'ia32'
               mkl_src_name = 'mklvars32.sh'
         else:
            raise CheckCompilerError(_('Unsupported platform : %s') % self.platform)

      if self.is_v11 or self.is_v12:
         add_arch = True
         self.src_mkl = False
         search_paths.append( self.cfg['CC'].replace('/%s/icc'   % intel_arch, ''))
         search_paths.append(self.cfg['F90'].replace('/%s/ifort' % intel_arch, ''))
         search_paths.append(os.path.normpath(os.path.join(self.cfg['CC'], os.pardir, os.pardir, os.pardir)))
         # unset LANG because of (version 11.0 only)
         # """Catastrophic error: could not set locale "" to allow processing of multibyte characters"""
         #         self.cfg['OPT_ENV'] = self.cfg.get('OPT_ENV', '')
         #         self.cfg['OPT_ENV'] += os.linesep + """
         ## because of this error : 'Catastrophic error: could not set locale "" to allow processing of multibyte characters'
         #unset LANG
         #"""
         self.cfg['OPT_ENV'] = self.cfg.get('OPT_ENV', '').strip()
      else:
         # from '/opt/intel/fc/9.1.045/bin/ifort', add '/opt/intel'
         search_paths.append(os.path.normpath(os.path.join(self.cfg['CC'], os.pardir, os.pardir, os.pardir, os.pardir)))

      self._print('add_arch =', repr(add_arch), '; src_mkl =', repr(self.src_mkl),
                  '; intel_arch =', repr(intel_arch), '; mkl_src_name =', repr(mkl_src_name), DBG=True)

      if self.src_mkl:
         self.profiles.append(mkl_src_name)
      for prof in self.profiles:
         res = self.ftools.find_file(prof, paths=search_paths, typ='all', maxdepth=self.maxdepth)
         if res:
            if add_arch:
               res += ' ' + intel_arch
            self.env_files.append(res)
      if not self.src_mkl and self.is_v11:
         self.fcheck('should be sourced by iccvars.sh/ifortvars.sh', mkl_src_name)
      if os.environ.get('INTEL_LICENSE_FILE'):
         self.cfg['OPT_ENV'] = self.cfg.get('OPT_ENV', '')
         self.cfg['OPT_ENV'] += os.linesep
         self.cfg['OPT_ENV'] += "export INTEL_LICENSE_FILE='%s'" % os.environ['INTEL_LICENSE_FILE']
         self.cfg['OPT_ENV'] = self.cfg['OPT_ENV'].strip()

      CONFIGURE_COMPILER.check_env(self)

   def set_flags(self):
      """Set compiler options."""
      self.cfg['DEFINED']  += '_USE_INTEL_IFORT _USE_OPENMP _DISABLE_MATHLIB_FPE'
      self.cfg['LDFLAGS']   = '-nofor_main'   # add -static-intel ?
      self.cfg['CFLAGS']    = '-O3 -traceback'
      self.cfg['F90FLAGS']  = '-O3 -fpe0 -traceback'
      self.cfg['CFLAGS_OPENMP'] = '-openmp'
      self.cfg['F90FLAGS_OPENMP'] = '-openmp'
      self.cfg['LDFLAGS_OPENMP'] = '-openmp'
      if self.arch == 'x86_64':
         self.cfg['F90FLAGS_I8'] = ' -i8 -r8'

      self.insert_option('-fPIC')
      self.cfg['CFLAGS_DBG']   = self.cfg['CFLAGS'].replace('-O3', '-g ')
      self.cfg['F90FLAGS_DBG'] = self.cfg['F90FLAGS'].replace('-O3', '-g ')


class INTEL_without_MATH_COMPILER(INTEL_COMPILER):
   """Intel compilers without mathematical libraries."""

   def after_compilers(self):
      """Define libs to search."""
      if not self.is_v11:
         self.libs.append(('sys', 'guide'))
      self.libs.append(('sys', 'pthread'))      # pthread must appear after guide
      # prefer always libstdc++.so to the static one
      self.libs.extend([('cxx', ['libstdc++' + self._ext_shared, 'libstdc++' + self._ext_static]),])


class OPEN64_COMPILER(CONFIGURE_COMPILER):
   """Open64 compilers."""
   CC  = 'opencc'
   CXX = 'openCC'
   F90 = 'openf90'

   def after_compilers(self):
      """Define libs to search."""
      # prefer always libstdc++.so to the static one
      self.libs.extend([('math', 'lapack'), ('math', 'blas'),
                        ('cxx', ['libstdc++' + self._ext_shared, 'libstdc++' + self._ext_static]),])

   def set_flags(self):
      """Set compiler options."""
      self.cfg['CFLAGS']     = '-O'
      self.cfg['F90FLAGS']   = '-O'
      if self.arch == 'x86_64':
         self.cfg['F90FLAGS_I8'] = ' -i8 -r8'

      self.insert_option('-openmp')
      self.insert_option('-fPIC')
      self.cfg['DEFINED']  += ' _USE_OPENMP'
      self.cfg['CFLAGS_DBG']   = self.cfg['CFLAGS'].replace('-O', '-g ')
      self.cfg['F90FLAGS_DBG'] = self.cfg['F90FLAGS'].replace('-O', '-g ')


class OPEN64_without_MATH_COMPILER(OPEN64_COMPILER):
   """Open64 compilers without mathematical libraries."""

   def after_compilers(self):
      """Define libs to search."""
      # prefer always libstdc++.so to the static one
      self.libs.extend([('cxx', ['libstdc++' + self._ext_shared, 'libstdc++' + self._ext_static]),])


class PATHSCALE_COMPILER(CONFIGURE_COMPILER):
   """Pathscale compilers."""
   CC  = 'pathcc'
   CXX = 'pathCC'
   F90 = 'pathf90'

   def after_compilers(self):
      """Define libs to search."""
      # prefer always libstdc++.so to the static one
      self.libs.extend([('math', 'lapack'), ('math', 'blas'),
                        ('cxx', ['libstdc++' + self._ext_shared, 'libstdc++' + self._ext_static]),])

   def set_flags(self):
      """Set compiler options."""
      self.cfg['CFLAGS']     = '-O'
      self.cfg['F90FLAGS']   = '-O'
      if self.arch == 'x86_64':
         self.cfg['F90FLAGS_I8'] = ' -i8 -r8'

      self.insert_option('-openmp')
      self.insert_option('-fPIC')
      self.cfg['DEFINED']  += ' _USE_OPENMP'
      self.cfg['CFLAGS_DBG']   = self.cfg['CFLAGS'].replace('-O', '-g ')
      self.cfg['F90FLAGS_DBG'] = self.cfg['F90FLAGS'].replace('-O', '-g ')


class PATHSCALE_without_MATH_COMPILER(PATHSCALE_COMPILER):
   """Pathscale compilers without mathematical libraries."""

   def after_compilers(self):
      """Define libs to search."""
      # prefer always libstdc++.so to the static one
      self.libs.extend([('cxx', ['libstdc++' + self._ext_shared, 'libstdc++' + self._ext_static]),])


dict_name = {
   'INTEL' : INTEL_COMPILER,
   'GNU'   : GNU_COMPILER,
   'OPEN64' : OPEN64_COMPILER,
   'PATHSCALE' : PATHSCALE_COMPILER,
   'INTEL_WITHOUT_MATH' : INTEL_without_MATH_COMPILER,
   'GNU_WITHOUT_MATH'   : GNU_without_MATH_COMPILER,
   'OPEN64_WITHOUT_MATH' : OPEN64_without_MATH_COMPILER,
   'PATHSCALE_WITHOUT_MATH' : PATHSCALE_without_MATH_COMPILER,
}

global_pref_order = [
   'INTEL', 'GNU', 'OPEN64', 'PATHSCALE',
   'INTEL_WITHOUT_MATH', 'GNU_WITHOUT_MATH',
   'OPEN64_WITHOUT_MATH', 'PATHSCALE_WITHOUT_MATH',
]


class COMPILER_MANAGER:
   """Manager multiple compilers during installation.
   """

   def __init__(self, debug=False, print_func=None):
      """Initialization"""
      self.config = {}
      self._first_switch = True
      self._first_values = {}
      self._out_values   = {}
      self._overwritten_attrs = ['DEFINED', 'OPT_ENV',]
      self._compilers_attrs   = set(self._overwritten_attrs)
      self._global_cfg = {}
      self.debug = debug
      self.print_func = print_func

   def _print(self, *args, **kargs):
      if self.print_func:
         self.print_func(*args, **kargs)
      else:
         print args, kargs

   def configure(self, **kargs):
      """Configure a compiler.
      """
      success = False
      name    = kargs.get('name', '').upper()
      product = kargs.get('product', name)
      # already checked or not ?
      conf = self.config.get(name)
      if not conf:
         klass = dict_name.get(name)
         if not klass:
            return success
         conf = klass(**kargs)
         conf.run()
         conf.diag()
         self._global_cfg.update(conf.cfg_add_global)
         conf.fcheck(', '.join(conf.cfg_add_global.values()), 'global values')
         self._print("_global_cfg : ", self._global_cfg, DBG=True)
      else:
         conf.fcheck('ok (already configured)', conf.__doc__)

      success = conf.check_ok()
      if success:
         self.config[product] = conf
         self.config[name]    = conf
         # if __main__ is not yet defined
         self.config['__main__'] = self.config.get('__main__', conf)

      return success

   def check_compiler(self, **kargs):
      """Try to configure a compiler. Stops at first success.
         'name' : prefered compiler (searched first).
      """
      l_search = []
      # add prefered class and its derivated first (GNU, GNU_xxx...)
      name_ini = kargs.get('name', '').upper()
      if name_ini:
         klass = dict_name.get(name_ini)
         if klass:
            l_search.append(name_ini)
            for name in global_pref_order:
               if (name.startswith(name_ini) or name_ini.startswith(name)) \
                  and name not in l_search:
                  l_search.append(name)
      # or take all classes
      else:
         for name in global_pref_order:
            if name not in l_search:
               l_search.append(name)

      success = False
      for name in l_search:
         kargs['name'] = name
         success = self.configure(**kargs)
         if success:
            break
      return success

   def get_config(self, product=None):
      """Return config dict."""
      return self.config.get(product, self.config.get('__main__')).cfg

   def switch_in_dep(self, dependency_object, product, system=None, verbose=False):
      """Change 'cfg' attribute of the dependency_object.
      """
      __dbgsw  = False
      cfg = dependency_object.cfg
      compiler_cfg = self.get_config(product)
      if __dbgsw:
         print '#SWITCH switch cfg pour %s' % product
         pprint(cfg)
         print '#SWITCH compiler_cfg'
         pprint(compiler_cfg)
         print '#SWITCH _first_values'
         pprint(self._first_values)

      # first time store initial values
      if self._first_switch:
         for attr in self._overwritten_attrs:
            if cfg.get(attr) is not None:
               if __dbgsw:
                  print '#SWITCH init cfg[%s] = %s' % (attr, cfg.get(attr))
               self._first_values[attr] = cfg[attr]
         self._first_switch = False
      else:
         # differences added by products
         lk = set(cfg.keys())
         lk.update(self._out_values.keys())
         for k in lk:
            v1 = self._out_values.get(k, '')
            v2 = cfg.get(k, '')
            if v1 != v2:
               if __dbgsw:
                  print '#SWITCH has changed %s' % k
                  print '   %s  //  %s' % (v1, v2)
               diff = v2.replace(v1, '').strip()
               if __dbgsw:
                  print '#SWITCH increment : ', diff
               self._first_values[k] = (self._first_values.get(k, '') + ' ' + diff).strip()
            else:
               pass
               if __dbgsw:
                  print '#SWITCH idem %-12s : %s' % (k, v1)

      # re-init values defined by compilers
      for attr in self._compilers_attrs:
         cfg[attr] = ''

      # copy values if not already in cfg
      math_lib = []
      cxx_lib  = []
      sys_lib  = []

      sorted_keys = set(compiler_cfg.keys())
      sorted_keys.update(self._global_cfg.keys())
      sorted_keys = list(sorted_keys)
      sorted_keys.sort()            # to preserve libs order
      for key in sorted_keys:
         value = compiler_cfg.get(key)
         from_globv = value is None
         if from_globv:
            value = self._global_cfg[key]
            self._print('from _global_cfg[%s] = %s' % (key, value), DBG=True)
         # ignore null values
         if not value:
            continue
         if not key.startswith('__'):
            if cfg.get(key) and __dbgsw:
               print '#SWITCH already exists %s' % key
               print '   old=%s' % cfg[key]
               print '   new=%s' % value
            cfg[key] = value
         elif key.startswith('__LIBS_math_'):
            if value in math_lib and from_globv:
               math_lib.remove(value)
            math_lib.append(value)
         elif key.startswith('__LIBS_cxx_'):
            if value in cxx_lib and from_globv:
               cxx_lib.remove(value)
            cxx_lib.append(value)
         elif key.startswith('__LIBS_sys_'):
            if value in sys_lib and from_globv:
               sys_lib.remove(value)
            sys_lib.append(value)
      cfg['MATHLIB']  = ' '.join(math_lib)
      cfg['CXXLIB']   = ' '.join(cxx_lib)
      cfg['OTHERLIB'] = ' '.join(sys_lib)
      l_key = compiler_cfg.keys()
      for key in ['MATHLIB', 'CXXLIB', 'OTHERLIB']:
         if not key in l_key:
            l_key.append(key)
      self._compilers_attrs.update(l_key)

      if __dbgsw:
         print '#SWITCH defined  old=%s' % cfg['DEFINED']
      cfg['DEFINED'] = self._first_values.get('DEFINED', '') + ' ' + compiler_cfg.get('DEFINED', '')
      cfg['DEFINED'] = cfg['DEFINED'].strip()
      if __dbgsw:
         print '             new=%s' % cfg['DEFINED']

      cfg['OPT_ENV'] = self._first_values.get('OPT_ENV', '')
      if __dbgsw:
         print '#SWITCH opt_env  old=%s' % cfg['OPT_ENV']

      if cfg['OPT_ENV'].strip() != compiler_cfg.get('OPT_ENV', '').strip():
         if cfg['OPT_ENV']:
            cfg['OPT_ENV'] += os.linesep
         cfg['OPT_ENV'] += compiler_cfg.get('OPT_ENV', '')
      cfg['OPT_ENV'] = cfg['OPT_ENV'].strip()
      if system:
         system.AddToEnv(cfg['OPT_ENV'], verbose=False)
      if __dbgsw:
         print '             new=%s' % cfg['OPT_ENV']

      # set new cfg dict and store output values
      dependency_object.cfg = cfg
      self._out_values = cfg.copy()

      txtdbg = os.linesep.join(['#SWITCH sortie cfg pour %s' % product, pformat(cfg)])
      if self.debug:
         open('cfg_%s' % product, 'w').write(txtdbg)
      if __dbgsw:
         print txtdbg

      # 1.5.2. ----- export environment variables for compilers and linker
      cfg['FC'] = cfg.get('F90', '')
      cfg['FCFLAGS'] = cfg.get('F90FLAGS', '')
      for var in ['CC', 'CXX', 'F90', 'LD',
                  'CFLAGS', 'CXXFLAGS', 'FCFLAGS', 'F90FLAGS', 'LDFLAGS']:
         os.environ[var] = cfg.get(var, '')

      # if verbose, return environment variables for the selected compiler
      txt = []
      l_key.sort()
      try:
         l_key.remove('OPT_ENV')
      except ValueError:
         pass
      for key in l_key:
         if cfg.get(key):
            txt.append('export %16s=%r' % (key, cfg[key]))
      txt.append('')
      txt.append('# Environment settings :')
      txt.extend(cfg['OPT_ENV'].splitlines())

      if verbose:
         return os.linesep.join(txt)

