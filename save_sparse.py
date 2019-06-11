# -*- coding: utf-8 -*-
from __future__ import print_function
"""
Created on Tue Apr 18 13:28:25 2019
@author: KANYAMIBWA Romaric
SparseGeneator
================
Generation/Save and load of a random sparse matrix A and a vector b from the
Ax=b linear system
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

"""http://stackoverflow.com/questions/6282432/load-sparse-array-from-npy-file
"""

import random
import scipy.sparse as sparse
import scipy.io
import multiprocessing
import numpy as np
from argparse import ArgumentParser
import time

def save_sparse_matrix(filename,n,density, rhs=False):
    start_time = time.time()
    print("Generating Sparse matrix......")
    x=sparse.rand(n,n,density=density)
    x_coo = x.tocoo()
    NNZ = x.nnz#int(n*n*density)
    LB=-100
    UB=101
    row = x.row#np.random.randint(0,n,NNZ)
    col = x.col#np.random.randint(0,n,NNZ)
    data = np.random.uniform(LB,UB,NNZ)


    with open(filename,"w") as file:

        file.write(str(n)+"\n")
        file.write(str(NNZ))
        print('Saving Generated Sparse matrix...')

        for i in range(NNZ):#we add 1 so we can be comptatible with MUMPS/Fortran indexing that starts at 1
            tmp="\n"+str(row[i]+1)+"\t"+str(col[i]+1)+"\t"+str(data[i])
            file.write(tmp)     

        if rhs : 
            print("Generating RHS......")
            y=np.random.uniform(LB,UB,n)
            for j in range(n):
                tmp="\n"+str(y[j])
                file.write(tmp)

        file.write("\n")
        elapsed_time = time.time() - start_time
        str_time="# Sparse File Generation time:"+str(elapsed_time)+"s #"
        seperators="#"
        empty_sep ="#"
        for k in range(len(str_time)-2):
            seperators+="#"
            empty_sep +=" "
        seperators+="#"
        empty_sep +="#"

        print(seperators)
        print(empty_sep)
        print(str_time)
        print(empty_sep)
        print(seperators)



def load_sparse_matrix(filename, rhs=False):

    data = []
    row = []
    col = []

    with open(filename, "r") as file:
        N=int(file.readline())
        NNZ=int(file.readline())
        print ("N=",N," NNZ=",NNZ)
        
        for k in range(NNZ):
            line=file.readline()
            # line_array=line.split()
            # print(line_array)
            res=map(lambda x:(int(x[0])-1,int(x[1])-1,float(x[2])),[line.split()])
            # print(res[0][2])
            row.append(res[0][0]);col.append(res[0][1]);data.append(res[0][2])

            # print(k,"=>",row[k],col[k],data[k])
        if rhs:
            y=[]
            for k in range(N):
                line=file.readline()
                y.append(float(line))

    M=sparse.coo_matrix((data,(row,col)),shape=(N,N))

    
    print("REAL NNZ:",M.nnz)
    print("-----------------------------------------------")
    print(M)
    print("-----------------------------------------------")
    print(M.todense())
    print("-----------------------------------------------")

    print(y)
    return M

parser = ArgumentParser()

file='sparse_input.txt'
parser.add_argument("-f", "--file", dest="filename",help="Name of the generated file [default value "+file+"]"
    ,default=file, metavar="FILE")

parser.add_argument("-N",
    dest="N", default=100,metavar="n",
    help="Sparse matrix size N*N [default value 100]",type=int)

parser.add_argument("-d","--density",
                    dest="density", default=0.05,metavar="r",
                    help="Density of the sparse matrix [default value 5%]",type=float)

parser.add_argument("--load", dest="load",action="store_true",
    help="Load and print dense structure of saved file")

parser.add_argument("--RHS", dest="RHS",action="store_true",default=False,
    help="Generate and save Right Hand Side of Ax=b[default value False]")


#-------------------------------------------------------------------------------
if __name__ == '__main__':
    args = parser.parse_args()

    n=m=args.N
    # matrixA=sparse.rand(n,m,density=args.density)
    # print(matrixA)
    if args.RHS :
        save_sparse_matrix(args.filename,n,args.density,args.RHS)
    else:
        save_sparse_matrix(args.filename,n,args.density)
    loadfile=args.filename #'input_simpletest_real'#"aster_matrix_input"

    if args.load :
        load_sparse_matrix(loadfile,args.RHS)#.tolil()