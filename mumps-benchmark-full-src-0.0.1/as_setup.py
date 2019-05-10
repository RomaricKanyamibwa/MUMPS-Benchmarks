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

"""This module defines following classes :
- SETUP        main class to configure, make, install Code_Aster products,
- DEPENDENCIES stores dependencies between products,
- SUMMARY      stores setup informations,
- SYSTEM       encapsulates calls to system commands,
- FIND_TOOLS   package of utilities to find files, libraries...

+ exceptions to control errors occurences.
"""


__all__ = ['SETUP', 'SUMMARY', 'SYSTEM', 'DEPENDENCIES', 'FIND_TOOLS',
   'should_continue', 'GetPrefix', 'GetSitePackages', 'AddToPostInstallDir',
   'less_than_version', 'export_parameters', 'get_install_message',
   'SetupCheckError', 'SetupChgFilesError', 'SetupChmodError', 'SetupCleanError',
   'SetupConfigureError', 'SetupError', 'SetupExtractError', 'SetupInstallError',
   'SetupMakeError']

import sys
import os
import os.path as osp
import glob
import re
import time
import traceback
import tarfile
import compileall
import imp
import pprint
import distutils.sysconfig as SC
from subprocess import Popen, PIPE

StringTypes = (str, unicode)
EnumTypes=(list, tuple)

# ----- differ messages translation
def _(mesg): return mesg

#-------------------------------------------------------------------------------
class SetupError(Exception):
    def __repr__(self):
        txt = [str(arg) for arg in self.args]
        return ''.join(txt).strip()

class SetupExtractError(SetupError):   pass
class SetupConfigureError(SetupError): pass
class SetupChgFilesError(SetupError):  pass
class SetupChmodError(SetupError):     pass
class SetupMakeError(SetupError):      pass
class SetupInstallError(SetupError):   pass
class SetupCheckError(SetupError):     pass
class SetupCleanError(SetupError):     pass


def get_install_message(package, missed):
    """Return a message recommending to install a package"""
    txt = ""
    if missed:
        txt += """
Unable to find %s
""" % missed
    if package:
        txt += """
A package named "%(pkg)s" is required (the package name may differ
depending on your system). You should install it using your package
manager or by a command line similar to :

on debian/ubuntu:
    apt-get install %(pkg)s

on centos, rhel, fedora:
    yum install %(pkg)s

on mandriva:
    urpmi %(pkg)s
""" % { 'pkg' : package }
    return txt

def _clean_path(lpath, returns='str'):
   """Clean a path variable as PATH, PYTHONPATH, LD_LIBRARY_PATH...
   """
   dvu = {}
   lnew = []
   lpath = (':'.join(lpath)).split(':')
   for p in lpath:
      p = osp.abspath(p)
      if p != '' and not dvu.get(p, False):
         lnew.append(p)
         dvu[p] = True
   if returns == 'str':
      val = ':'.join(lnew)
   else:
      val = lnew
   return val

def _chgline(line, dtrans, delimiter=re.escape('?')):
   """Change all strings by their new value provided by 'dtrans' dictionnary
   in the string 'line'.
   """
   for old, new in dtrans.items():
      line=re.sub(delimiter+old+delimiter, str(new), line)
   return line

_noprompt = False
def should_continue_reg(noprompt):
    """Register behavior for `should_continue`."""
    global _noprompt
    _noprompt = noprompt

def should_continue(default='n', stop=True, question=None):
   """Ask if the user want to stop or continue.
   The response is case insensitive.
   If 'stop' is True, ends the execution with exit code 'UserInterruption',
   else returns the response.
   """
   if _noprompt:
       return 'yes'
   yes = ['yes', 'y', 'oui', 'o']   # only lowercase
   no  = ['no',  'n', 'non',]
   question = question or "Do you want to continue (y/n, default %s) ? " % default.lower()
   valid=False
   while not valid:
      try:
         resp=raw_input(question)
      except EOFError:
         resp=None
      except KeyboardInterrupt:
         sys.exit('KeyboardInterrupt')
      if resp=='':
         resp=default
      valid = resp<>None and resp.lower() in yes+no
   if resp.lower() in no:
      resp = 'no'
      if stop:
         sys.exit('UserInterruption')
   else:
      resp = 'yes'
   return resp.lower()

def GetSitePackages(prefix):
   return SC.get_python_lib(prefix=prefix)

def GetPrefix(site_packages):
   suff = osp.join('lib', 'python'+sys.version[:3], 'site-packages')
   if not site_packages.endswith(suff):
      suff = osp.join('lib64', 'python'+sys.version[:3], 'site-packages')
      if not site_packages.endswith(suff):
          raise SetupError(_('invalid `site_packages` path : %s') % site_packages)
   return site_packages.replace(suff, '')

def AddToPostInstallDir(filename, postinst, dest):
   """Add filename to post-installation directory.
   """
   fbas = osp.basename(filename)
   fdir = osp.dirname(filename)
   ibckp = 0
   fnum = osp.join(postinst, '%06d_numfile' % 0)
   if osp.exists(fnum):
      try:
         ibckp = int(open(fnum, 'r').read().strip())
      except:
         pass
   ibckp += 1
   #bckpf = osp.join(postinst, '%06d_file_%s'    % (ibckp, fbas))
   bdest = osp.join(postinst, '%06d_dest_%s'    % (ibckp, fbas))
   open(fnum, 'w').write(str(ibckp))
   open(bdest, 'w').write(osp.join(dest, filename))

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
class SETUP:
   """
   Attributes :
    .product      : product name,
    .version      : product version,
    .description  : description of the product,
    .archive      : archive filename (gzip and bzip2 compressed archives support
      is provided by tarfile module, default is product-version),
    .content      : name of the directory contained in archive
      (default is product-version),
    .verbose      : True for verbose mode,
    .debug        : True for debug mode,
    .installdir   : installation directory,
    .sourcedir    : directory where is 'archive',
    .workdir      : directory used for extraction, compilation...
    .delimiter    : ChgFiles search strings enclosed by this delimiter
      (note with special character in regexp, default is '?'),
    .manual       : if False, Go() is automatically called by __init__
      (NOTE : if True and error occurs SETUP instance won't be created because
       __init__ wasn't finish),
    .actions      : give the list of actions run by 'Go' method and arguments,
    .clean_actions : give the list of actions run if 'Go' failed,
    ._tmpdir : setup working directory,
    .exit_code    : None during process, exit code after,

    .depend       : DEPENDENCIES object.

     + Shell, VerbStart, VerbIgnore, VerbEnd : shortcuts to SYSTEM methods

   NB : Configure, Make, Install and Check methods can be provided by 'user'
      through 'external' argument for particular applications.
   """
   _separ = '\n' + '-'*80 + '\n'
   _fmt_info = _separ+_(""" Installation of   : %s %s
   %s
 Archive filename  : %s
 Destination       : %s
 Working directory : %s""")+_separ
   _fmt_enter = _("entering directory '%s'")
   _fmt_leave = _("leaving directory '%s'")
   _fmt_title = '\n >>> %s <<<\n'
   _fmt_inst  = _(' %s has already been installed.\n' \
                  ' Remove %s to force re-installation.')
   _fmt_ended = _separ+_(' Installation of %s %s successfully completed')+_separ
#-------------------------------------------------------------------------------
   def __init__(self, **kargs):
      """Initializes an instance of an SETUP object and calls Info to print
      informations.
      """
      self.exit_code = None
      self._tmpdir = kargs.get('tmpdir', os.environ.get('TMPDIR', '/tmp'))
      # product parameters
      required_args=('product', 'version', 'description', 'installdir', 'sourcedir')
      for arg in required_args:
         try:
            setattr(self, arg, kargs[arg])
         except KeyError, msg:
            raise SetupError(_('missing argument %s') % str(msg))
      optional_args={
         'depend'    : None,
         'archive'   : '%s-%s' % (self.product, self.version),
         'content'   : '%s-%s' % (self.product, self.version),
         'workdir'   : osp.join(self._tmpdir,
               'install_'+self.product+'.'+str(os.getpid())),
         'delimiter' : re.escape('?'),
         'manual'    : True,
         'reinstall' : 'ask',
      }
      for arg, default in optional_args.items():
         setattr(self, arg, kargs.get(arg, default))
      self.success_key = 'successfully_installed_%s' % self.product
      self.success_key = self.success_key.replace('-', '')
      self.success_key = self.success_key.replace('.', '')

      # default actions can only be set after initialisation
      default_actions = (
         ('Extract'   , {}),
         ('Configure' , {}),
         ('Make'      , {}),
         ('Install'   , {}),
         ('Check'     , {}),
         ('Clean'     , {}),
      )
      self.actions = kargs.get('actions', default_actions)
      self.clean_actions = kargs.get('clean_actions', [])
      for d in ('installdir', 'sourcedir', 'workdir'):
         setattr(self, d, osp.abspath(getattr(self, d)))

      # external methods
      system=kargs.get('system')
      if system==None:
         raise SetupError(_("Argument not found 'system'"))
      self.verbose    = system.verbose
      self.debug      = system.debug
      self.Shell      = system.local_shell
      self.VerbStart  = system.VerbStart
      self.VerbIgnore = system.VerbIgnore
      self.VerbEnd    = system.VerbEnd
      self._print = kargs['log']._print

      # print product informations
      self.Info()

      # Go if not manual
      if not self.manual:
         self.Go()

