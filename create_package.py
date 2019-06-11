# -*- coding: utf-8 -*-
from __future__ import print_function
"""
Created on Tue Jun 7 16:52:25 2019
@author: KANYAMIBWA Romaric
SparseGeneator
================
Packaging of MUMPS Benchmark
"""

#############################################################################
#  Copyright (C) 2019                                                       #
#                                                                           #
#                                                                           #
#  Distributed under the terms of the GNU General Public License (GPL)      #
#  either version 3, or (at your option) any later version                  #
#                                                                           #
#  http://www.gnu.org/licenses/                                             #
#############################################################################

# ----- differ messages translation
def _(mesg): return mesg
import sys
# ----- check for Python version
if sys.hexversion < 0x020600F0:
   print('This script requires Python 2.6 or higher, sorry !')
   sys.exit(4)
import subprocess
# import shutil
# import mprint
from optparse import OptionParser
import os
from glob import glob

log_file = 'create_package.log'
# log = mprint.MPRINT(log_file, 'w')

python_version    = '.'.join([str(n) for n in sys.version_info[:3]])

to_install=['scotch','metis','parmetis','mumps','mumps_benchmark']


usage="usage: python %prog [options] [install|test] [arg]\n" + \
   _("""

   Setup script for MUMPS Benchmarks distribution.

   NOTE : MUMPS Benchmarks packaging script
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


parser = OptionParser(
         usage=usage,
         version='Packaging tool v1 ')


def command_func(command):
	print("command:",command)
	os.system(command)
	# print("===========================================================================")

def exec_commands(commands,name):
	print(">>>>>>>>>>>>> Updating "+name+".... <<<<<<<<<<<<<")
	print("===============================================================================================")

	for c in commands:
		command_func(c)

	print("===============================================================================================")
	
	print(">>>>>>>>>>>>> End of Update..... <<<<<<<<<<<<<")

def extract(path,file):
	return "tar -C "+path+" -xf "+os.path.join(path,file)

def compress(path,folder):

	return "cd "+path+"/;tar cfJ "+folder \
		+"1.tar.xz "+folder+";rm -r "+folder+"/"

def update_mumps(file,path):
	commands=[]

	commands.append(extract(path,file))
	name_folder=file.split(".tar")
	uncompressed=path+"/"+name_folder[0]+"/"
	commands.append("cp -r Make "+uncompressed)
	commands.append(compress(path,name_folder[0]))
	exec_commands(commands,"MUMPS")
	# shutil.unpack_archive(os.path.join(path,file),extract_dir=path)
	# print("\tExtracting MUMPS....")
	# print(os.path.join(path,file))
	# command_func("tar -C "+path+" -xf "+os.path.join(path,file))
	# name_folder=file.split(".tar")
	# uncompressed=path+"/"+name_folder[0]+"/"
	# command_func("cp -r Make "+uncompressed)
	# command_func("cd "+path+"/;tar cfJ "+name_folder[0]
	# 	+"1.tar.xz "+name_folder[0]+";rm -r "+name_folder[0]+"/")


def update_benchfiles(file,path):
	commands=[]
	commands.append(extract(path,file))
	name_folder=file.split(".tar")
	uncompressed=path+"/"+name_folder[0]+"/"
	commands.append("cp -r Make "+uncompressed)
	mat_folder=" Matrices/"
	matrices=["","aster_matrix_input","determinant_test","*.mtx"]
	command_matrix="cp "+mat_folder.join( matrices)
	command_matrix+=" "+uncompressed

	print(command_matrix)  

	source_files=["save_sparse.py","dsimpletest.F","mmio.f"]
	command_src ="cp "+" ".join(source_files)
	command_src+=" "+uncompressed

	print(command_src)

	commands.append(command_matrix)
	commands.append(command_src)

	commands.append(compress(path,name_folder[0]))

	exec_commands(commands,"Benchmark MUMPS")




	



parser.add_option("--MUMPS", dest="mumps",action="store_true",default=False,
    help="Update MUMPS FILE[default value False]")

parser.add_option("--BenchFiles", dest="BenchFiles",action="store_true",default=False,
    help="Update MUMPS Benchmarks FILE[default value False]")


version = {
 'mumps': '5.1.2',
 'mumps_benchmark': '0.0.1'}

#-------------------------------------------------------------------------------
if __name__ == '__main__':
	main_folder="mumps-benchmark-full-src-0.0.1/"
	opts, args = parser.parse_args()
	print("Starting Packaging....")
	tar_ext="tar.xz"

	if len(args) > 0:
		if args[0] == 'clean':
			# for fname in [log_file.split(".")[0]+"*"]:
			print("removing...")

			print("===============================================================================================")
			

			command_func("cd "+main_folder+";"+"python setup.py clean")
			command_func("rm -r "+main_folder+"public")

			print("===============================================================================================")
			

				# os.remove(fname)
         	# print("temporary files deleted!")

	if opts.mumps:
		file_mumps="mumps-"+version["mumps"]
		update_mumps(file_mumps+"."+tar_ext,main_folder+"SRC")

	if opts.BenchFiles:
		file_bench="mumps_benchmark-"+version['mumps_benchmark']
		update_benchfiles(file_bench+"."+tar_ext,main_folder+"SRC")