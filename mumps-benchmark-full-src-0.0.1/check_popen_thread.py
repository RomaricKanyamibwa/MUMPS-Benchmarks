"""
Provoke the Popen bug.
(there is a similar bug in subprocess module)
"""

import popen2 
import threading

numthreads = 20
nb = 5
count = 0
count_lock = threading.Lock()

class test_popen2(threading.Thread):
   def __init__(self):
      threading.Thread.__init__(self)

   def run (self):
      global count, count_lock
      for i in range(nb):
         pipe = popen2.Popen4("ls > /dev/null")
         try:
            pipe.wait()
            count_lock.acquire()
            count += 1
            count_lock.release()
         except OSError:
            pass


def main():
   """
   Provoke the Popen bug.
   """
   global count
   lt = []
   for i in range(numthreads):
      t = test_popen2()
      lt.append(t)
      t.start ()
   for t in lt:
      t.join()
   ok = count == numthreads * nb
   return ok


if __name__ == '__main__':
   iret = main()
   print iret