#-------------------------------------------------------------------------------
   def _call_external(self, **kargs):
      """Call an external user's method to perform an operation.
      """
      try:
         kargs.get('external')(self, **kargs)
      except:
         self.exit_code=4
         self._print(self._separ, term='')
         self._print(self._fmt_title % _('External method traceback'))
         traceback.print_exc()
         self._print(self._separ)
         raise SetupConfigureError(_("external method failed (see traceback above)."))

#-------------------------------------------------------------------------------
   def Go(self):
      """Run successively each actions defined in 'self.actions',
      call PreCheck() first.
      """
      if self.depend.cfg.get(self.success_key) == 'YES' \
         and self.reinstall == 'ignore':
         self._print(self._fmt_inst % (self.product, self.depend.cache))
      else:
         self.PreCheck()
         self.depend.LastCheck()
         for act, kargs in self.actions:
            if act is None:
               continue
            elif not hasattr(self, act):
               raise SetupError(_("unknown action '%s'") % act)
            else:
               getattr(self, act)(**kargs)
         self.exit_code = 0
         # trace of success in cache file
         self.depend.cfg[self.success_key] = 'YES'
         self.depend.FillCache(self.product, [self.success_key, ])
      self._print(self._fmt_ended % (self.product, self.version))

#-------------------------------------------------------------------------------
   def IfFailed(self):
      """Run successively each actions defined in 'self.clean_actions',
      if installation failed.
      """
      if self.exit_code == 0:
         return

      for act, kargs in self.clean_actions:
         if not hasattr(self, act):
            raise SetupError(_("unknown action '%s'") % act)
         else:
            getattr(self, act)(**kargs)

#-------------------------------------------------------------------------------
   def IsInstalled(self, filename):
      """Raise SetupError if the product is already installed."""
      if self.reinstall == 'force':
          return
      all_inst = True
      for path in filename:
          path = self.special_vars(path)
          all_inst = all_inst and osp.exists(path)
          if not all_inst:
              break
      if all_inst:
          msg = _("Product '%s' is already installed.") % self.product
          if self.reinstall == 'ask':
              self._print(msg)
              question = _("Choose 'no' to keep the current installation, "
                           "'yes' to force its re-installation (y/n, default no): ")
              resp = should_continue(stop=False, question=question)
              if resp == 'no':
                  self.reinstall = 'ignore'
          if self.reinstall == 'ignore':
              self.exit_code = 0
              raise SetupError(msg)

   def PreCheck(self, check_values=True):
      """Check for permission and variables settings.
      """
      # fill cache file
      self.depend.FillCache(self.product)

      # check for permissions and create directories
      self.VerbStart(_('Checking permissions...'))
      iret=0
      ldirs=[self.installdir, self.workdir]
      for d in ldirs:
         try:
            if not osp.exists(d):
               os.makedirs(d)
            elif os.access(d, os.W_OK)==0:
               raise OSError(_('no permission to write in %s') % d)
         except OSError:
            iret+=1
            if iret==1: self._print()
            self._print(_(' Unsufficient permission to create or write in %s') % repr(d))
      if iret<>0: self.VerbStart('')   # just for pretty print if fails
      self.VerbEnd(iret)
      if iret<>0:
         raise SetupError(_('permission denied'))

#-------------------------------------------------------------------------------
   def Info(self):
      """Print informations about the installation of current product
      """
      self._print(self._fmt_info % (self.product, self.version, self.description,
                              self.archive, self.installdir, self.workdir))

#-------------------------------------------------------------------------------
   def Extract(self, **kargs):
      """Extract the archive of the product into 'workdir'.
         archive : full pathname of archive,
         command : alternative command line to extract archive (MUST include
            archive filename !),
         extract_as : rename content.
      """
      self._print(self._fmt_title % _('Extraction'))
      if kargs.get('external')<>None:
         self._call_external(**kargs)
         return
      archive = kargs.get('archive', osp.join(self.sourcedir,self.archive))
      command = kargs.get('command')
      newname = kargs.get('extract_as', None)
      path=self.workdir
      iextr_as=newname<>None and self.content<>newname and self.content<>'.'
      if iextr_as:
         path=osp.join(self.workdir,'tmp_extract')
         if not osp.exists(path):
            os.makedirs(path)

      if not osp.isfile(archive):
         l_fic = []
         for opt in ('', '-*'):
            for ext in ('.tar', '.tar.gz','.tar.xz', '.tgz', '.tar.bz2'):
               l_fic.extend(glob.glob(archive + opt + ext))
         if len(l_fic) > 0:
            archive = l_fic[0]
      if not osp.isfile(archive):
         self.exit_code=1
         raise SetupExtractError(_("file not found : %s") % archive)

      prev=os.getcwd()
      self._print(self._fmt_enter % path)
      os.chdir(path)

      if command != None:
         iret,output = self.Shell(command,
               alt_comment=_('Extracting %s...') % osp.basename(archive))
         if iret<>0:
            self.exit_code=4
            raise SetupExtractError(_('error during extracting archive %s') % archive)
      else:
         self.VerbStart(_('Extracting %s...') % osp.basename(archive))
         # open archive using tarfile module
         try:
            tar = tarfile.open(archive, 'r')
         except (tarfile.CompressionError, tarfile.ReadError):
            # try with gzip or bzip2
            self.VerbIgnore()
            iret = -1
            if archive.endswith('gz'):
               iret, output = self.Shell('gzip -dc %s | tar -xf -' % archive,
                     alt_comment=_('Trying GZIP decompression...'))
            elif archive.endswith('bz2'):
               iret, output = self.Shell('bzip2 -dc %s | tar -xf -' % archive,
                     alt_comment=_('Trying BZIP2 decompression...'))
            else:
               iret, output = self.Shell('tar -xf %s' % archive,
                     alt_comment=_('Trying raw tar extraction...'))
            if iret != 0:
               self.exit_code = 2
               raise SetupExtractError(_('unsupported archive format for %s') % archive)
         # extract archive
         else:
            iret=0
            n=0
            tar.errorlevel=2
            try:
               for ti in tar:
                  n+=1
                  if ti.issym():             # pourquoi supprime-t-on les symlink ?
                     try:
                        os.remove(ti.name)
                     except OSError:
                        pass                 # la cible n'existe pas encore
                  tar.extract(ti)
            except tarfile.ExtractError:
               iret=4
            except (IOError,OSError), msg:
               iret=8
            except:
               iret=16
            self.VerbEnd(iret)
            tar.close()
            self._print(_(' --- %d files extracted') % n)
            if iret<>0:
               traceback.print_exc()
               self.exit_code=iret
               raise SetupExtractError(_('error during extracting archive %s') % archive)

      if iextr_as:
         iret=0
         self.VerbStart(_('Renaming %s to %s...') % (self.content, newname))
         newname=osp.join(self.workdir,newname)
         try:
            if osp.exists(newname):
               self._print()
               iret,output=self.Shell('rm -rf '+newname,
                     alt_comment=_('Deleting previous content of %s...') % newname)
               if iret<>0:
                  raise OSError
            os.rename(self.content, newname)
         except (OSError, IOError), msg:
            iret=4
            self._print()
            raise SetupExtractError(_('error renaming %s to %s') \
                  % (self.content, newname))
         self.VerbEnd(iret)

      self._print(self._fmt_leave % path)
      os.chdir(prev)
      if iextr_as:
         self.Clean(to_delete=path)

#-------------------------------------------------------------------------------
   def Configure(self, **kargs):
      """Configuration of the product.
         command : alternative command line
         path    : directory to build
      """
      self._print(self._fmt_title % _('Configuration'))
      command = kargs.get('command')
      path    = kargs.get('path', osp.join(self.workdir,self.content))
      path = self.special_vars(path)
      if command==None:
         command='./configure --prefix='+self.installdir

      if not osp.isdir(path):
         self.exit_code=4
         raise SetupConfigureError(_('directory not exists %s') % path)

      prev=os.getcwd()
      self._print(self._fmt_enter % path)
      os.chdir(path)

      if kargs.get('external')<>None:
         self._call_external(**kargs)

      else:
         self._print(_('Command line :'), command)
         iret,output=self.Shell(command, follow_output=self.verbose,
               alt_comment=_('configure %s installation...') % self.product)
         if iret<>0:
            if not self.verbose: self._print(output)
            self.exit_code=4
            raise SetupConfigureError(_('error during configure'))

      self._print(self._fmt_leave % path)
      os.chdir(prev)

