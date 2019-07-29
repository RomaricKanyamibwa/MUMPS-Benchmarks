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


usage="usage: python %prog [options] [clean]\n" + \
   _("""

   Packaging script for MUMPS Benchmark distribution.

   NOTE : MUMPS Benchmarks packaging script
          the Python you use to run this setup :
            interpreter    : %(interp)s (version %(vers)s)
            prefix         : %(prefix)s

   arguments :
     action : only 'clean'.
     """) % {
      'vers' : python_version,
      'prefix' : os.path.abspath(sys.prefix),
      'interp' : sys.executable,
   }


parser = OptionParser(
         usage=usage,
         version='Packaging tool v1 ')


def command_func(command):
	print("command:",command)
	os.system(command)
	# print("===========================================================================")

def exec_commands(commands,name):
	print("\n>>>>>>>>>>>>> Updating "+name+".... <<<<<<<<<<<<<")
	print("===============================================================================================")

	for c in commands:
		command_func(c)

	print("===============================================================================================")
	
	print(">>>>>>>>>>>>> End of Update..... <<<<<<<<<<<<<")

def extract(path,file):
	return "tar -C "+path+" -xf "+os.path.join(path,file)

def compress(path,folder):

	return "cd "+path+"/;tar cfJ "+folder \
		+".tar.xz "+folder+";rm -r "+folder+"/"

def update_mumps(file,path):
	commands=[]

	commands.append(extract(path,file))
	name_folder=file.split(".tar")
	uncompressed=path+"/"+name_folder[0]+"/"
	commands.append("cp -r Make "+uncompressed)
	commands.append(compress(path,name_folder[0]))
	exec_commands(commands,"MUMPS")


def update_benchfiles(file,path):
	commands=[]
	commands.append(extract(path,file))
	name_folder=file.split(".tar")
	uncompressed=path+"/"+name_folder[0]+"/"
	commands.append("cp -r Make/ "+uncompressed)
	mat_folder=" Matrices/"
	# matrices=["","aster_matrix_input","*.mtx"]
	matrices=["","aster_matrix_input","fidap011*","e40r5000*","e40r0000*"]
	command_matrix="cp -r "+mat_folder#+mat_folder.join( matrices)
	command_matrix+=" "+uncompressed

	# print(command_matrix)  

	source_files=["save_sparse.py","dsimpletest.F","mmio.f"]
	command_src ="cp "+" ".join(source_files)
	command_src+=" "+uncompressed

	# print(command_src)

	commands.append(command_matrix)
	commands.append(command_src)

	commands.append(compress(path,name_folder[0]))

	exec_commands(commands,"Benchmark MUMPS")


parser.add_option("--MUMPS", dest="mumps",action="store_true",default=False,
    help="Update MUMPS Make directory  		[default value False]")

parser.add_option("--BenchFiles", dest="BenchFiles",action="store_true",default=False,
    help="Update MUMPS Benchmarks FILE 		[default value False]")

parser.add_option("--CPY", dest="cpy",action="store_true",default=False,
    help="copy package to DEST directory		[default value False]")

parser.add_option("--dest", dest="dest",action="store",
	default="/mnt/.tgvdv2/projets/projets.002/ccnhpc.066/Benchmarks",
    help="copy destination for package		[default value '/mnt/.tgvdv2/projets/projets.002/ccnhpc.066/Benchmarks']")




version = {
 'mumps': '5.1.2',
 'mumps_benchmark': '0.0.1'}

#-------------------------------------------------------------------------------
if __name__ == '__main__':
	main_folder="mumps-benchmark-full-src-0.0.1/"
	opts, args = parser.parse_args()
	print("Starting Packaging....")
	tar_ext=".tar.xz"

	if len(args) > 0:
		if args[0] == 'clean':
			# for fname in [log_file.split(".")[0]+"*"]:
			print("removing...")

			print("===============================================================================================")
			

			command_func("cd "+main_folder+";"+"python setup.py clean")
			command_func("rm -r "+main_folder+"public "+main_folder+"bin/")

			print("===============================================================================================")
			

				# os.remove(fname)
         	# print("temporary files deleted!")

	if opts.mumps:
		file_mumps="mumps-"+version["mumps"]
		update_mumps(file_mumps+tar_ext,main_folder+"SRC")

	if opts.BenchFiles:
		file_bench="mumps_benchmark-"+version['mumps_benchmark']
		update_benchfiles(file_bench+tar_ext,main_folder+"SRC")

	create_package="tar cfJ "+main_folder.replace("/","") \
	+tar_ext+" "+main_folder
	exec_commands([create_package],"Package")

	if opts.cpy:
		dest=opts.dest
		print("------------------------------------------------------------")
		command_func("mv "+main_folder.replace("/","") \
			+tar_ext+" "+dest)
		print("------------------------------------------------------------")

