#!/usr/bin/python

# mlb scores and standing utility
#
# Seamus Riordan
# seamus@riordan.io
# May 1, 2016
# 
# Reads publicly available JSON data from mlb.com and prints out
# up to date scores, reduced box score, or standings
# Self contained script


import json
import urllib2
import datetime
import sys
import time
import argparse

# FIXME - read in from file
bestteams = ["CHC"]
# Switch from previous scores to today's scores at 10AM
daytime_rollover = 10 

base_scoreboard_url = "http://gd2.mlb.com/components/game/mlb/year_%4d/month_%02d/day_%02d/master_scoreboard.json"
base_boxscore_url   = "http://gd2.mlb.com/%s/boxscore.json"
base_standings_uri  = "http://mlb.com/lookup/json/named.standings_schedule_date.bam?season=%4s&schedule_game_date.game_date='%8s'&sit_code='h0'&league_id=103&league_id=104&all_star_sw='N'&version=2"
max_uri_retry = 5    # standings URI sometimes doesn't respond
wait_until_retry = 5 # number of seconds to wait until retrying standings after failure


class URIException( BaseException ):
    def __init__(self, value):
        self.value = value

def printgame(game):
    # Print out basic game status and score, or 
    # if the game hasn't started, when and who is pitching
    sys.stdout.write("%-3s @ %-3s   " % (game["away_name_abbrev"], game["home_name_abbrev"]))
    
    status = game["status"]["status"]
    
    if status == "Preview":
        # FIXME:  Add timezone support
        sys.stdout.write("  %6s %s " % (game["time"], game["time_zone"]))
        homep = game["home_probable_pitcher"]
        awayp = game["away_probable_pitcher"]

        sys.stdout.write("%12s (%s) vs %12s (%s)"
            % ( awayp["last_name"], awayp["era"],  homep["last_name"], homep["era"] )  \
            )

    else: 
        if not status == "In Progress":
            sys.stdout.write( "%-9s" %( status ))
        else:
            innpart = "Mid"
            if game["status"]["inning"] == "Y":
                innpart = "Top" 
            else: 
                innpart = "Bot"
            sys.stdout.write( "%3s %-5s" %( innpart, game["status"]["inning"]   ))
        
        if status == "Postponed":
            sys.stdout.write( "  (%s)" %(game["status"]["reason"] ))
            
        if "linescore" in game:
            hscore = int( game["linescore"]["r"]["home"] )
            ascore = int( game["linescore"]["r"]["away"] )
            sys.stdout.write("  %2d-%-2d" %( ascore, hscore ))
            
def printdetails(game):
    # Print more detailed line score
    ninn = max(9, len(game["linescore"]["inning"]))

    try:
        linescore = game["linescore"]
    except:
        print("Line score not found")
        return

    # Format header
    sys.stdout.write("    ")
    for i in range(ninn):
        sys.stdout.write("%2d " % (i+1))
    sys.stdout.write("|  H  R  E SO\n")
    
    sys.stdout.write("%-4s" % game["away_name_abbrev"])
    
    # Print for what we have data for
    for i in range(len(linescore["inning"])):
        try:
            sys.stdout.write("%2d " % int( linescore["inning"][i]["away"] ) )
        except:
            sys.stdout.write("   ")

    # Pad if innings are missing
    for i in range(ninn - len(linescore["inning"])):
        sys.stdout.write("   ")
    sys.stdout.write("| %2d %2d %2d %2d\n" % \
      (int(linescore["h"]["away"]), int(linescore["r"]["away"]), \
        int(linescore["e"]["away"]), int(linescore["so"]["home"]))  )
    
    # Print for what we have data for home team, same as above
    sys.stdout.write("%-4s" % game["home_name_abbrev"])
    for i in range(len(linescore["inning"])):
        try:
            sys.stdout.write("%2d " % int( linescore["inning"][i]["home"] ) )
        except:
            sys.stdout.write("   ")
    # Pad if innings are missing
    for i in range(ninn - len(linescore["inning"])):
        sys.stdout.write("   ")
    sys.stdout.write("| %2d %2d %2d %2d\n" % \
      (int(linescore["h"]["home"]), int(linescore["r"]["home"]), \
        int(linescore["e"]["home"]), int(linescore["so"]["away"]))  )