#-------------------------------------------------------------------------------
   def ChgFiles(self, **kargs):
      """Modify files from 'files' according a dictionnary 'dtrans'
         defined as { 'string_to_replace' : 'new_value' }.
      Pathnames are relative to workdir/content or to 'path' argument.
      !!! Do only post-install tasks if 'only_postinst' is True.
      optional args : 'delimiter', 'keep', 'ext', 'postinst', 'postdest'
         postinst : directory to backup file for post-installation
         postdest : if different of self.installdir
      """
      self._print(self._fmt_title % _('Modifying pre-configured files'))
      chglist   = kargs.get('files', [])
      dtrans    = kargs.get('dtrans',{})
      delimiter = kargs.get('delimiter', self.delimiter)
      keep      = kargs.get('keep', False)
      ext       = kargs.get('ext')
      postinst  = kargs.get('postinst')
      postdest  = kargs.get('postdest', self.installdir)
      postdest  = self.special_vars(postdest)
      path      = kargs.get('path', osp.join(self.workdir,self.content))
      path      = self.special_vars(path)
      only_postinst = kargs.get('only_post', False)

      if not osp.isdir(path):
         self.exit_code=4
         raise SetupChgFilesError(_('directory not exists %s') % path)

      prev=os.getcwd()
      self._print(self._fmt_enter % path)
      os.chdir(path)

      if kargs.get('external') != None:
         self._call_external(**kargs)

      else:
         for f0 in chglist:
            for f in glob.glob(f0):
               iret=0
               self.VerbStart(_('modifying %s') % f)
               if osp.isfile(f):
                  if not only_postinst:
                     iret=self._chgone(f, dtrans, delimiter, keep, ext)
                  if postinst != None:
                     AddToPostInstallDir(f, postinst, postdest)
                  self.VerbEnd(iret)
               else:
                  self.VerbIgnore()

      self._print(self._fmt_leave % path)
      os.chdir(prev)

   def _chgone(self, filename, dtrans, delimiter=None, keep=False, ext=None):
      """Change all strings by their new value provided by 'dtrans' dictionnary
      in the existing file 'filename'.
      """
      if delimiter == None:
         delimiter = self.delimiter
      if ext == None:
         ext = '.orig'
      iret = 0
      try:
         os.rename(filename, filename+ext)
      except OSError:
         return 4
      fsrc = open(filename+ext, 'r')
      fnew = open(filename, 'w')
      for line in fsrc:
         fnew.write(_chgline(line, dtrans, delimiter))
      fnew.close()
      fsrc.close()
      if not keep:
         os.remove(filename+ext)
      return iret

#-------------------------------------------------------------------------------
   def Make(self, **kargs):
      """Compilation of product.
         command : alternative command line
         path    : directory to build (or list of directories)
      """
      self._print(self._fmt_title % _('Building the product'))
      if kargs.get('external')<>None:
         self._call_external(**kargs)
         return
      command = kargs.get('command')
      lpath   = kargs.get('path', osp.join(self.workdir,self.content))
      nbcpu   = kargs.get('nbcpu', 1)
      capturestderr = kargs.get('capturestderr', True)
      if not type(lpath) in EnumTypes:
         lpath=[lpath,]
      if command == None:
         command = 'make'
      if nbcpu != 1:
         command += ' -j %d' % nbcpu

      for path in lpath:
         path = self.special_vars(path)
         if not osp.isdir(path):
            self.exit_code=4
            raise SetupConfigureError(_('directory not exists %s') % path)

         prev=os.getcwd()
         self._print(self._fmt_enter % path)
         os.chdir(path)

         self._print(_('Command line :'), command)
         iret,output=self.Shell(command, follow_output=self.verbose,
               capturestderr=capturestderr,
               alt_comment=_('compiling %s...') % self.product)
         if iret<>0:
            if not self.verbose: self._print(output)
            self.exit_code=4
            raise SetupMakeError(_('error during compilation'))

         self._print(self._fmt_leave % path)
         os.chdir(prev)

#-------------------------------------------------------------------------------
   def Install(self, **kargs):
      """Perform installation of the product.
         command : alternative command line
         path    : directory to build
      """
      self._print(self._fmt_title % _('Installation'))
      command = kargs.get('command')
      path    = kargs.get('path', osp.join(self.workdir,self.content))
      path = self.special_vars(path)
      if command==None:
         command='make install'

      if not osp.isdir(path):
         self.exit_code=4
         raise SetupInstallError(_('directory not exists %s') % path)

      prev=os.getcwd()
      self._print(self._fmt_enter % path)
      os.chdir(path)

      if kargs.get('external')<>None:
         self._call_external(**kargs)

      else:
         self._print(_('Command line :'), command)
         iret,output=self.Shell(command, follow_output=self.verbose,
               alt_comment=_('installing %s to %s...') % (self.product, self.installdir))
         if iret<>0:
            if not self.verbose: self._print(output)
            self.exit_code=4
            raise SetupInstallError(_('error during installation'))

      self._print(self._fmt_leave % path)
      os.chdir(prev)

#-------------------------------------------------------------------------------
   def PyInstall(self, **kargs):
      """Perform installation of a Python module.
         command  : alternative command line
         path     : initial directory
         prefix   : installation prefix
         cmd_opts : options
      """
      format = '%(python)s %(script)s %(global_opts)s %(cmd)s --prefix=%(prefix)s %(cmd_opts)s'
      d_cmd = {}
      d_cmd['python']      = self.depend.cfg.get('PYTHON_EXE', sys.executable)
      d_cmd['script']      = kargs.get('script', 'setup.py')
      d_cmd['global_opts'] = kargs.get('global_opts', '')
      d_cmd['cmd']         = kargs.get('cmd', 'install')
      d_cmd['cmd_opts']    = kargs.get('cmd_opts', '')
      d_cmd['prefix']      = kargs.get('prefix', GetPrefix(self.installdir))

      kargs['command'] = kargs.get('command', format % d_cmd)
      self.Install(**kargs)

#-------------------------------------------------------------------------------
   def PyCompile(self, **kargs):
      """Recursively descend the directory tree named by 'path', compiling
      all .py files along the way.
         path    : one or more directories
      """
      self._print(self._fmt_title % _('Compiling Python source files'))
      lpath    = kargs.get('path', osp.join(self.workdir,self.content))
      if not type(lpath) in EnumTypes:
         lpath=[lpath,]

      iret=0
      for path in lpath:
         path = self.special_vars(path)
         if not osp.isdir(path):
            self.exit_code=4
            raise SetupInstallError(_('directory not exists %s') % path)

         prev=os.getcwd()
         self._print(self._fmt_enter % path)
         os.chdir(path)

         ierr=0
         self.VerbStart(_('Building byte-code files from %s...') % path)
         self._print()
         try:
            compileall.compile_dir(path, quiet=(self.verbose==False))
         except Exception, msg:
            ierr=iret=4
            self._print(msg)
         if self.verbose: self.VerbStart('')   # just for pretty print
         self.VerbEnd(ierr)
      if iret<>0:
         raise SetupInstallError(_('error during byte-code built'))

      self._print(self._fmt_leave % path)
      os.chdir(prev)

#-------------------------------------------------------------------------------
   def Chmod(self, **kargs):
      """Change mode of the 'files' to 'mode'.
      Pathnames are relative to installdir or to 'path' argument.
      """
      self._print(self._fmt_title % _('Set files permission'))
      chglist = kargs.get('files', [])
      try:
         mode    = int(kargs.get('mode', 0644))
      except ValueError:
         self.exit_code=4
         raise SetupChmodError(_("an integer is required for 'mode'"))
      path=kargs.get('path', self.installdir)
      path = self.special_vars(path)

      if not osp.isdir(path):
         self.exit_code=4
         raise SetupChgFilesError(_('directory not exists %s') % path)

      prev=os.getcwd()
      self._print(self._fmt_enter % path)
      os.chdir(path)

      if kargs.get('external')<>None:
         self._call_external(**kargs)

      else:
         for f0 in chglist:
            for f in glob.glob(f0):
               iret=0
               self.VerbStart(_('applying chmod %04o to %s') % (mode,f))
               if osp.isfile(f):
                  try:
                     os.chmod(f, mode)
                  except OSError:
                     iret=4
                  self.VerbEnd(iret)
               else:
                  self.VerbIgnore()

      self._print(self._fmt_leave % path)
      os.chdir(prev)

#-------------------------------------------------------------------------------
   def Check(self, **kargs):
      """Check if installation was successfull.
         path    : directory to build
      """
      self._print(self._fmt_title % _('Check for installation'))
      command = kargs.get('command')
      path    = kargs.get('path', osp.join(self.workdir,self.content))
      path = self.special_vars(path)
      if command==None:
         command='make check'

      if not osp.isdir(path):
         self.exit_code=4
         raise SetupConfigureError(_('directory not exists %s') % path)

      prev=os.getcwd()
      self._print(self._fmt_enter % path)
      os.chdir(path)

      if kargs.get('external')<>None:
         self._call_external(**kargs)

      else:
         self._print(_('Command line :'), command)
         iret,output=self.Shell(command, follow_output=self.verbose,
               alt_comment=_('checking %s installation...') % self.product)
         if iret<>0:
            if not self.verbose: self._print(output)
            self.exit_code=4
            raise SetupCheckError(_('error during checking installation'))

      self._print(self._fmt_leave % path)
      os.chdir(prev)

#-------------------------------------------------------------------------------
   def Clean(self, **kargs):
      """Clean working directory.
         'to_delete' : list of objects to delete
      Pathnames are relative to workdir or to 'path' argument.
      """
      self._print(self._fmt_title % _('Clean temporary objects'))
      to_del = kargs.get('to_delete', [self.content])
      path   = kargs.get('path', self.workdir)
      if not type(to_del) in EnumTypes:
         to_del=[to_del]

      prev=os.getcwd()
      self._print(self._fmt_enter % path)
      os.chdir(path)

      for obj in [osp.abspath(o) for o in to_del]:
         iret,output=self.Shell(cmd='rm -rf '+obj,
               alt_comment=_('deleting %s...') % obj)
      try:
         os.rmdir(self.workdir)
         self._print(_('deleting %s...') % self.workdir)
      except:
         pass

      self._print(self._fmt_leave % path)
      os.chdir(prev)

