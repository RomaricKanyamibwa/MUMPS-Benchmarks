      module iso_fortran_env

C         Nonintrinsic version for Lahey/Fujitsu Fortran for Linux. 
C         See Subclause 13.8.2 of the Fortran 2003 standard. 

        implicit NONE 
        public 

        integer, parameter :: Character_Storage_Size = 8 
        integer, parameter :: Error_Unit = 0 
        integer, parameter :: File_Storage_Size = 8 
        integer, parameter :: Input_Unit = 5 
        integer, parameter :: IOSTAT_END = -1 
        integer, parameter :: IOSTAT_EOR = -2 
        integer, parameter :: Numeric_Storage_Size = 32 
        integer, parameter :: Output_Unit = 6 

      end module iso_fortran_env

      program main

        IMPLICIT NONE
        INCLUDE 'mpif.h'

        INTERFACE 
          SUBROUTINE readargs(typefile,filename,RHS)

            CHARACTER(len=120),INTENT(INOUT)  :: filename,RHS
            INTEGER,INTENT(OUT)  :: typefile
            CHARACTER(len=120) :: arg
            INTEGER :: cpt,nb_arg

          END SUBROUTINE readargs

          SUBROUTINE MPI_ERROR_HANDLING(error)
            INCLUDE 'mpif.h'

            INTEGER,INTENT(IN)::error
            INTEGER :: length , temp
            CHARACTER(LEN=MPI_MAX_ERROR_STRING) :: message

          END SUBROUTINE MPI_ERROR_HANDLING
        END INTERFACE

        INTEGER    status(MPI_STATUS_SIZE),I    
        INTEGER*8  offset    !    Note,    might 
        INTEGER nints, fh, ierr, count,FILESIZE,INTSIZE,nprocs,rank
        DOUBLE PRECISION,ALLOCATABLE::buf(:)
        DOUBLE PRECISION yty
        CHARACTER(len=120) filename,RHS

        INTEGER t1, t2, clock_rate, clock_max,typefile
        REAL*8 elapsed_time

        INTEGER :: error , junk
        INTEGER :: NNZ,N

        junk=MPI_COMM_WORLD

        yty=0.0
        typefile=1
        filename="Matrices/aster_matrix_input"
        RHS=""
        call readargs(typefile,filename,RHS)
        INQUIRE(FILE=filename, SIZE=FILESIZE)

C       Get the size of doubles
        INTSIZE=sizeof(yty)

C       starts MPI
        CALL MPI_INIT(ierr)
C       get number of processes
        CALL MPI_COMM_SIZE(MPI_COMM_WORLD, nprocs, ierr)
C       get current process id
        CALL MPI_COMM_RANK(MPI_COMM_WORLD, rank, ierr)

C       Install a new error handler
        CALL MPI_Comm_set_errhandler(junk,MPI_ERRORS_RETURN,error )


        IF (rank .eq. 0) THEN
          print*,"FILESIZE:",FILESIZE
        END IF

C       Open FILE with MPI
        CALL MPI_FILE_OPEN(MPI_COMM_WORLD,filename,
     &  MPI_MODE_RDONLY,MPI_INFO_NULL,fh,ierr)
        CALL MPI_ERROR_HANDLING(ierr)

        CALL MPI_FILE_READ(fh,N,1,MPI_INTEGER,status,ierr)
        CALL MPI_FILE_READ(fh,NNZ,1,MPI_INTEGER,status,ierr)
        CALL MPI_ERROR_HANDLING(ierr)

        print*,'N=',N
        print*,'NNZ=',NNZ

        nints  = FILESIZE/(nprocs*INTSIZE) 

        ALLOCATE(buf(nints))

        print*,"PostAllocate:3 first read values",(buf(I),I=1,3)


        offset = rank*nints*INTSIZE+2*INTSIZE 
        CALL system_clock ( t1, clock_rate, clock_max )
        CALL MPI_FILE_READ_AT_ALL(fh,offset,buf,nints,MPI_DOUBLE
     &  ,status,ierr)
        CALL system_clock ( t2, clock_rate, clock_max )
        CALL MPI_ERROR_HANDLING(ierr)

        elapsed_time=real (t2-t1)
     &   /real(clock_rate)

        CALL MPI_GET_COUNT(status,MPI_DOUBLE,count,ierr)  
        CALL MPI_ERROR_HANDLING(ierr)

        print*,"process",rank,"Read time:",elapsed_time,"sec" 
        print*,"process",rank,"read",count,"integers"    

C         print*,"***process",rank,":3 first read values",buf
        CALL MPI_FILE_CLOSE(fh,ierr)  
        CALL MPI_ERROR_HANDLING(ierr)


        CALL MPI_FINALIZE(ierr)
        DEALLOCATE(buf)

      
      end 

      SUBROUTINE MPI_ERROR_HANDLING(error)
        USE iso_fortran_env
        IMPLICIT NONE
        INCLUDE 'mpif.h'

        INTEGER,INTENT(IN)::error
        INTEGER :: length , temp
C         INTEGER :: errclass
        CHARACTER(LEN=MPI_MAX_ERROR_STRING) :: message

        IF ( error .NE. MPI_SUCCESS ) THEN

C           MPI_ERROR_CLASS(error,errclass,temp)
C           IF (errclass .EQ. MPI_ERR_RANK ) THEN
C             print*,"ERROR:Invalid rank used in MPI call"
C           END IF

          CALL MPI_ERROR_STRING ( error ,message , length , temp )
          write(Error_Unit,*)message(1:length)
          CALL MPI_Abort( MPI_COMM_WORLD,1 ,temp )
        END IF


      END SUBROUTINE


      SUBROUTINE readargs(typefile,filename,RHS)

        IMPLICIT NONE
        CHARACTER(len=120),INTENT(INOUT)  :: filename,RHS
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
                  print*,'ERROR:File does not exist: ',RHS
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

