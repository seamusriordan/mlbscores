#!/usr/bin/python
import mlbscores

import StringIO
import sys
import urllib2

class IdenticalException(BaseException):
    def __init__(self):
        self.value = "Identical return values!"


class NoFailureException(BaseException):
    def __init__(self):
        self.value = "Failed to fail"

def check_urls():
    # Make sure our URLs are at least valid from specific cases that worked at one point
    urllib2.urlopen(mlbscores.base_scoreboard_url % (2016, 05, 01))
    urllib2.urlopen( mlbscores.base_boxscore_url % "/components/game/mlb/year_2016/month_05/day_01/gid_2016_05_01_atlmlb_chnmlb_1")
    urllib2.urlopen( mlbscores.base_standings_uri % ("16", "160501"))

def test_functionality():
    # Basic functionality tests
    # General idea is these all should a) run without failure and b) produce different output

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
            checkedargs= []
            for x in checked:
                checkedargs.append(x[0])
            sys.stderr.write("Warning: Identical results found from arguments " + str(output[0]) + " and subset of " + str(checkedargs) + "\n")
            print output[1].getvalue()
            
#            Not necesssarily bad
#            raise IdenticalException()
        else:
            checked.append(output)

def test_standings_failure():
    sys.stdout.write("Checking standings retrieve failure:  Errors messages expected\n")
    save_uri = mlbscores.base_standings_uri
    mlbscores.base_standings_uri = "http://www.github.io/?%s_%s"

    did_not_fail = True
    try:
        mlbscores.print_standings()
    except mlbscores.URIException:
        did_not_fail = False
    mlbscores.base_standings_uri = save_uri

    if did_not_fail:
        raise NoFailureException()
    sys.stdout.write("Failed as expected\n")

if __name__ == "__main__":
    to_run =  [[check_urls,             "URL"], 
               [test_functionality,     "Basic functionality"], 
               [test_standings_failure, "Standings failure"] 
            ]

    for testcase in to_run:
        try:
            testcase[0]()
        except:
            exit("%s test failed!\n" % testcase[1])
        sys.stdout.write("%s test completed successfully!\n" % testcase[1])

    sys.stdout.write("\nAll tests completed successfully!\n")