#-------------------------------------------------------------------------------
   def special_vars(self, ch):
      """Insert in `ch` the content of "special vars" (attributes).
      """
      auth_vars = ['product', 'version', 'content',
         'workdir', 'installdir', 'sourcedir']
      for var in auth_vars:
         spv = '__setup.%s__' % var
         if ch.find(spv) > -1:
            ch = ch.replace(spv, getattr(self, var))
      return ch

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
class DEPENDENCIES:
   """Class to store dependencies between products.
   Attributes :
      prod_req : dict where keys are products names and values the list of
         variables required by them,
      req_prod : reverse of prod_req,
      prod_set : dict where keys are products names and values the list of
         variables set by them,
      set_prod : reverse of prod_set,
      req_obj  : dict product : required objects (only tested by LastCheck),
      cfg      : dictionnary containing parameters values,
      cache    : cache filename,
      debug    : debug mode.
   """
   _separ='\n' + '-'*80 + '\n'
#-------------------------------------------------------------------------------
   def __init__(self, **kargs):
      """Constructor
      """
      self.cfg=kargs.get('cfg', {})
      self.cache=kargs.get('cache', {})
      self._print = kargs['log']._print

      # external methods
      system=kargs.get('system')
      if system==None:
         raise SetupError(_("Argument not found 'system'"))
      self.debug      = system.debug
      self.Shell      = system.local_shell
      self.VerbStart  = system.VerbStart
      self.VerbIgnore = system.VerbIgnore
      self.VerbEnd    = system.VerbEnd

      self.prod_req = {}
      self.req_prod = {}
      self.prod_set = {}
      self.set_prod = {}
      self.req_obj  = {}
      if kargs.get('req')<>None or kargs.get('set')<>None:
         self.Add('__main__', kargs.get('req', []), kargs.get('set', []))

#-------------------------------------------------------------------------------
   def PrintContent(self, **kargs):
      """Print content
      """
      self._print(self._separ, ('Content of cfg :'))
      self._print(self.cfg)
      self._print(_('\nProducts prerequisites :'))
      self._print(self.prod_req)
      self._print(_('\nProducts which require these variables :'))
      self._print(self.req_prod)
      self._print(_('\nVariables set by products :'))
      self._print(self.prod_set)
      self._print(_('\nProducts which set these variables :'))
      self._print(self.set_prod)

#-------------------------------------------------------------------------------
   def Add(self, product, req=None, set=None, reqobj=None):
      """Add dependencies of 'product'.
      'req' should contains all variables set before this product setup.
      Required variables that could be deduced from others should only be
      in 'set'.
      'reqobj' contains names of objects (actually only files) required.
      """
      if req is None:
         req = []
      if set is None:
         set = []
      if reqobj is None:
         reqobj = []
      def check_varname(v):
         d={}
         try:
            exec(v+'=0') in d
         except Exception, msg:
            raise SetupError(_(' invalid variable name %s' % repr(v)))

      if not self.prod_req.has_key(product): self.prod_req[product]=[]
      if not self.prod_set.has_key(product): self.prod_set[product]=[]
      if not self.req_obj.has_key(product):  self.req_obj[product]=[]

      # takes from req only variables not set by product
      for r in [r for r in req if not r in set]:
         check_varname(r)
         self.prod_req[product].append(r)
         if not self.req_prod.has_key(r): self.req_prod[r]=[]
         self.req_prod[r].append(product)
      for s in set:
         check_varname(s)
         self.prod_set[product].append(s)
         if not self.set_prod.has_key(s): self.set_prod[s]=[]
         self.set_prod[s].append(product)

      for o in reqobj:
         self.req_obj[product].append(o)

      # check
      self.CheckDepVal(product)

      # set variables are considered as required
      for r in set:
         check_varname(r)
         self.prod_req[product].append(r)
         if not self.req_prod.has_key(r): self.req_prod[r]=[]
         self.req_prod[r].append(product)

#-------------------------------------------------------------------------------
   def CheckDepVal(self, product='all'):
      """Check for dependencies, values setting and permission.
      """
      if self.debug:
         self._print('PASSAGE CHECKDEPVAL product='+product, self._separ, term='')
         self.PrintContent()

      self._print(self._separ, term='')
      self.VerbStart(_('Checking for dependencies and required ' \
            'variables for %s...') % repr(product))
      iret, lerr = self.Check(product)
      if iret<>0: self.VerbStart('')   # just for pretty print if fails
      self.VerbEnd(iret)
      if iret<>0:
        raise SetupError(_('inconsistent dependencies or missing variables'\
               +'\n     Problem with : %s') % ', '.join(lerr))

#-------------------------------------------------------------------------------
   def Check(self, product='all', check_deps=True, check_values=True):
      """Check for dependencies.
      """
      iret=0
      lerr=[]
      if product=='all':
         product=self.prod_req.keys()
      if not type(product) in EnumTypes:
         product=[product,]
      for p in product:
         if not self.prod_req.has_key(p):
            iret=-1
            self._print()
            self._print(_(' No dependencies found for %s') % repr(p))
         else:
            for v in self.prod_req[p]:
               err=0
               if check_values and not self.cfg.has_key(v):
                  iret+=1
                  err=1
                  lerr.append(v)
                  if iret==1: self._print()
                  self._print(_(' %15s is required by %s but not set.') % (v, repr(p)))
               if check_deps and not v in self.set_prod.keys() and err==0:
                  iret+=1
                  lerr.append(v)
                  if iret==1: self._print()
                  self._print(_(' %15s is required by %s') % (v, repr(p)))
      return iret, lerr

#-------------------------------------------------------------------------------
   def LastCheck(self, product='all'):
      """Check for required objects are present.
      """
      iret=0
      lerr=[]
      if product=='all':
         product=self.req_obj.keys()
      if not type(product) in EnumTypes:
         product=[product,]
      for p in product:
         if not self.req_obj.has_key(p):
            iret=-1
            self._print()
            self._print(_(' No objects dependencies found for %s') % repr(p))
         else:
            for v in self.req_obj[p]:
               typ=v.split(':')[0]
               val=''.join(v.split(':')[1:])
               if typ=='file':
                  vf=_chgline(val, self.cfg)
                  if not osp.exists(vf):
                     iret+=1
                     lerr.append(vf)
                     self._print(_(' %s requires this file : %s') % (repr(p), vf))
               else:
                  raise SetupError(_('unknown type of object : %s') % typ)
      if iret>0:
        raise SetupError(_('missing objects'\
               +'\n     Problem with : %s') % ', '.join(lerr))

#-------------------------------------------------------------------------------
   def FillCache(self, product='all', only=None):
      """Fill cache file with all values set by product if `only` is None
      or only these of `only` list.
      NOTE : call it only if you are sure variables are set !
      """
      lerr=[]
      if product=='all':
         product=self.prod_req.keys()
      if not type(product) in EnumTypes:
         product=[product,]

      # fill cache file with values set by product(s)
      self.VerbStart(_('Filling cache...'))
      iret=0
      f=open(self.cache, 'a')
      for p in product:
         f.write('\n# Variables set by %s at %s\n' % \
               (repr(p),time.strftime('%c')))
         if type(only) in EnumTypes:
            l_vars = only[:]
         else:
            l_vars = self.prod_set[p]
         # alphabetical sort (easier to read)
         l_vars.sort()
         for v in l_vars:
            if self.cfg.has_key(v):
               f.write('%s = %s\n' % (v, repr(self.cfg[v])))
            else:
               iret=255
               self._print()
               lerr.append(v)
               self._print(_(' %15s not yet defined' % repr(v)))
      f.close()
      if iret<>0: self.VerbStart('')   # just for pretty print if fails
      self.VerbEnd(iret)
      if iret<>0:
         raise SetupError(_('unavailable variables' \
               +'\n     Problem with : %s') % ', '.join(lerr))

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
class SUMMARY:
   """This class collects informations about product installations as
   diagnostic, exception raised if any...
   """
   _separ='\n' + '-'*80 + '\n'
   _fmt_title=_separ + '      %s' + _separ
   _fmt_sum=_(""" Installation of   : %(product)s %(version)s
 Destination       : %(installdir)s
 Elapsed time      : %(time).2f s""")
   _fmt_except=_('\n *** Exception %s raised : %s\nSee detailed traceback in' \
         ' the logfile')
#-------------------------------------------------------------------------------
   def __init__(self, list_of_products, **kargs):
      self.products=list_of_products
      self.diag={}

      # external methods
      system=kargs.get('system')
      self._print = kargs['log']._print
      if system==None:
         raise SetupError(_("Argument not found 'system'"))
      self.Shell      = system.local_shell
      self.VerbStart  = system.VerbStart
      self.VerbIgnore = system.VerbIgnore
      self.VerbEnd    = system.VerbEnd

      self._glob_title = "MUMPS Benchmark + %d of its prerequisites" % len(self.products)
      self._t_ini = kargs.get('t_ini') or time.time()
      for p in self.products:
         self.diag[p]={
            'product'      : p,
            'version'      : '(version unavailable)',
            'installdir'   : 'unknown',
            'exit_code'    : None,
            'time'         : 0.,
            'tb_info'      : None,
         }


   def SetGlobal(self, aster_root, version):
      """Set informations for mumps_benchmark-full
      """
      self.diag[self._glob_title] = {
            'product'      : self._glob_title,
            'version'      : version,
            'installdir'   : aster_root,
            'exit_code'    : 0,
            'time'         : 0.,
            'tb_info'      : None,
      }

#-------------------------------------------------------------------------------
   def Set(self, product, setup, dt, traceback_info=None):
      """Set informations about a product installation.
      """
      if isinstance(setup, SETUP):
         self.diag[product].update({
            'version'      : setup.version,
            'installdir'   : setup.installdir,
            'exit_code'    : setup.exit_code,
         })
      else:
         self.diag[product]['exit_code']=4
      self.diag[product]['time']=dt
      if traceback_info<>None:
         self.diag[product]['tb_info']=traceback_info
      sys.exc_clear()

