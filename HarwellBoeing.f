
      PROGRAM main

C     ================================================================
C     ... SAMPLE CODE FOR READING A GENERAL SPARSE MATRIX, POSSIBLY
C         WITH RIGHT-HAND SIDE VECTORS
C     ================================================================
      INTEGER nnzmax

      CHARACTER      TITLE*72 , KEY*8    , MXTYPE*3 , RHSTYP*3,
     1               PTRFMT*16, INDFMT*16, VALFMT*20, RHSFMT*20,
     2               ifile*32

      INTEGER        TOTCRD, PTRCRD, INDCRD, VALCRD, RHSCRD,
     1               NROW  , NCOL  , NNZERO, NELTVL,
     2               NRHS  , NRHSIX, NRHSVL, NGUESS, NEXACT

      parameter (nnzmax=100000)

      INTEGER        POINTR (nnzmax), ROWIND (nnzmax), 
     1               RHSPTR (nnzmax), RHSIND(nnzmax)

      REAL           VALUES (nnzmax) , RHSVAL (nnzmax),
     1               XEXACT (nnzmax), SGUESS (nnzmax)

C     ------------------------
C     ... READ IN HEADER BLOCK
C     ------------------------
      IF (IARGC() .GT. 0) THEN
        CALL GETARG(1,IFILE)
        LUNIT = 8
        OPEN(UNIT=LUNIT,FILE=IFILE)
      ELSE
        LUNIT = 5
      ENDIF

      READ ( LUNIT, 1000 ) TITLE , KEY   ,
     1                     TOTCRD, PTRCRD, INDCRD, VALCRD, RHSCRD,
     2                     MXTYPE, NROW  , NCOL  , NNZERO, NELTVL,
     3                     PTRFMT, INDFMT, VALFMT, RHSFMT

      print*,"Title:",TITLE
      print*,"KEY:",KEY
      print*,"TOTCRD:",TOTCRD
      print*,"PTRCRD:",PTRCRD
      print*,"RHSCRD:",RHSCRD
      print*,"NROW: ",NROW
      print*,"NCOL: ",NCOL
      print*,"NNZERO:",NNZERO


      IF  ( RHSCRD .GT. 0 )
     1    READ ( LUNIT, 1001 ) RHSTYP, NRHS, NRHSIX

 1000 FORMAT ( A72, A8 / 5I14 / A3, 11X, 4I14 / 2A16, 2A20 )
 1001 FORMAT ( A3, 11X, 2I14 )

C     -------------------------
C     ... READ MATRIX STRUCTURE
C     -------------------------

      READ ( LUNIT, PTRFMT ) ( POINTR (I), I = 1, NCOL+1 )

      READ ( LUNIT, INDFMT ) ( ROWIND (I), I = 1, NNZERO )

      IF  ( VALCRD .GT. 0 )  THEN

C         ----------------------
C         ... READ MATRIX VALUES
C         ----------------------

          IF  ( MXTYPE (3:3) .EQ. 'A' )  THEN
              READ ( LUNIT, VALFMT ) ( VALUES (I), I = 1, NNZERO )
          ELSE
              READ ( LUNIT, VALFMT ) ( VALUES (I), I = 1, NELTVL )
          ENDIF

C           print *,VALUES(1:10)
C           print *,ROWIND(2),POINTR(2),VALUES(2)

C         -------------------------
C         ... READ RIGHT-HAND SIDES
C         -------------------------

          IF  ( NRHS .GT. 0 )  THEN

              IF  ( RHSTYP(1:1) .EQ. 'F' ) THEN

C                 -------------------------------
C                 ... READ DENSE RIGHT-HAND SIDES
C                 -------------------------------

                  NRHSVL = NROW * NRHS
                  READ ( LUNIT, RHSFMT ) ( RHSVAL (I), I = 1, NRHSVL )

              ELSE

C                 ---------------------------------------------
C                 ... READ SPARSE OR ELEMENTAL RIGHT-HAND SIDES
C                 ---------------------------------------------


                  IF (MXTYPE(3:3) .EQ. 'A') THEN

C                    ------------------------------------------------
C                    ... SPARSE RIGHT-HAND SIDES - READ POINTER ARRAY
C                    ------------------------------------------------

                     READ (LUNIT, PTRFMT) ( RHSPTR (I), I = 1, NRHS+1 )

C                    ----------------------------------------
C                    ... READ SPARSITY PATTERN FOR RIGHT-HAND
C                        SIDES
C                    ----------------------------------------

                     READ (LUNIT, INDFMT) ( RHSIND (I), I = 1, NRHSIX )

C                    --------------------------------------
C                    ... READ SPARSE RIGHT-HAND SIDE VALUES
C                    --------------------------------------

                     READ (LUNIT, RHSFMT) ( RHSVAL (I), I = 1, NRHSIX )

                  ELSE

C                    -----------------------------------
C                    ... READ ELEMENTAL RIGHT-HAND SIDES
C                    -----------------------------------

                     NRHSVL = NNZERO * NRHS
                     READ (LUNIT, RHSFMT) ( RHSVAL (I), I = 1, NRHSVL )

                  ENDIF

              END IF

              IF  ( RHSTYP(2:2) .EQ. 'G' ) THEN

C                 -------------------------
C                 ... READ STARTING GUESSES
C                 -------------------------

                 NGUESS = NROW * NRHS
                 READ (LUNIT, RHSFMT) ( SGUESS (I), I = 1, NGUESS )

              END IF

              IF  ( RHSTYP(3:3) .EQ. 'X' ) THEN

C                 -------------------------
C                 ... READ SOLUTION VECTORS
C                 -------------------------

                 NEXACT = NROW * NRHS
                 READ (LUNIT, RHSFMT) ( XEXACT (I), I = 1, NEXACT )
              END IF
          END IF
      END IF


      END PROGRAM