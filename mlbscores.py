#!/usr/bin/python

import json
import urllib2
import datetime
import sys
import argparse

bestteams = ["CHC"]

def printgame(game):
    sys.stdout.write("%-3s @ %-3s   " % (game["away_name_abbrev"], game["home_name_abbrev"]))
    
    status = game["status"]["status"]
    
    if status == "Preview":
        sys.stdout.write("  %6s %s " % (game["time"], game["time_zone"]))
        homep = game["home_probable_pitcher"]
        awayp = game["away_probable_pitcher"]

        sys.stdout.write("%12s (%s) vs %12s (%s)"
            % ( awayp["last_name"], awayp["era"],  homep["last_name"], homep["era"] )  \
            )

    else: 
        if not status == "In Progress":
            sys.stdout.write( "%-8s" %( status ))
        else:
            innpart = "Mid"
            if game["status"]["inning"] == "Y":
                innpart = "Top" 
            else: 
                innpart = "Bot"
            sys.stdout.write( "%3s %-4s" %( innpart, game["status"]["inning"]   ))
        
        if status == "Postponed":
            sys.stdout.write( "  (%s)" %(game["status"]["reason"] ))
            
        if "linescore" in game:
            hscore = int( game["linescore"]["r"]["home"] )
            ascore = int( game["linescore"]["r"]["away"] )
            sys.stdout.write("   %d-%d" %( ascore, hscore ))
            
def printdetails(game):
    ninn = max(9, len(game["linescore"]["inning"]))
    # FIXME  Make exception
    if not "linescore" in game:
        return

    linescore = game["linescore"]

    # Format header
    sys.stdout.write("    ")
    for i in range(ninn):
        sys.stdout.write(" %d " % (i+1))
    sys.stdout.write("|  H  R  E SO\n")
    
    sys.stdout.write("%-4s" % game["away_name_abbrev"])
    for i in range(len(linescore["inning"])):
        try:
            sys.stdout.write("%2d " % int( linescore["inning"][i]["away"] ) )
        except:
            sys.stdout.write("   ")
    for i in range(ninn - len(linescore["inning"])):
        sys.stdout.write("   ")
    sys.stdout.write("| %2d %2d %2d %2d\n" % \
      (int(linescore["h"]["away"]), int(linescore["r"]["away"]), \
        int(linescore["e"]["away"]), int(linescore["so"]["home"]))  )
    
    sys.stdout.write("%-4s" % game["home_name_abbrev"])
    for i in range(len(linescore["inning"])):
        try:
            sys.stdout.write("%2d " % int( linescore["inning"][i]["home"] ) )
        except:
            sys.stdout.write("   ")
    for i in range(ninn - len(linescore["inning"])):
        sys.stdout.write("   ")
    sys.stdout.write("| %2d %2d %2d %2d\n" % \
      (int(linescore["h"]["home"]), int(linescore["r"]["home"]), \
        int(linescore["e"]["home"]), int(linescore["so"]["away"]))  )


def printboxscore(game):
    boxscore_url = \
         "http://gd2.mlb.com/" + game["game_data_directory"] + "/boxscore.json"
    #print boxscore_url
    sys.stdout.write("\n")

    boxjsondata = urllib2.urlopen(boxscore_url)
    boxscore= json.loads(boxjsondata.read())["data"]["boxscore"]
    #boxscore = json.loads(open("boxscore.json", "r").read())["data"]["boxscore"]

#    sys.stdout.write("%-20s\n" % game[pitchers["team_flag"]+"_team_name"]  )

    #  Print batting stats
    for batters in boxscore["batting"]:

        #  Ugh.  Recast as list if there's only one pitcher
        if not isinstance(batters["batter"], list):
            batters["batter"] = [batters["batter"]]

        sys.stdout.write("%-20s   H  BB   R  HR  SO\n" %
                         
                         game[batters["team_flag"]+"_team_name"]  )
                          
        
        sums = {"h" :0 ,"bb" : 0, "r" : 0, "hr" : 0, "so" :0 }

        for p in batters["batter"]:
            try:
                sys.stdout.write("%-20s %3d %3d %3d %3d %3d\n" % (p["name_display_first_last"], \
                     int(p["h"]), int(p["bb"]), int(p["r"]),\
                    int(p["hr"]), int(p["so"])))
            except Exception as e:
                print e

            for k in sums.keys():
                sums[k] += float(p[k])
        sys.stdout.write("%-20s %3d %3d %3d %3d %3d\n\n" % ("TOTAL", \
            int(sums["h"]), int(sums["bb"]), int(sums["r"]),\
            int(sums["hr"]), int(sums["so"]) ))

    

    #  Print pitchers IP count SO H, BB, R  HR and sum
    for pitchers in boxscore["pitching"]:

        #  Ugh.  Recast as list if there's only one pitcher
        if not isinstance(pitchers["pitcher"], list):
            pitchers["pitcher"] = [pitchers["pitcher"]]

        sys.stdout.write("%-20s   IP  NP SO  H BB  R HR   ERA\n" %
                         
                         game[pitchers["team_flag"]+"_team_name"]  )
                          
        
        sums = {"out" : 0, "np" : 0,  "so" :0 ,"h" : 0, "bb" : 0, "r" : 0, "hr" :0 }

        for p in pitchers["pitcher"]:
            try:
                sys.stdout.write("%-20s %4.1f %3d %2d %2d %2d %2d %2d %5.2f\n" % (p["name_display_first_last"], \
                    float(p["out"])/3, int(p["np"]), int(p["so"]), int(p["h"]), int(p["bb"]), int(p["r"]),\
                    int(p["hr"]), float(p["era"] )))
            except Exception as e:
                print e

            for k in sums.keys():
                sums[k] += float(p[k])
        sys.stdout.write("%-20s %4.1f %3d %2d %2d %2d %2d %2d\n\n" % ("TOTAL", \
            float(sums["out"])/3, int(sums["np"]), int(sums["so"]), int(sums["h"]), int(sums["bb"]), int(sums["r"]),\
            int(sums["hr"])))