#-------------------------------------------------------------------------------
   def Print(self):
      """Return a representation of the SUMMARY object
      """
      self.diag[self._glob_title]['time'] = time.time() - self._t_ini

      self._print(self._fmt_title % _('SUMMARY OF INSTALLATION'))
      for p in self.products + [self._glob_title,]:
         self.VerbStart(self._fmt_sum % self.diag[p])
         if self.diag[p]['exit_code']==None:
            self.VerbIgnore()
         else:
            if self.diag[p]['exit_code']<>0:
               self._print(self._fmt_except % self.diag[p]['tb_info'][:2])
#                traceback.print_tb(self.diag[p]['tb_info'][2])
               self.VerbStart('')   # just for pretty print if fails
            self.VerbEnd(self.diag[p]['exit_code'])

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
def _exitcode(status, default=99):
   """Extrait le code retour du status. Retourne `default` si le process
   n'a pas fini par exit.
   """
   if os.WIFEXITED(status):
      iret = os.WEXITSTATUS(status)
   elif os.WIFSIGNALED(status):
      iret = os.WTERMSIG(status)
   elif os.WIFSTOPPED(status):
      iret = os.WSTOPSIG(status)
   else:
      iret = default
   return iret

#-------------------------------------------------------------------------------
_command_id = 0
def get_command_id():
    """Return a unique identifier for command started by 'local_shell'.
    """
    global _command_id
    _command_id += 1
    return '%d_%08d' % (os.getpid(), _command_id)

def get_command_line(cmd_in, bg, follow_output, separated_stderr,
                     output_filename, error_filename, var_exitcode):
    """Returns the command to run to redirect output/error, retreive exit code
    """
    command = {
        'foreground' : '( %(cmd)s ) > /dev/null 2>&1',
        'background' : '( %(cmd)s ) > /dev/null 2>&1 &',
        'follow_with_stderr' : '( %(cmd)s ; echo %(var)s=$? ) 2>&1 | tee %(output)s',
        'follow_separ_stderr' : '( %(cmd)s ; echo %(var)s=$? ) 2> %(error)s | tee %(output)s',
        'not_follow_with_stderr' : '( %(cmd)s ) > %(output)s 2>&1',
        'not_follow_separ_stderr' : '( %(cmd)s ) > %(output)s 2> %(error)s',
        'rm_file' : '\\rm -f %(args)s',
        'rm_dirs' : '\\rm -rf %(args)s',
        'copy' : 'cp -L -r %(args)s',
        'ping' : 'ping -c 1 -W %(timeout)s %(host)s',
        'shell_cmd' : "bash -c",
        'file' : "file %(args)s",
        'hostid' : 'ifconfig',
    }
    values = {
        'cmd' : cmd_in.replace(os.linesep, ''),
        'output' : output_filename,
        'error' : error_filename,
        'var' : var_exitcode,
    }
    if bg:
        # new_cmd = cmd + ' &' => NO : stdout/stderr must be closed not to block
        new_cmd = command['background'] % values
    elif follow_output:
        if not separated_stderr:
            new_cmd = command['follow_with_stderr'] % values
        else:
            new_cmd = command['follow_separ_stderr'] % values
    else:
        if not separated_stderr:
            new_cmd = command['not_follow_with_stderr'] % values
        else:
            new_cmd = command['not_follow_separ_stderr'] % values
    #print3(u"Command :", new_cmd)
    # may happen if tmpdir has been deleted before another one, just before exit.
    if not osp.isdir(osp.dirname(output_filename)):
        new_cmd = command['foreground'] % values
    return new_cmd

def get_tmpname_base(dirname=None, basename=None):
    """Return a name for a temporary directory (*not created*)
    of the form : 'dirname'/user@machine-'basename'.'pid'
    *Only* basename is not compulsory in this variant.
    """
    basename = basename or 'tmpname-%.6f' % time.time()
    pid = "pid-%.6f" % time.time()
    root, ext = osp.splitext(basename)
    name = root + '.' + str(pid) + ext
    return osp.join(dirname, name)


class SYSTEM:
   """Class to encapsultate "system" commands (this a simplified version of
   ASTER_SYSTEM class defined in ASTK_SERV part).
   """
   # this value should be set during installation step.
   MaxCmdLen=1024
   # line length -9
   _LineLen=80-9
#-------------------------------------------------------------------------------
   def __init__(self, run, **kargs):
      """run : dictionnary to define 'verbose', 'debug'
      """
      self.verbose   = run['verbose']
      self.debug     = run['debug']
      self._print = kargs['log']._print
      self._tmpdir = osp.join(kargs.get('tmpdir', '/tmp'),
                                           'system.%s' % os.getpid())
      if not osp.exists(self._tmpdir):
         os.makedirs(self._tmpdir)
      if kargs.has_key('maxcmdlen'):
         self.MaxCmdLen = kargs['maxcmdlen']

#-------------------------------------------------------------------------------
   def _mess(self,msg,cod=''):
      """Just print a message
      """
      self._print('%-18s %s' % (cod,msg))

#-------------------------------------------------------------------------------
   def VerbStart(self,cmd,verbose=None):
      """Start message in verbose mode
      """
      Lm=self._LineLen
      if verbose==None:
         verbose=self.verbose
      if verbose:
         pcmd=cmd
         if len(cmd)>Lm-2 or cmd.count('\n')>0:
            pcmd=pcmd+'\n'+' '*Lm
         self._print(('%-'+str(Lm)+'s') % (pcmd,), term='')
         #sys.stdout.flush()  done by _print

#-------------------------------------------------------------------------------
   def VerbEnd(self,iret,output='',verbose=None):
      """Ends message in verbose mode
      """
      if verbose==None:
         verbose=self.verbose
      if verbose:
         if iret==0:
            self._print('[  OK  ]')
         else:
            self._print(_('[FAILED]'))
            self._print(_('Exit code : %d') % iret)
         if (iret<>0 or self.debug) and output:
            self._print(output)

#-------------------------------------------------------------------------------
   def VerbIgnore(self,verbose=None):
      """Ends message in verbose mode
      """
      if verbose==None:
         verbose=self.verbose
      if verbose:
         self._print('[ SKIP ]')

#-------------------------------------------------------------------------------
   def local_shell(self, cmd, bg=False, verbose=None, follow_output=False,
                   alt_comment=None, interact=False, capturestderr=True,
                   **ignore_args):
        """Execute a command shell
            cmd           : command
            bg            : put command in background if True
            verbose       : print status messages during execution if True
            follow_output : follow interactively output of command
            alt_comment   : print this "alternative comment" instead of "cmd"
        Return :
            iret     : exit code if bg = False,
                    0 if bg = True
            output   : output lines (as string)
        """
        separated_stderr = not capturestderr
        if not alt_comment:
            alt_comment = cmd
        if verbose==None:
            verbose=self.verbose
        if bg:
            interact=False
        if len(cmd) > self.MaxCmdLen:
            self._mess((_('length of command shell greater '\
                    'than %d characters.') % self.MaxCmdLen), '<A>_ALARM')
        if self.debug:
            self._print('<local_shell>', cmd, DBG=True)
        self.VerbStart(alt_comment, verbose=verbose)
        if follow_output and verbose:
            self._print(_('\nCommand output :'))

        var_id = "EXIT_COMMAND_%s" % get_command_id()
        fout_name = get_tmpname_base(self._tmpdir, 'local_shell_output')
        ferr_name = get_tmpname_base(self._tmpdir, 'local_shell_error')
        new_cmd = get_command_line(cmd, bg, follow_output, separated_stderr,
                                   fout_name, ferr_name, var_id)
        # execution
        iret = os.system(new_cmd)
        iret = _exitcode(iret)
        output, error = "", ""
        try:
            output = open(fout_name, "r").read()
            os.remove(fout_name)
        except:
            pass
        try:
            error = open(ferr_name, "r").read()
            os.remove(ferr_name)
        except:
            pass

        if follow_output:
            # repeat header message
            self.VerbStart(alt_comment, verbose=verbose)
        mat = re.search('EXIT_CODE=([0-9]+)', output)
        if mat:
            iret = int(mat.group(1))
        elif follow_output:
            # os.system returns exit code of tee
            mat = re.search("%s=([0-9]+)" % var_id, output)
            if mat:
                iret = int(mat.group(1))
        self.VerbEnd(iret, output, verbose=verbose)
        self._print('ERROR : iret = %s' % iret, '+++ STANDARD OUTPUT:', output,
                    '+++ STANDARD ERROR:', error, '+++ END', DBG=True)
        if bg:
            iret = 0
        return iret, output

#-------------------------------------------------------------------------------
   def GetHostName(self, host=None):
      """Return hostname of the machine 'host' or current machine if None.
      """
      from socket import gethostname, gethostbyaddr
      if host==None:
         host = gethostname()
      try:
         fqn, alias, ip = gethostbyaddr(host)
      except:
         fqn, alias, ip = host, [], None
      if fqn.find('localhost')>-1:
         alias=[a for a in alias if a.find('localhost')<0]
         if len(alias)>0:
            fqn=alias[0]
         for a in alias:
            if a.find('.')>-1:
               fqn=a
               break
      return fqn

