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
        SUBROUTINE readargs(typefile,filename,RHS)

          CHARACTER(len=120),INTENT(OUT)  :: filename,RHS
          INTEGER,INTENT(OUT)  :: typefile
          CHARACTER(len=120) :: arg
          INTEGER :: cpt,nb_arg

        END SUBROUTINE readargs

        SUBROUTINE mmread(iunit,rep,field,symm,rows,cols,nnz,
     *                 indx,jndx,ival,rval,cval)

          integer,DIMENSION(:),INTENT(INOUT)::ival
          double precision,DIMENSION(:),INTENT(INOUT)::rval
          complex,DIMENSION(:),INTENT(INOUT)::cval
          double precision rpart,ipart
          integer,DIMENSION(:),INTENT(INOUT)::indx
          integer,DIMENSION(:),INTENT(INOUT)::jndx
          integer,INTENT(IN):: iunit
          integer ,INTENT(OUT)::rows, cols, nnz
          integer count,i,nnzreq
          character mmhead*15
          character mmtype*6
          character,INTENT(OUT)::rep*10
          character,INTENT(OUT)::field*7
          character,INTENT(OUT)::symm*19
          character tmp1*1024
          character tmp2*2
        END SUBROUTINE

        SUBROUTINE mminfo(iunit,rep,field,symm,rows,cols,nnz)
          integer,INTENT(IN):: iunit
          integer ,INTENT(OUT)::rows, cols, nnz
          integer count,i
          character mmhead*15
          character mmtype*6
          character,INTENT(OUT)::rep*10
          character,INTENT(OUT)::field*7
          character,INTENT(OUT)::symm*19
          character tmp1*1024
          character tmp2*2
        END SUBROUTINE

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
      CHARACTER(len=120) filename,RHS

C       mmio variables
C       INTEGER nnzmax
      INTEGER iunit
      CHARACTER rep*10
      CHARACTER field*7
      CHARACTER symm*19
      CHARACTER ifile*32,ofile*32
C       PARAMETER (nnzmax=5000000)
      INTEGER,ALLOCATABLE :: ival(:)
      DOUBLE PRECISION,ALLOCATABLE :: rval(:)
      COMPLEX,ALLOCATABLE :: cval(:)
      INTEGER,ALLOCATABLE :: indx(:)
      INTEGER,ALLOCATABLE :: jndx(:)
      INTEGER :: ncols,nnz,nrows
c

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
        RHS=""
        call readargs(typefile,filename,RHS)

        iunit = 8
        OPEN(unit=iunit,FILE=filename)
C       Reading Matrix Market Exchange Formats
        IF ( typefile .eq. 3) THEN
          print *,'Reading header and data...'
          call mminfo(iunit,rep,field,symm,nrows,ncols,nnz)
          if( rep .ne. 'array' ) then
            ALLOCATE(indx(nnz))
            ALLOCATE(jndx(nnz))
          endif

          if ( field .eq. 'integer' ) then
            ALLOCATE(ival(nnz))
          elseif ( field .eq. 'real') then
            ALLOCATE(rval(nnz))
          elseif ( field .eq. 'complex' ) then
            ALLOCATE(cval(nnz))
          endif

C           print*,"END Allocation"
          call mmread(iunit,rep,field,symm,nrows,ncols,nnz,
     *           indx,jndx,ival,rval,cval)
          print *,'  Matrix is type: ',rep,' ',field,' ',symm
          print *,'  Matrix size: ',nrows,' by ',ncols,' with ',
     *                          nnz,' nonzeros.'

          mumps_par%N=nrows
          mumps_par%NNZ=nnz

          ALLOCATE( mumps_par%IRN ( mumps_par%NNZ ) )
          ALLOCATE( mumps_par%JCN ( mumps_par%NNZ ) )
          ALLOCATE( mumps_par%A( mumps_par%NNZ ) )
          ALLOCATE( mumps_par%RHS ( mumps_par%N  ) )

          mumps_par%IRN(:)=indx(:)
          mumps_par%JCN(:)=jndx(:)
          mumps_par%A=rval

          IF ((RHS .EQ. "") .OR. (len(RHS) .LE. 0)) THEN
            print*,"ERROR:Expected option --RHS"
            GOTO 500
          END IF 

          CLOSE(iunit)
          OPEN(unit=9,FILE=RHS)
          print *,'Reading RHS header and data...'
          call mmread(9,rep,field,symm,nrows,ncols,nnz,
     *           indx,jndx,ival,rval,cval)
          print *,'  Matrix is type: ',rep,' ',field,' ',symm
          print *,'  RHS size: ',nrows,' by ',ncols

          if( rep .ne. 'array' ) then
            print*,"ERROR:Expected array type matrix"
            GOTO 500
          endif

          mumps_par%RHS=rval(1:nrows)
          CLOSE(9)

