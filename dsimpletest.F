C
C  This file is part of MUMPS 5.1.2, released
C  on Mon Oct  2 07:37:01 UTC 2017
C
      PROGRAM MUMPS_TEST
      IMPLICIT NONE
      INCLUDE 'mpif.h'
      INCLUDE 'dmumps_struc.h'
      TYPE (DMUMPS_STRUC) mumps_par

      INTERFACE 
        SUBROUTINE readargs(typefile,filename)

          CHARACTER(len=60),INTENT(OUT)  :: filename
          INTEGER,INTENT(OUT)  :: typefile
          CHARACTER(len=60)  :: arg
          INTEGER :: cpt,nb_arg


        END SUBROUTINE readargs
      END INTERFACE

      INTEGER IERR, I,index
      INTEGER(8) I8
C       Variables for Flops per step  
      DOUBLE PRECISION gflops_step(3),Giga,determ 
C     Reduce variables  
      CHARACTER(len=20) str_fin

      REAL start_time, stop_time, elapsed_time
      INTEGER t1, t2, clock_rate, clock_max 

C       input arguments
      INTEGER typefile
      CHARACTER(len=60) filename

      CALL MPI_INIT(IERR)
C Define a communicator for the package.
      mumps_par%COMM = MPI_COMM_WORLD

C  Initialize an instance of the package
C  for L U factorization (sym = 0, with working host)
      mumps_par%JOB = -1
      mumps_par%SYM = 0
      mumps_par%PAR = 1
      CALL DMUMPS(mumps_par)

      
      gflops_step(:)=0
      Giga=1024.0*1024.0*1024.0

      IF (mumps_par%INFOG(1).LT.0) THEN
       WRITE(6,'(A,A,I6,A,I9)') " ERROR RETURN: ",
     &            "  mumps_par%INFOG(1)= ", mumps_par%INFOG(1), 
     &            "  mumps_par%INFOG(2)= ", mumps_par%INFOG(2) 
       GOTO 500
      END IF

C       call cpu_time(start_time)
C       print*,"-----      Define problem on the host      -----"
C  Define problem on the host (processor 0)
      IF ( mumps_par%MYID .eq. 0 ) THEN

        typefile=1
        filename="aster_matrix_input"
        call readargs(typefile,filename)

C         OPEN(unit=8,FILE="aster_matrix_input")
        OPEN(unit=8,FILE=filename)

        READ(8,*) mumps_par%N
        READ(8,*) mumps_par%NNZ
        print*,"N=",mumps_par%N," NNZ=",mumps_par%NNZ
        ALLOCATE( mumps_par%IRN ( mumps_par%NNZ ) )
        ALLOCATE( mumps_par%JCN ( mumps_par%NNZ ) )
        ALLOCATE( mumps_par%A( mumps_par%NNZ ) )
        ALLOCATE( mumps_par%RHS ( mumps_par%N  ) )

        DO I8 = 1, mumps_par%NNZ
          READ(8,*) mumps_par%IRN(I8),mumps_par%JCN(I8),mumps_par%A(I8)

        END DO
        DO I = 1, mumps_par%N
          IF (typefile .eq. 1) THEN
            READ(8,*)index,mumps_par%RHS(I)
          ELSE
              READ(8,*)mumps_par%RHS(I)!for test input matrix
          END IF
          
        END DO
        CLOSE(8)

      END IF

C       print*,"-----     End  of problem definition      -----"
C  Call package for solution
      mumps_par%ICNTL(33)=1
      mumps_par%JOB = 6
      CALL system_clock ( t1, clock_rate, clock_max )
      CALL DMUMPS(mumps_par)
      CALL system_clock ( t2, clock_rate, clock_max )

      IF (mumps_par%INFOG(1).LT.0) THEN
       WRITE(6,'(A,A,I6,A,I9)') " ERROR RETURN: ",
     &            "  mumps_par%INFOG(1)= ", mumps_par%INFOG(1), 
     &            "  mumps_par%INFOG(2)= ", mumps_par%INFOG(2) 
       GOTO 500
      END IF
C  Solution has been assembled on the host
      IF ( mumps_par%MYID .eq. 0 ) THEN