#-------------------------------------------------------------------------------
   def AddToEnv(self, profile, verbose=None):
      """Read 'profile' file (with sh/bash/ksh syntax) and add updated
      variables to os.environ.
      """
      def env2dict(s):
         """Convert output to a dictionnary."""
         l = s.split(os.linesep)
         d = {}
         for line in l:
            mat = re.search('^([-a-zA-Z_0-9@\+]+)=(.*$)', line)
            if mat != None:
               d[mat.group(1)] = mat.group(2)
         return d
      if verbose==None:
         verbose=self.verbose

      if not profile:
         return
      if type(profile) in (str, unicode):
         ftmp = osp.join(self._tmpdir, 'temp.opt_env')
         open(ftmp, 'w').write(profile)
         os.chmod(ftmp, 0755)
         profile = ftmp

      if not osp.isfile(profile):
         self._mess(_('file not found : %s') % profile, '<A>_FILE_NOT_FOUND')
         return
      # read initial environment
      iret, out = self.local_shell('sh -c env', verbose=verbose)
      env_init = env2dict(out)
      if iret != 0:
         self._mess(_('error getting environment'), '<E>_ABNORMAL_ABORT')
         return
      # read profile and dump modified environment
      iret, out = self.local_shell('sh -c ". %s ; env"' % profile, verbose=verbose)
      env_prof = env2dict(out)
      if iret != 0:
         self._mess(_('error reading profile : %s') % profile,
               '<E>_ABNORMAL_ABORT')
         return
      # "diff"
      for k, v in env_prof.items():
         if env_init.get(k, None) != v:
            if self.debug:
               self._print('AddToEnv adding : %s=%s' % (k, v), DBG=True)
            os.environ[k] = v
      for k in [k for k in env_init.keys() if env_prof.get(k) is None]:
         self._print('Unset %s ' % k, DBG=True)
         try:
            del os.environ[k]
         except:
            pass

#-------------------------------------------------------------------------------
def _getsubdirs(prefdirs, others, maxdepth=5):
   """Returns the list of subdirectories of 'prefdirs' and 'others' up to 'maxdepth'.
   Note that 'prefdirs' appear at the beginning of the returned list,
   followed by their subdirectories, then 'others', and their subdirectories.
   """
   new, dnew = [], {}   # dnew exists only for performance (order must be kept in new)
   for dirs in (prefdirs, others):
      if not type(dirs) in EnumTypes:
         dirs=[dirs]
      dirs=[osp.realpath(i) for i in dirs if i<>'']
      for d in dirs:
         if dnew.get(d) is None:
            new.append(d)
            dnew[d] = 1
      if maxdepth > 0:
         for d in dirs:
            level=len(d.split(osp.sep))
            for root, l_dirs, l_nondirs in os.walk(d):
               lev=len(root.split(osp.sep))
               if lev <= (level + maxdepth):
                  if dnew.get(root) is None:
                     new.append(root)
                     dnew[root] = 1
               else:
                  del l_dirs[:] # empty dirs list so we don't walk needlessly
   return new

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
class FIND_TOOLS:
   """Some utilities to find files, libraries...
   """
   _fmt_search  = _('Checking for %s... ')
   _fmt_test    = _('Checking if %s... ')
   _fmt_chkpref = _('Checking prefix for %s (%s)... ')
   _fmt_home    = _('adjust to %s')
   _fmt_locate  = _('(locate)... ')
   _fmt_yes     = _('yes')
   _fmt_no      = _('no')
   dict_rearch = {
      'x86'    : 'shell|script|80.86',
      'i86pc'  : 'shell|script|80.86',
      'x86_64' : 'shell|script|x86.64',
      'ppc64'  : 'shell|script|64-bit PowerPC',
      'ia64'   : 'shell|script|ia.64',
   }
#-------------------------------------------------------------------------------
   def __init__(self, **kargs):
      self._print       = kargs.get('log', None)._print
      self.maxdepth     = kargs.get('maxdepth', 0)
      self.use_locate   = kargs.get('use_locate', False)
      self.prefshared   = kargs.get('prefshared', False)
      self.paths        = {
         'bin'    : [],
         'lib'    : [],
         'inc'    : [],
         'pymod'  : [],
      }
      self.std_dirs     = {
         'bin'    : _clean_path(kargs.get('bindirs', []), returns='list'),
         'lib'    : _clean_path(kargs.get('libdirs', []), returns='list'),
         'inc'    : _clean_path(kargs.get('incdirs', []), returns='list'),
         'pymod'  : [],
      }
      self.tag2var = {
         'bin'   : 'PATH',
         'lib'   : 'LD_LIBRARY_PATH',
         'inc'   : 'INCLUDEPATH',   # should not be used
         'pymod' : 'PYTHONPATH',
      }
      self.var2tag = {}
      for k, v in self.tag2var.items():
         self.var2tag[v] = k
      for k in ('bin', 'lib', 'inc', 'pymod'):
         self._print("std_dirs['%s'] =" % k, self.std_dirs[k], DBG=True)

      self._ext_static  = '.a'
      self._ext_shared  = '.so'
      if sys.platform in ("win32", "cygwin"):
          self._ext_static = self._ext_shared = '.lib'  # but not yet supported!
      elif sys.platform == 'darwin':
          self._ext_shared = '.dylib'

      self.debug        = kargs.get('debug', False)
      self.Shell        = kargs['system'].local_shell
      self._tmpdir = kargs['system']._tmpdir
      self.arch         = kargs.get('arch', 'default')
      self.home_checked = []  # store vars which have already been checked
      self.noerror      = kargs.get('noerror', False)
      self._last_found  = None
      self._cache   = { 'bin' : {}, 'lib' : {}, 'inc' : {} }
      self._print('maxdepth = %s' % self.maxdepth, DBG=True)
      self.nbcpu = 1
      # "file" command
      self._command_file = None
      self._command_ar   = None
      self.configure_command_file()

   def clear_temporary_folder(self):
      os.system('rm -rf %s' % self._tmpdir)

#-------------------------------------------------------------------------------
   def configure_command_file(self):
      """Fill 'file' command arguments."""
      cmd = self.find_file('file', typ='bin')
      if cmd is None: # 'file' command not found !
         return
      # check for --dereference argument
      for arg in ('--dereference', '-L'):
         iret, out = self.Shell('%s %s %s' % (cmd, arg, cmd), verbose=self.debug)
         if iret == 0:
            cmd = '%s %s' % (cmd, arg)
            break
      self._command_file = cmd
      self._command_ar = self.find_file('ar', typ='bin')

#-------------------------------------------------------------------------------
   def check_type(self, filename, typ='bin', arch=None):
      """Check that 'filename' has the right type."""
      if arch is None:
         arch = self.arch
      # unable to call file or arch unknown
      if not self._command_file or arch == 'default':
         return True
      if not typ in ('bin', 'lib'):
         return True
      # search arch using regexp
      re_arch = re.compile(self.dict_rearch[arch], re.IGNORECASE)
      iret, out = self.Shell('%s %s' % (self._command_file, filename), verbose=self.debug)
      if iret != 0:
         self._print('ERROR <check_type>: %s' % out)
         return False
      else:
         if typ == 'lib':
            # ascii text : GROUP (list of libs) !
            if re.search('ascii', out, re.IGNORECASE) != None:
               content = open(filename, 'r').read()
               mlib = re.search('GROUP.*\((.*?)\)', content, re.IGNORECASE)
               if mlib:
                  dirn = osp.dirname(filename)
                  llibs = mlib.group(1).strip().split()
                  self._print('GROUP lib found, test %s' % llibs, DBG=True)
                  ok = True
                  for lib in llibs:
                     if not osp.exists(osp.join(dirn, lib)):
                        if lib[:2] == '-l':
                           lib = 'lib' + lib[2:]
                     lib = osp.join(dirn, lib)
                     if not osp.exists(lib):
                        libtest = [lib + self._ext_static, lib + self._ext_shared]
                     else:
                        libtest = [lib,]
                     elem = False
                     for lib in libtest:
                        elem = self.check_type(lib, typ, arch)
                        if elem: break
                     if not elem:
                        ok = False
                        break
                  return ok

            # dynamic lib : pass, static lib : extract the first object
            if re.search('archive', out, re.IGNORECASE) != None:
               # keep few lines and egrep .o to be sure to ignore comment or head line...
               jret, out2 = self.Shell('%s t %s | head -5 | egrep "\.o"' \
                        % (self._command_ar, filename), verbose=self.debug)
               if jret == 0:
                  prev = os.getcwd()
                  os.chdir(self._tmpdir)
                  doto = out2.splitlines()[0]
                  jret, out2 = self.Shell('%s x %s %s' % (self._command_ar, filename, doto),
                                          verbose=self.debug)
                  jret, out = self.Shell('%s %s' % (self._command_file, doto),
                                          verbose=self.debug)
                  os.chdir(prev)
      mat = re_arch.search(out)
      if mat is None:
         self._print('invalid type (%s): %s // %s' % (typ, filename, out), DBG=True)
      return mat is not None

#-------------------------------------------------------------------------------
   def check_compiler_name(self, compiler, name):
      """Returns True/False the 'compiler' matches 'name'.
      """
      self._print(self._fmt_test % ('%s is %s' % (compiler, name)), term='')
      iret, out, outspl = self.get_product_version(compiler)
      res = False
      comment = ''
      if len(outspl) >= 3:
         res = name.lower() in (outspl[0].lower(), outspl[1].lower())
         comment = '   %s version %s' % tuple(outspl[1:3])
      if res:
         self._print(self._fmt_yes, term='')
      else:
         self._print(self._fmt_no, term='')
      self._print(comment)
      self._print('check_compiler_name  out =', out, DBG=True)
      return res

