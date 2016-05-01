#!/usr/bin/python
import mlbscores

import StringIO
import sys

class IdenticalException(BaseException):
    def __init__(self):
        self.value = "Identical return values!"


# Basic functionality tests
# General idea is these all should a) and b) produce different output

argstocheck = [ [""], ["-t"], ["-y"], ["-b"], ["-s"], ["-tt"] ]

stdouts = []
stdout_save = sys.stdout

for a in argstocheck:
    stdouts.append([a, StringIO.StringIO()] )
    sys.stdout = stdouts[-1][1]
    sys.argv = ['./mlbscores.py'] + a
    mlbscores.main(['./mlbscores.py'] + a)

# Set stdout back to normal
sys.stdout = stdout_save

checked = []

for output in stdouts:
    if any( output[1].getvalue() == x[1].getvalue() for x in checked ):
#        if  md5.new(output[1].getvalue()).digest() ==  md5.new(checked[0][1].getvalue()).digest():
        print "Identical results between", output[0], checked[0][0]
        print output[1].getvalue()
        print checked[0][1].getvalue()
        
        raise IdenticalException()
    else:
        checked.append(output)