C         WRITE( 6, * ) ' Solution is ',(mumps_par%RHS(I),I=1,mumps_par%N)

        print*,""
        print*,"------------------------------------------------------"
        print*,"RINFO(1):",mumps_par%RINFO(1)
        print*,"RINFO(2):",mumps_par%RINFO(2)
        print*,"RINFO(3):",mumps_par%RINFO(3)
        print*,"------------------------------------------------------"
        print*,""
        

      END IF

      CALL MPI_REDUCE(mumps_par%RINFO,gflops_step, 3, MPI_DOUBLE,
     &      MPI_SUM, 0, mumps_par%COMM, ierr) 


C  Deallocate user data
      IF ( mumps_par%MYID .eq. 0 )THEN

        elapsed_time=real (t2-t1)
     &   /real(clock_rate)
C         elapsed_time=stop_time-start_time
        WRITE(6,'(A,F8.3,A)')" Resolution time:",elapsed_time,"sec"

        print*,"Analysis:",gflops_step(1)/Giga,"Gflops"
        print*,"Factorization:",gflops_step(2)/Giga,"Gflops"
        print*,"Resolution:",gflops_step(3)/Giga,"Gflops"
        determ=(mumps_par%RINFOG(12))*2.0**mumps_par%INFOG(34)
C         print*,"mumps_par%RINFOG(12):",mumps_par%RINFOG(12)
C         print*,"mumps_par%INFOG(34):",mumps_par%INFOG(34)
        print*,"Determinant:",determ
        str_fin="               #"

        print*,"#######################################################"
        print*,"#                                                     #"
        print*,"#                                                     #"
        print*,"#  Gflops/s:",sum(gflops_step)/Giga/elapsed_time,str_fin
        print*,"#  Resolution time:",elapsed_time,"s ",str_fin
        print*,"#                                                     #"
        print*,"#                                                     #"
        print*,"#######################################################"

        DEALLOCATE( mumps_par%IRN )
        DEALLOCATE( mumps_par%JCN )
        DEALLOCATE( mumps_par%A   )
        DEALLOCATE( mumps_par%RHS )
      END IF
C  Destroy the instance (deallocate internal data structures)
      mumps_par%JOB = -2
      CALL DMUMPS(mumps_par)
      IF (mumps_par%INFOG(1).LT.0) THEN
       WRITE(6,'(A,A,I6,A,I9)') " ERROR RETURN: ",
     &            "  mumps_par%INFOG(1)= ", mumps_par%INFOG(1), 
     &            "  mumps_par%INFOG(2)= ", mumps_par%INFOG(2) 
       GOTO 500
      END IF
 500  CALL MPI_FINALIZE(IERR)
      STOP
      END


      SUBROUTINE readargs(typefile,filename)

        CHARACTER(len=60),INTENT(OUT)  :: filename
        INTEGER,INTENT(OUT)  :: typefile
        CHARACTER(len=60) :: arg
        INTEGER :: cpt,nb_arg

        nb_arg=iargc()
        cpt=1
      do  while (cpt<= nb_arg)
        call getarg(cpt, arg)

        select case (arg)

            case ('-h','--help')
                call print_help()
C                 print*,"HELP"
                stop
            case ('-f','--file')
                cpt=cpt+1
                call getarg(cpt,arg)
                read(arg,*)filename
                print*,"Filename=",filename
            case ('-t','--type')
                cpt=cpt+1
                call getarg(cpt,arg)
                read(arg,*)typefile
                print*,'FileType=',typefile
            case default
                print '(a,a,/)','Unrecognized command-line option:'
                call print_help()
                stop
        end select
        cpt=cpt+1
      end do

      contains
        subroutine print_help()
          print  '(a)','usage: dsimpletest [OPTIONS]'
          print  '(a)',''
          print  '(a)','Without options, typefile=1,filename='//
     &    'aster_matrix_input'
          print  '(a)',''
          print  '(a)','cmdline options:'
          print  '(a)',''
          print  '(a)','  -f          Filename'
          print  '(a)','  -t          Typefile [1,2]'
          print  '(a)','  -h, --help  print usage information and exit'
        end subroutine print_help

      END SUBROUTINE readargs