#-------------------------------------------------------------------------------
   def check_compiler_version(self, compiler):
      """Prints 'compiler' version.
      """
      self._print(self._fmt_search % 'compiler version', term='')
      iret, out, outspl = self.get_product_version(compiler)
      l_out = out.splitlines()
      if len(l_out) > 0:
         rep = l_out[0]
      else:
         rep = '?'
      self._print(rep)
      return rep, outspl


   def get_cpu_number(self):
      """Returns the number of processors."""
      self._print(self._fmt_search % 'number of processors (core)', term='')
      if sys.platform == 'darwin':
         try:
             self.nbcpu = int(os.popen('sysctl -n hw.ncpu').read())
         except ValueError:
             pass
      else:
         iret, out = self.Shell('cat /proc/cpuinfo', verbose=self.debug)
         exp = re.compile('^processor\s+:\s+([0-9]+)', re.MULTILINE)
         l_ids = exp.findall(out)
         if len(l_ids) > 1:      # else: it should not !
            self.nbcpu = max([int(i) for i in l_ids]) + 1
      self._print(self.nbcpu)


   def get_path_typ(self, dict_list, typ):
      """Returns dict_list[typ] or more."""
      res = dict_list.get(typ)
      if res is None:
         res = dict_list['bin'] + dict_list['lib'] + dict_list['inc']
      else:
         res = res[:]
      return res

#-------------------------------------------------------------------------------
   def find_file(self, filenames, paths=None, maxdepth=None, silent=False,
                 addto=None, typ='all', with_locate=False):
      """Returns absolute path of the first of 'filenames' located
      in paths+std_dirs (so search from paths first) or None if no one was found.
      """
      self._last_found = None
      if not type(filenames) in EnumTypes:
         filenames=[filenames,]
      if paths is None:
         paths = []
      if not type(paths) in EnumTypes:
         paths=[paths,]
      # give maximum chances to 'paths'
      paths = paths[:]
      paths.extend(self.get_path_typ(self.paths, typ))
      if maxdepth==None:
         maxdepth=self.maxdepth
      for name in filenames:
         if not silent:
            if not with_locate:
               self._print(self._fmt_search % name, term='')
            else:
               self._print(self._fmt_locate, term='')
         # Check the user's directories and then standard locations
         std_dirs = self.get_path_typ(self.std_dirs, typ)
         self._print('search_dirs : %s' % repr(paths), DBG=True)
         search_dirs=_getsubdirs(paths, std_dirs, maxdepth)
         if self.debug:
            self._print('search_dirs : \n%s' % os.linesep.join(search_dirs), DBG=True)
         for dir in search_dirs:
            f = osp.join(dir, name)
            if osp.exists(f):
               self._last_found = osp.abspath(f)
               chk = self.check_type(self._last_found, typ=typ)
               if chk:
                  if not silent:
                     self._print(self._last_found)
                  return self._last_found
         # try this 'name' using locate
         ldirs = self.locate(name, addto=addto, typ=typ)
         if len(ldirs) > 0 and not with_locate:
            found = self.find_file(name, ldirs, maxdepth, silent, typ=typ, with_locate=True)
            if found:
               return found
         elif not silent:
            self._print(self._fmt_no)
         # not found try next item of 'filenames'
      # Not found anywhere
      return None

#-------------------------------------------------------------------------------
   def locate(self, filenames, addto=None, typ='bin'):
      """Returns dirname (none, one or more, always as list) of 'filename'.
      If addto != None, addto dirnames into 'addto'.
      """
      dnew = []
      if not self.use_locate:
         return dnew
      if addto is None:
         addto = []
      assert type(addto) is list, _('"addto" argument must be a list !')
      if not type(filenames) in (list, tuple):
         filenames=[filenames,]
      for name in filenames:
         iret, out = self.Shell('locate %s | egrep "/%s$"' % (name, name),
                           verbose=self.debug)
         if iret == 0:
            dirn = [osp.dirname(d) for d in out.splitlines()]
            for f in out.splitlines():
               if typ != 'bin' or (os.access(f, os.X_OK) and osp.isfile(f)):
                  d = osp.dirname(f)
                  if not d in addto:
                     dnew.append(d)
      addto.extend(dnew)
      return dnew

#-------------------------------------------------------------------------------
   def find_and_set(self, cfg, var, filenames, paths=None, err=True,
         typ='bin', append=False, maxdepth=None, silent=False, prefix_to=None,
         reqpkg=None):
      """Uses find_file to search 'filenames' in paths.
      - If 'err' is True, raises SetupConfigureError if no one was found and
        print a message in reqpkg is set.
      - Value set in cfg[var] depends on 'typ' :
         typ='bin' : cfg[var]='absolute filename found'
         typ='inc' : cfg[var]='-Idirname'
         typ='lib' : cfg[var]='static lib' name or '-Ldirname -llib'
      - If cfg[var] already exists :
         if 'append' is False, cfg[var] is unchanged ('previously set' message)
         if 'append' is True, new found value is appended to cfg[var]
      - prefix_to allows to adjust the value with _real_home
        (only used for includes).
      """
      conv = { 'bin' : 'bin', 'inc' : 'include', 'lib' : 'lib' }
      if not type(filenames) in EnumTypes:
         filenames=[filenames,]
      if maxdepth==None:
         maxdepth=self.maxdepth
      # insert in first place 'cfg[var]'/"type"
      if paths is None:
         paths = []
      if not type(paths) in EnumTypes:
         paths=[paths,]
      # give maximum chances to 'paths'
      paths_in = paths[:]
      for p in paths:
         paths_in.append(osp.join(p, conv[typ]))
      paths = paths_in
      self._print('find_and_set %s' % filenames, DBG=True)
      if cfg.has_key(var):
         paths.insert(0, osp.join(cfg[var], conv[typ]))
         paths.insert(0, osp.dirname(cfg[var]))
      if not cfg.has_key(var) or append:
         found=self.find_file(filenames, paths, maxdepth, silent, typ=typ)
         adj = self._real_home(found, prefix_to)
         if found == None:
            if cfg.has_key(var) and not append:
               del cfg[var]
            elif not cfg.has_key(var) and append:
               cfg[var]=''
            if err and not self.noerror:
                msg = get_install_message(package=reqpkg, missed=' or '.join(filenames))
                raise SetupConfigureError(msg)
         else:
            root, ext = osp.splitext(found)
            dirname   = osp.abspath(osp.dirname(root))
            basename  = osp.basename(root)
            if typ == 'lib':
               if ext == self._ext_shared:
                  found = '-L%s -l%s' % (dirname, re.sub('^lib', '', basename))
            elif typ == 'inc':
               if adj != None:
                  dirname = adj
               found = '-I%s' % dirname
            if not cfg.has_key(var) or not append:
               cfg[var] = found
            elif cfg[var].find(found) < 0:
               cfg[var] = (cfg[var] + ' ' + found).strip()
            self.AddToPath(typ, found)
      else:
         self._print(self._fmt_search % ' or '.join(filenames), term='')
         self._print(_("%s (previously set)") % cfg[var])
         # append = False donc on peut appeler AddToPath
         self.AddToPath(typ, cfg[var])

#-------------------------------------------------------------------------------
   def findlib_and_set(self, cfg, var, libname, paths=None,
                    err=True, append=False, prefshared=None,
                    maxdepth=None, silent=False, prefix_to=None, reqpkg=None):
      """Same as find_and_set but expands 'libname' as static and shared
      library filenames.
      """
      l_exts=[self._ext_static, self._ext_shared]
      if maxdepth==None:
         maxdepth=self.maxdepth
      if prefshared==None:
         prefshared=self.prefshared
      if prefshared:
         l_exts.reverse()
      if not type(libname) in EnumTypes:
         libname=[libname,]
      if paths is None:
         paths = []
      if not type(paths) in EnumTypes:
         paths=[paths,]
      l_names = []
      for name in libname:
         found = self._cache['lib'].get(name)
         if found:
            self._print(self._fmt_search % name, term='')
            self._print(_("%s (already found)") % found)
            if not cfg.has_key(var) or not append:
               cfg[var] = found
            elif cfg[var].find(found) < 0:
               cfg[var] = (cfg[var] + ' ' + found).strip()
            return
         if name.find('/') > 0 or name.find('.') > 0:
            l_names.append(name)
         l_names.extend(['lib'+name+ext for ext in l_exts])
      #XXX perhaps we should add the same paths with lib64 first on 64 bits platforms ?
      pathlib = [osp.join(p, 'lib') for p in paths]
      paths = pathlib + paths
      self.find_and_set(cfg, var, l_names, paths, err, 'lib', append, maxdepth,
                        silent, prefix_to, reqpkg)

#-------------------------------------------------------------------------------
   def AddToCache(self, typ, var, value):
      """Store value to cache (only for libs)."""
      assert typ == 'lib'
      self._cache[typ][var] = value

