"""
This module contains source code for testing compilers, libs...

DO NOT FORGET TO DOUBLE '%' because the source code will be expanded using
a dict containing : INTEGER_SIZE (4 or 8).
"""

blas_lapack  = {
   '__integer8__' : False,
   '__error__' : """
-------------------------------------------------------------------------------
WARNING :
   The C/fortran test program calling blas and lapack subroutines failed.

Reasons :
   - unable to find suitable C/fortran compilers
   - blas/lapack libraries (or required by them) missing
   - incorrect compilation options

Nevertheless the compilation of Code_Aster may work !
If it failed, you must help the setup by setting CC, CFLAGS, MATHLIB...
-------------------------------------------------------------------------------

""",
   'main.c' : r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Test unitaire :
   - passage d'argument C/Fortran : entier, chaine, logique, reel
   - appel blas et lapack dans le fortran
*/

#define INTEGER int
#define STRING_SIZE unsigned int

#if defined HPUX
void test(INTEGER *, char *, INTEGER *, double *, double *, STRING_SIZE);
#define CALL_TEST(a,b,c,d,e) test(a,b,c,d,e,strlen(b))

#elif defined _WIN32 || WIN32
void TEST(INTEGER *, char *, STRING_SIZE, INTEGER *, double *, double *);
#define CALL_TEST(a,b,c,d,e) __stdcall TEST(a,b,strlen(b),c,d,e)

#else
void test_(INTEGER *, char *, INTEGER *, double *, double *, STRING_SIZE);
#define CALL_TEST(a,b,c,d,e) test_(a,b,c,d,e,strlen(b))

#endif


int main(int argc, char **argv)
{
   INTEGER ivers, ilog;
   char vdate[11] = "           ";
   int iret=4;
   double res, res2;
   vdate[10] = '\0';

   CALL_TEST(&ivers, &vdate[0], &ilog,&res, &res2);
   printf("RESULTS : %%d / '%%s' / %%d / %%f / %%f\n", ivers, vdate, ilog, res, res2);
   if (ivers == 10 && res == 10. && res2 == 5. && strncmp(vdate, "01/01/2010", 10) == 0) {
      iret = 0;
   }
   printf("EXIT_CODE=%%d\n", iret);
   exit(iret);
}
""",

   'test.F90' : r"""
subroutine test(vers,date,exploi, res, res2)

    implicit none
    integer vers
    character*10 :: date
    logical :: exploi
!
    real(kind=8) :: ddot, dlapy2
    real(kind=8) :: a1(2), a2(2), res, res2
    integer :: i
!
    vers = 10
    date = '01/01/2010'
    exploi = .true.
!
    do i = 1, 2
        a1(i) = 1.d0 * i
        a2(i) = 2.d0 * i
    end do
    res = ddot(2,a1,1,a2,1)
    res2 = dlapy2(3.d0, 4.d0)
end subroutine test
""",
}


gcc51267  = {
   '__error__' : """
-------------------------------------------------------------------------------
WARNING :
   The fortran test program checking the LOC function with a loop failed.

Reasons :
   - it is known to fail using GNU Fortran 4.6.1 (and may be other releases)
     but it should be fixed using '-fno-tree-dse option'.

Code_Aster will be compiled without error but will be unusable!
You must choose another compiler or change the optimization level.
You can cancel now or make the changes later in the config.txt file of
Code_Aster and rebuild it.
-------------------------------------------------------------------------------

""",
   'main.F90' : r"""
program testloc
    volatile ius
    integer(kind=8) :: ius(1)
    integer(kind=8) :: i,iad,n,loc
    common /jvcomm/ ius
    logical :: ok
    integer(kind=8) :: tab(6)
!
    n = 2
    iad = ( loc(tab) - loc(ius) ) / 8
    do i=1,n
        ius(iad+(i*3-2) ) = -1
        ius(iad+(i*3-1) ) = -1
        ius(iad+(i*3  ) ) = -1
    end do
    ok = .true.
    do i=1,3*n
        print *,'tab(',i,')=',tab(i), (tab(i).eq.-1)
        if (tab(i) .ne. -1) ok = .false.
    end do
    if (ok) then
        print *,'EXIT_CODE=0'
    else
        print *,'EXIT_CODE=1'
    endif
end program
""",
}