#    sys.stdout.write("\n")

def print_standings():
    now = datetime.datetime.now()

    standings_uri = "http://mlb.com/lookup/json/named.standings_schedule_date.bam?season=" \
        + str(now.year) + "&schedule_game_date.game_date='" + now.strftime("%y%m%d" ) + "'&sit_code='h0'&league_id=103&league_id=104&all_star_sw='N'&version=2"
        
    standingsjson = urllib2.urlopen(standings_uri)
    standings = json.loads(standingsjson.read())["standings_schedule_date"]["standings_all_date_rptr"]["standings_all_date"]

    orderedkeys = []
    divdict = {}

    for league in standings:
        for team in league["queryResults"]["row"]:
            try:
                divdict[team['division']].append(team)
            except:
                orderedkeys.append( team['division'] )
                divdict[team['division']] = [team]

    for div in orderedkeys:
        sys.stdout.write("%-24s    W    L       %%   GB  L10 Strk\n" % div)
        for team in divdict[div]:
            sys.stdout.write("%-24s %4d %4d   %5.3f %4s %4s %4s\n" \
                % (team['team_full'], int(team['w']), int(team['l']), float(team['pct']), \
                    team['gb'], team['last_ten'], team['streak'] ))

        sys.stdout.write("\n")
    sys.stdout.write("\n")

###########################

argparser = argparse.ArgumentParser(description="MLB scores utility")
argparser.add_argument("-y", action="store_const", dest="t", const=-1, help="Show for yesterday")
argparser.add_argument("-t", action="store_const", dest="t", const=1, help="Show for tomorrow")
argparser.add_argument("-tt", action="store_const", dest="t", const=2, help="Show for two days from now")
argparser.add_argument("-b", action="store_true", dest="boxscore", help="Show boxscore output for best games")
argparser.add_argument("-f", action="store_true", dest="full", help="Show full output for all games")
argparser.add_argument("-s", action="store_true", dest="standings", help="Show current standings")
argparser.add_argument("teams", help="Explicit teams only", nargs="*")
args = argparser.parse_args()

if args.standings:
    print_standings()
    exit(0)

# Identify date
now = datetime.datetime.now()
if now.hour < 10:
    #  If before 10AM, use yesterday
    now = now - datetime.timedelta(1)
if args.t:
    now = now + args.t*datetime.timedelta(1)
    
explicitteams = False
if len(args.teams) > 0:
    explicitteams = True
    bestteams = [x.upper() for x in args.teams]

# Form JSON URL and load
mlb_scoreboard_url = \
     "http://gd2.mlb.com/components/game/mlb/year_%4d/month_%02d/day_%02d/master_scoreboard.json" \
     % (now.year, now.month, now.day)
scoreboardjson = urllib2.urlopen(mlb_scoreboard_url)
gamejson = json.loads(scoreboardjson.read())["data"]["games"]
#gamejson = json.loads(open("master_scoreboard.json", "r").read())["data"]["games"]

# Presort games

bestgames = []
remaininggames = []

for game in gamejson["game"]:
    if any( game["away_name_abbrev"] == s for s in bestteams ) or \
        any( game["home_name_abbrev"] == s for s in bestteams ):
        bestgames.append(game)
    else:
#        gametime = datime
        remaininggames.append(game)

#  Form output
sys.stdout.write("Baseball for " + now.strftime("%A %B %d, %Y") + "\n\n")
for game in bestgames:
    printgame(game)
    sys.stdout.write("\n")
    if "linescore" in game:
        printdetails(game)
        if args.boxscore:
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
    