def printboxscore(game):
    # Print reduced box score data for all batters and pitchers
    boxscore_url = base_boxscore_url % game["game_data_directory"] 

    boxjsondata = urllib2.urlopen(boxscore_url)
    boxscore= json.loads(boxjsondata.read())["data"]["boxscore"]


    #  Print batting stats
    for batters in boxscore["batting"]:

        #  Ugh.  Recast as list if there's only one batterr
        if not isinstance(batters["batter"], list):
            batters["batter"] = [batters["batter"]]

        sys.stdout.write("   %-20s  PA   H  BB   R  HR  SO    OBP    OPS\n" %
                         
                         game[batters["team_flag"]+"_team_name"]  )
                          
        # batter variables we want to sum
        keystosum = ["ab", "h", "bb", "r", "hr", "so", "hbp", "sac"]
        sums = {}
        for k in keystosum: 
            sums[k] = 0

        for p in batters["batter"]:
            try:
                sys.stdout.write("%-23s %3d %3d %3d %3d %3d %3d  %5.3f  %5.3f\n" % (
                    "%2s %s" % (p["pos"], p["name_display_first_last"] ), \
                    int(p["ab"]) + int(p["bb"]) + int(p["hbp"]) + int(p["sac"]), int(p["h"]), int(p["bb"]), int(p["r"]),\
                    int(p["hr"]), int(p["so"]), float(p['obp']), float(p['obp']) + float(p['slg'])) )
            except Exception as e:
                print e

            for k in sums.keys():
                sums[k] += float(p[k])
        sys.stdout.write("   %-20s %3d %3d %3d %3d %3d %3d\n\n" % ("TOTAL", \
            int(sums["ab"]) + int(sums["bb"]) + int(sums["hbp"]) + int(sums["sac"]), \
            int(sums["h"]), int(sums["bb"]), int(sums["r"]), int(sums["hr"]), int(sums["so"]) ))

    

    #  Print pitchers IP count SO H, BB, R  HR, etc and sum
    for pitchers in boxscore["pitching"]:

        #  Ugh.  Recast as list if there's only one pitcher
        if not isinstance(pitchers["pitcher"], list):
            pitchers["pitcher"] = [pitchers["pitcher"]]

        sys.stdout.write("   %-20s   IP  PC SO  H BB  R HR   ERA\n" %
                         
                         game[pitchers["team_flag"]+"_team_name"]  )
                          
        keystosum = ["out", "np", "so", "h", "bb", "r", "hr"]
        # pitcher variables we want to sum
        sums = {}
        for k in keystosum: 
            sums[k] = 0

        for p in pitchers["pitcher"]:
            try:
                sys.stdout.write("   %-20s %4.1f %3d %2d %2d %2d %2d %2d %5.2f\n" % \
                    (p["name_display_first_last"],  float(p["out"])/3, int(p["np"]), \
                      int(p["so"]), int(p["h"]), int(p["bb"]), int(p["r"]), int(p["hr"]), float(p["era"] )))
            except Exception as e:
                print e

            for k in sums.keys():
                sums[k] += float(p[k])
        sys.stdout.write("   %-20s %4.1f %3d %2d %2d %2d %2d %2d\n\n" % ("TOTAL", \
            float(sums["out"])/3, int(sums["np"]), int(sums["so"]), int(sums["h"]), \
            int(sums["bb"]), int(sums["r"]), int(sums["hr"])))

def load_standings(uri):
    standingsjson = urllib2.urlopen(uri)
    standings = json.loads(standingsjson.read())["standings_schedule_date"]["standings_all_date_rptr"]["standings_all_date"]
    return standings


