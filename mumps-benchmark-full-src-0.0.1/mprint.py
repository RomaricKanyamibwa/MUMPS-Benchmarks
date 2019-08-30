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

# $Id: mprint.py 3728 2008-12-23 16:36:01Z courtois $
# $Name$

import sys
import os
import re

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
class MPRINT:
   """This class encapsulates standard print statement.
   """
#-------------------------------------------------------------------------------
   def __init__(self, filename, mode='a'):
      """filename : name of log file ; mode = 'w'/'a'
      """
      self.mode   = mode
      self.stderr = sys.stderr
      self.logf   = [sys.stdout]
      debug_name = filename.replace('.log', '.dbg')
      filename = [filename, debug_name]
      for filen_i in filename:
         nmax = 100
         for i in range(nmax, -1, -1):
            if i > 0:
               fich = '%s.%d' % (filen_i, i)
            else:
               fich = filen_i
            if os.path.exists(fich):
               if i == nmax:
                  os.remove(fich)
               else:
                  os.rename(fich, '%s.%d' % (filen_i, i+1))
         self.logf.append(open(filen_i, mode))
      sys.stderr  = self.logf[1]
      self.last_char = [os.linesep,] * 3

#-------------------------------------------------------------------------------
   def close(self):
      """Close file properly on deletion.
      """
      sys.stderr = self.stderr
      for f in self.logf[1:]:
         f.close()

#-------------------------------------------------------------------------------
   def _print(self, *args, **kargs):
      """print replacement.
      Optionnal argument :
       term  : line terminator (default to os.linesep).
      """
      term = kargs.get('term', os.linesep)
      for i, f in enumerate(self.logf):
         if kargs.get('DBG') and i != 2:
            continue
         if type(f) is file:
            l_val = []
            for a in args:
               if type(a) in (str, unicode):
                  l_val.append(a)
               else:
                  l_val.append(repr(a))
            txt = ' '.join(l_val)
            txt = txt.replace(os.linesep+' ',os.linesep)
            if kargs.get('DBG'):
               lines = txt.splitlines()
               if self.last_char[i] != os.linesep:
                  lines.insert(0, '')
               else:
                  lines[0] = '<DBG> ' + lines[0]
               txt = (os.linesep + '<DBG> ').join(lines)
            txt = txt + term
            f.write(txt)
            f.flush()
            if len(txt) > 0:
               self.last_char[i] = txt[-1]
         else:
            print 'Unexpected object %s : %s' % (type(f), repr(f))