#-------------------------------------------------------------------------------
   def AddToPath(self, typ, var):
      """Get the directory of object of type 'typ' from 'var', and add it
      to corresponding paths items.
      'var' is supposed to be a result of find_and_set.
      """
      if not type(var) in StringTypes:
         return
      toadd=[]
      if   typ=='bin':
         for v in var.split():
            toadd.append(osp.dirname(v))
      elif typ=='lib':
         for v in var.split():
            if   v[:2]=='-L':
               toadd.append(v[2:])
            elif v[:2]=='-l':
               pass
            elif osp.isabs(v):
               toadd.append(osp.dirname(v))
      elif typ=='inc':
         for v in var.split():
            if v[:2]=='-I':
               toadd.append(v[2:])
            elif osp.isabs(v):
               if v.endswith('.h'):
                  toadd.append(osp.dirname(v))
               else:
                  toadd.append(v)
      elif typ=='pymod':
         for v in var.split():
            if osp.isabs(v):
               toadd.append(v)
      else:
         raise SetupError(_('unexpected type %s') % repr(typ))
      self._print("AddToPath .paths['%s'] =" % typ, self.paths[typ], DBG=True)
      for elt in toadd:
         if elt != '' and not elt in self.paths[typ]:
            if elt in self.std_dirs[typ]:
               self.paths[typ].append(elt)
               self._print('AddToPath OUT append %s : %s' % (typ, elt), DBG=True)
            else:
               self.paths[typ].insert(0, elt)
               self._print('AddToPath OUT insert %s : %s' % (typ, elt), DBG=True)

#-------------------------------------------------------------------------------
   def GetPath(self, typ, add_cr=False):
      """Returns a representation of paths[typ] to set an environment variable.
      """
      if not self.paths.has_key(typ):
         raise SetupError(_('unexpected type %s') % repr(typ))
      res = _clean_path(self.paths[typ])
      if add_cr:
         res = res.replace(':', ':\\' + os.linesep)
      return res

#-------------------------------------------------------------------------------
   def AddToPathVar(self, dico, key, new, export_to_env=True):
      """Add a path to a variable. If `export_to_env` is True, add the value
      into environment.
      """
      value_in = dico.get(key, '')
      if export_to_env:
         value_in = os.environ.get(key, '') + ':' + value_in
      lpath = value_in.split(':')
      if new is None:
         new = self.GetPath(self.var2tag[key]).split(':')
      else:
         self.AddToPath(self.var2tag[key], new)
      if type(new) not in (list, tuple):
         new = [new,]
      for p in new:
         if not p in lpath:
            lpath.append(p)
      dico[key] = _clean_path(lpath)
      if export_to_env:
         os.environ[key] = dico[key]
         self._print('AddToPathVar set %s = %s' % (key, dico[key]), DBG=True)

#-------------------------------------------------------------------------------
   def GccPrintSearchDirs(self, compiler):
      """Use 'compiler' --print-search-dirs option to add some reliable paths.
      """
      self._print(self._fmt_search % '%s configured installation directory' % compiler, term='')
      iret, out = self.Shell('%s -print-search-dirs' % compiler, verbose=self.debug)
      lines = out.splitlines()
      ldec = []
      for lig in lines:
         ldec.extend(re.split('[=: ]+', lig))
      # le prefix est normalement sur la premiere ligne,
      # on essaie de ne garder que celui-ci
      ldirs = [osp.normpath(p) for p in ldec if p.startswith(os.sep)][:1]
      if len(ldirs) > 0:
         pref = ldirs[0]
         self.AddToPath('bin', osp.join(pref, 'bin'))
         self.AddToPath('lib', osp.join(pref, 'lib'))
         self.AddToPath('bin', compiler)
         prefbin = osp.dirname(compiler)
         if prefbin != pref:
            self.AddToPath('lib', prefbin)
            pref = ', '.join([pref, prefbin])
      else:
         pref = 'not found'
      self._print(pref)

#-------------------------------------------------------------------------------
   def CheckFromLastFound(self, cfg, var, search):
      """Call _real_home and set the value in cfg[var].
      """
      val_in = self._last_found or ''
      self._print(self._fmt_chkpref % (var, val_in), term='')
      if val_in == '':
         self._print(_('unchanged'))
         return
      res = self._real_home(val_in, search)
      if search == 'lib' and self.arch.find('64') > -1:
          res64 = self._real_home(val_in, 'lib64')
          if res64:
              if res and len(res64) > len(res):
                  res = res64
      if res != None:
         self._print(self._fmt_home % res)
         cfg[var] = res
      else:
         self._print(_('%s not found in %s') % (search, val_in))

#-------------------------------------------------------------------------------
   def _real_home(self, path, search):
      """Checks that the path contains 'search' (starting from the end of 'path').
      Return the parent of 'search' if found or None.
      """
      if not (type(path) in StringTypes and type(search) in StringTypes):
         return None
      p = path.split(os.sep)
      np = len(p)
      s = search.split(os.sep)
      ns = len(s)
      val = None
      for i in range(np):
         if p[np-1-i:np-1-i+ns] == s:
            val = os.sep.join(p[:np-1-i])
            break
      return val

#-------------------------------------------------------------------------------
   def pymod_exists(self, module):
      """Checks if `module` is installed.
      """
      return check_pymodule(module)

#-------------------------------------------------------------------------------
   def check(self, func, name, silent=False, format='search'):
      """Execute a function for checking 'name'. 'func' returns True/False.
      Used to have the same output as searching files.
      """
      if not silent:
         if format == 'test':
            fmt = self._fmt_test
         else:
            fmt = self._fmt_search
         self._print(fmt % name, term='')
      # boolean or function
      if func is None:
         self._print()
         return None
      elif type(func) in (str, unicode):
         self._print(func)
         return None
      elif type(func) is bool:
         response = func
      else:
         try:
            response = func()
         except None:
            response = False
      if response:
         self._print(self._fmt_yes)
      else:
         self._print(self._fmt_no)
      return response

#-------------------------------------------------------------------------------
   def get_product_version(self, product, arg='--version'):
      """Returns the output of 'product' --version.
      """
      command = '%s %s' % (product, arg)
      iret, out = self.Shell(command, verbose=False)
      expr = re.compile('(.*)[ \t]+\((.*)\)[ \t]+(.*?)[ \(].*', re.MULTILINE)
      mat = expr.search(out)
      if mat is not None:
         outspl = mat.groups()
      else:
         outspl = out.split()
      return iret, out, outspl


def less_than_version(vers1, vers2):
   return version2tuple(vers1) < version2tuple(vers2)


def version2tuple(vers_string):
   """1.7.9alpha --> (1, 7, 9, 'alpha'), 1.8 --> (1, 8, 0, 'final')"""
   tupl0 = vers_string.split('.')
   val = []
   for v in tupl0:
      m = re.search('(^[ 0-9]+)(.*)', v)
      if m:
         val.append(int(m.group(1)))
         if m.group(2):
            val.append(m.group(2).replace('-', '').replace('_', '').strip())
      else:
         val.append(v)
   val.extend([0]*(3-len(val)))
   if type(val[-1]) in (int, long):
      val.append('final')
   return tuple(val)


def export_parameters(setup_object, dict_cfg, filename, **kwargs):
   """Export config dict into filename."""
   content = """parameters = %s""" % pprint.pformat(dict_cfg)
   print content
   print filename
   open(filename, 'w').write(content)


def check_pymodule(name, path=None):
    """Check if a python module exists."""
    exists = True
    lmod = name.split('.')
    curmod = lmod[0]
    try:
        res = imp.find_module(curmod, path)
    except Exception:
        return False
    if len(lmod) > 1:
        try:
            curobj = imp.load_module(curmod, *res)
            exists = check_pymodule('.'.join(lmod[1:]), path=curobj.__path__)
        except:
            exists = False
    return exists


def get_absolute_path(path, follow_symlink=True):
    """Retourne le chemin absolu en suivant les liens éventuels.
    """
    if follow_symlink and osp.islink(path):
        path = osp.realpath(path)
    res = osp.normpath(osp.abspath(path))
    return res


def relative_symlink(src, dst, follow_symlink=False, force=False):
    """Create a symbolic link pointing to src named dst.
    Remove the commun part between dirnames to make the symlink as
    relative as possible.
    """
    src = get_absolute_path(src, follow_symlink=follow_symlink)
    dst = get_absolute_path(dst, follow_symlink=follow_symlink)
    lsrc = src.split(os.sep)
    ldst = dst.split(os.sep)
    common = []
    while len(lsrc) > 0 and len(ldst) > 0:
        psrc = lsrc.pop(0)
        pdst = ldst.pop(0)
        if psrc != pdst:
            lsrc = [os.pardir,] * len(ldst) + [psrc,] + lsrc
            src = os.sep.join(lsrc)
            break
        common.append(psrc)
    #print ">>>", src, dst, os.sep.join(common)
    if force and osp.exists(dst):
        os.remove(dst)
    os.symlink(src, dst)


def unexpandvars_string(text, vars=None):
    """Reverse of os.path.expandvars."""
    if vars is None:
        vars = ('ASTER_VERSION_DIR', 'ASTER_ETC', 'ASTER_ROOT', 'HOME')
    if type(text) not in (str, unicode):
        return text
    for var in vars:
        if not os.environ.get(var):
            continue
        text = re.sub('%s( |\/|$)' % re.escape(os.environ[var]),
                      '$%s\\1' % var, text)
    return text

def unexpandvars_list(enum, vars=None):
    """Unexpand all values of ``enum``."""
    new = []
    for val in enum:
        new.append(unexpandvars(val, vars))
    return new

def unexpandvars_tuple(enum, vars=None):
    """Unexpand all values of ``enum``."""
    return tuple(unexpandvars_list(enum, vars))

def unexpandvars_dict(dico, vars=None):
    """Unexpand all values of ``dico``."""
    new = {}
    for key, val in dico.items():
        new[key] = unexpandvars(val, vars)
    return new

def unexpandvars(obj, vars=None):
    """Unexpand the value of ``obj`` according to its type."""
    dfunc = {
        list : unexpandvars_list,
        tuple : unexpandvars_tuple,
        dict : unexpandvars_dict,
    }
    return dfunc.get(type(obj), unexpandvars_string)(obj, vars)