def print_standings():
    # Print standings
    now = datetime.datetime.now()

    standings_uri = base_standings_uri % (now.strftime("%Y"), now.strftime("%Y%m%d"))
    
    loaded_standings = False
    nretry = 0
    while not loaded_standings and nretry < max_uri_retry:
        try :
            standings = load_standings(standings_uri)
            loaded_standings = True
        except ValueError:
            nretry += 1
            sys.stderr.write("Standings JSON data not returned... retry %d\n" % nretry)
            time.sleep(wait_until_retry)

    if not loaded_standings:
        sys.stderr.write("Cannot load JSON standing data after %d retries\n" % max_uri_retry)
        raise URIException("Cannot load JSON standing data after %d retries" % max_uri_retry)

    orderedkeys = []
    divdict = {}

    sys.stdout.write("\n")
    for league in standings:
        for team in league["queryResults"]["row"]:
            try:
                divdict[team['division']].append(team)
            except:
                orderedkeys.append( team['division'] )
                divdict[team['division']] = [team]

    for div in orderedkeys:
        sys.stdout.write("%-24s    W    L       %%   GB WCGB  L10 Strk\n" % div)
        for team in divdict[div]:
            sys.stdout.write("%-24s %4d %4d   %5.3f %4s %4s %4s %4s\n" \
                % (team['team_full'], int(team['w']), int(team['l']), float(team['pct']), \
                    team['gb'], team['gb_wildcard'], team['last_ten'], team['streak'] ))

        sys.stdout.write("\n")
    sys.stdout.write("\n")

###########################
# Main code

def main(argv):
    global bestteams
    argparser = argparse.ArgumentParser(prog="mlbscores", description="MLB scores utility")

    #FIXME add in option for arbitrary day offset and specific dates?
    argparser.add_argument("-b", action="store_true", dest="boxscore", help="Show boxscore output for best games")
    argparser.add_argument("-f", action="store_true", dest="full", help="Show full output for all games")
    argparser.add_argument("-s", action="store_true", dest="standings", help="Show current standings")
    argparser.add_argument("teams", help="Show explicit teams only specified by space separated list of case insensitive abbreviated names  e.g. chc coL SF", nargs="*")
    argtgroup = argparser.add_mutually_exclusive_group()
    argtgroup.add_argument("-y", action="store_const", dest="dayoffset", const=-1, help="Show for yesterday")
    argtgroup.add_argument("-t", action="store_const", dest="dayoffset", const=1, help="Show for tomorrow")
    argtgroup.add_argument("-tt", action="store_const", dest="dayoffset", const=2, help="Show for two days from now")

    args = argparser.parse_args()
    
    if args.standings:
        print_standings()
        return

    # Identify date
    now = datetime.datetime.now()
    if now.hour < daytime_rollover:
        #  If before some hour, use previous calendar day
        now = now - datetime.timedelta(1)

    # offset days relative to arguments
    if args.dayoffset:
        now = now + args.dayoffset*datetime.timedelta(1)
        
    explicitteams = False
    if len(args.teams) > 0:
        explicitteams = True
        bestteams = [x.upper() for x in args.teams]

    # Form JSON URL and load
    scoreboard_url = base_scoreboard_url % (now.year, now.month, now.day)
    scoreboardjson = urllib2.urlopen(scoreboard_url)
    gamejson       = json.loads(scoreboardjson.read())["data"]["games"]

    # Presort games
    bestgames      = []
    remaininggames = []

    for game in gamejson["game"]:
        if any( game["away_name_abbrev"] == s for s in bestteams ) or \
            any( game["home_name_abbrev"] == s for s in bestteams ):
            bestgames.append(game)
        else:
            remaininggames.append(game)

    #  Form output
    sys.stdout.write("Baseball for " + now.strftime("%A %B %d, %Y") + "\n\n")
    for game in bestgames:
        printgame(game)
        sys.stdout.write("\n")
        if "linescore" in game:
            printdetails(game)
            if args.boxscore:
                sys.stdout.write("\n")
                printboxscore(game)
        sys.stdout.write("\n")

    if not explicitteams:
        for game in remaininggames:
            printgame(game)
            if args.full and "linescore" in game:
                sys.stdout.write("\n")
                printdetails(game)
                if args.boxscore:
                    printboxscore(game)
            sys.stdout.write("\n")
        
if __name__ == "__main__":
    main(sys.argv)