C       Reading Harwell-Boeing Exchange Format
        ELSE IF ( typefile .eq. 4) THEN
          print*,"ERROR:Unimplemented Harwell-Boeing Exchange Format"
          print*,"Exiting...."
          CLOSE(8)
          GOTO 500
        ELSE

          READ(8,*) mumps_par%N
          READ(8,*) mumps_par%NNZ
          print*,"N=",mumps_par%N," NNZ=",mumps_par%NNZ
          ALLOCATE( mumps_par%IRN ( mumps_par%NNZ ) )
          ALLOCATE( mumps_par%JCN ( mumps_par%NNZ ) )
          ALLOCATE( mumps_par%A( mumps_par%NNZ ) )
          ALLOCATE( mumps_par%RHS ( mumps_par%N  ) )

          DO I8 = 1, mumps_par%NNZ
            READ(8,*) mumps_par%IRN(I8),mumps_par%JCN(I8),
     &      mumps_par%A(I8)

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
        print*,'------------------------------------------------------'
        WRITE( 6, * )'Solution is ',(mumps_par%RHS(I),I=1,5),'....'
        print*,'------------------------------------------------------'
      END IF


C  Deallocate user data and calculate overall performance
      IF ( mumps_par%MYID .eq. 0 )THEN
        gflops_step(1)=mumps_par%RINFOG(1)
        gflops_step(2)=mumps_par%RINFOG(2)
        gflops_step(3)=mumps_par%RINFOG(3)

        elapsed_time=real (t2-t1)
     &   /real(clock_rate)
        WRITE(6,'(A,F8.3,A)')" Resolution time:",elapsed_time,"sec"

        print*,"Analysis:",gflops_step(1)/Giga,"Gflops"
        print*,"Factorization:",gflops_step(2)/Giga,"Gflops"
        print*,"Resolution:",gflops_step(3)/Giga,"Gflops"
        determ=(mumps_par%RINFOG(12))*2.0**mumps_par%INFOG(34)
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

        IF ( typefile .eq. 3) THEN
          IF( rep .ne. 'array' ) THEN
              DEALLOCATE(indx)
              DEALLOCATE(jndx)
          ENDIF

          if ( field .eq. 'integer' ) then
            DEALLOCATE(ival)
          elseif ( field .eq. 'real') then
            DEALLOCATE(rval)
          elseif ( field .eq. 'complex' ) then
            DEALLOCATE(cval)
          endif
        ENDIF

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


      SUBROUTINE readargs(typefile,filename,RHS)

        IMPLICIT NONE
        CHARACTER(len=120),INTENT(OUT)  :: filename,RHS
        INTEGER,INTENT(OUT)  :: typefile
        CHARACTER(len=120) :: arg
        INTEGER :: cpt,nb_arg
        LOGICAL :: file_exists

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

                INQUIRE(FILE=filename, EXIST=file_exists)
                IF (file_exists .EQV. .FALSE.) THEN
                  print*,'ERROR:Problem with File => ',filename
                  STOP
                END IF 

                print*,'Filename=',filename
            case ('-t','--type')
                cpt=cpt+1
                call getarg(cpt,arg)
                read(arg,*)typefile
                print*,'FileType=',typefile

            case ('--RHS')
                cpt=cpt+1
                call getarg(cpt,arg)
                read(arg,*)RHS

                INQUIRE(FILE=RHS, EXIST=file_exists)
                IF (file_exists .EQV. .FALSE.) THEN
                  print*,'ERROR:Problem with File => ',RHS
                  STOP
                END IF

                print*,'RHS=',RHS
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
          print  '(a)','  --RHS       RHS Filename (needed for type 3)'
          print  '(a)','  -t          Typefile [|1,4|]'
          print  '(a)','  -h, --help  print usage information and exit'
        end subroutine print_help

      END SUBROUTINE readargs
