
# -*- coding: utf-8 -*-
# COPYRIGHT (C) 1991 - 2018  EDF R&D                  WWW.CODE-ASTER.ORG
"Package info"

modname      = 'codeaster-setup'
version      = '13.6.0'
numversion   = (13, 6, 0)
release      = '1'

license      = 'GPL, LGPL, non-free'
copyright    = 'Copyright (c) 2001-2018 EDF R&D - http://www.code-aster.org'

short_desc   = "Setup script for Code_Aster and some prerequisites"
long_desc    = short_desc

author       = "EDF R&D"
author_email = "code-aster@edf.fr"

dict_prod = {'aster': '13.6.0',
 'astk': '2018.0',
 'gmsh': '3.0.6',
 'grace': '5.1.23',
 'hdf5': '1.8.14',
 'homard': '11.10',
 'med': '3.3.1',
 'metis': '5.1.0',
 'mumps': '5.1.1',
 'scotch': '6.0.4',
 'tfel': '3.0.0'}

dict_prod_param = {'__to_install__': ['med',
                    'astk',
                    'hdf5',
                    'tfel',
                    'metis',
                    'aster',
                    'grace',
                    'mumps',
                    'homard',
                    'scotch',
                    'gmsh'],
 'aster-verslabel': 'stable'}

