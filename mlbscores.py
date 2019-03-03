#!/usr/bin/python3

# mlb scores and standing utility
#
# Seamus Riordan
# seamus@riordan.io
# May 1, 2016
# 
# Reads publicly available JSON data from mlb.com and prints out
# up to date scores, reduced box score, or standings
# Self contained script

USE_CERTIFI = True

import json
import urllib3
try:
    import certifi
except:
    USE_CERTIFI = False
    urllib3.disable_warnings()

import datetime
from datetime import timezone
import sys
import time
import argparse

# FIXME - read in from file
bestteams = ["CHC"]
# Switch from previous scores to today's scores at 10AM
daytime_rollover = 10 

base_scoreboard_url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1,51&date=%04d-%02d-%02d&leagueId=103,104,420&hydrate=team,linescore(matchup,runners),flags,person,probablePitcher,stats,game(summary)&useLatestGames=false&language=en"
base_boxscore_url   = "http://statsapi.mlb.com/api/v1/game/%s/boxscore"
base_standings_uri  = "https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season=%4s&standingsTypes=regularSeason,springTraining&hydrate=division,conference,league"
max_uri_retry = 5    # standings URI sometimes doesn't respond
wait_until_retry = 5 # number of seconds to wait until retrying standings after failure


class URIException( BaseException ):
    def __init__(self, value):
        self.value = value

def printgame(game):
    # Print out basic game status and score, or 
    # if the game hasn't started, when and who is pitching
    sys.stdout.write("%-3s @ %-3s   " % (game["teams"]["away"]["team"]["abbreviation"], game["teams"]["home"]["team"]["abbreviation"]))
    
    status = game["status"]["abstractGameState"]



    try:
        #  Example "2019-03-03T18:05:00Z"
        gtime = datetime.datetime.strptime(game["gameDate"], "%Y-%m-%dT%H:%M:%SZ")
        gtime = gtime.replace(tzinfo= timezone.utc ).astimezone(tz=None)
        game["time"] = "%2d:%02d %s" % (gtime.hour, gtime.minute, gtime.tzname())
    except:
        game["time"] = "Good thing time does not exist"


    if (status == "Preview") or (status == "Pregame"):
        sys.stdout.write("  %9s" % (game["time"]))

        try:
            homep = game["teams"]["home"]["probablePitcher"]
        except:
            homep = {'lastName': "--"}
        try:
            homep["era"] = str(homep["stats"][1]["stats"]["era"])
        except:
            homep["era"] = "-"
        
        try:
            awayp = game["teams"]["away"]["probablePitcher"]
        except:
            awayp = {'lastName': "--"}
        try:
            awayp["era"] = str(awayp["stats"][1]["stats"]["era"])
        except:
            awayp["era"] = "-"


        sys.stdout.write("%12s (%s) vs %12s (%s)"
            % ( awayp["lastName"], awayp["era"],  homep["lastName"], homep["era"] )  \
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
            hscore = int( game["linescore"]["teams"]["home"]["runs"] )
            ascore = int( game["linescore"]["teams"]["away"]["runs"] )
            sys.stdout.write("  %2d-%-2d" %( ascore, hscore ))
            
def printdetails(game):
    # Print more detailed line score
    try:
        ninn = max(9, len(game["linescore"]["innings"]))
        linescore = game["linescore"]
    except:
        print("Line score not found")
        return

    # Format header
    sys.stdout.write("    ")
    for i in range(ninn):
        sys.stdout.write("%2d " % (i+1))
    sys.stdout.write("|  H  R  E\n")
    
    sys.stdout.write("%-4s" %  game["teams"]["away"]["team"]["abbreviation"] )
    
    # Print for what we have data for
    for i in range(len(linescore["innings"])):
        try:
            sys.stdout.write("%2d " % int( linescore["innings"][i]["away"]["runs"] ) )
        except:
            sys.stdout.write("   ")

    # Pad if innings are missing
    for i in range(ninn - len(linescore["innings"])):
        sys.stdout.write("   ")

    for t in ["home", "away"]:
        for k in ["hits", "runs", "errors"]:
            try:
                linescore["teams"][t][k]
            except:
                linescore["teams"][t][k] = 0

    sys.stdout.write("| %2d %2d %2d\n" % \
      (int(linescore["teams"]["away"]["hits"]), int(linescore["teams"]["away"]["runs"]), \
      int(linescore["teams"]["away"]["errors"]))  )
    
    # Print for what we have data for home team, same as above
    sys.stdout.write("%-4s" % game["teams"]["home"]["team"]["abbreviation"])
    for i in range(len(linescore["innings"])):
        try:
            sys.stdout.write("%2d " % int( linescore["innings"][i]["home"]["runs"] ) )
        except:
            sys.stdout.write("   ")
    # Pad if innings are missing
    for i in range(ninn - len(linescore["innings"])):
        sys.stdout.write("   ")
    sys.stdout.write("| %2d %2d %2d\n" % \
      (int(linescore["teams"]["home"]["hits"]), int(linescore["teams"]["home"]["runs"]), \
        int(linescore["teams"]["home"]["errors"]))  )


def printboxscore(game):
    # Print reduced box score data for all batters and pitchers
    boxscore_url = base_boxscore_url % game["gamePk"] 

    
    boxjsondata = ''
    if USE_CERTIFI:
        urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where()).request('GET', boxscore_url)
    else:
        urllib3.PoolManager().request('GET', boxscore_url)
    #boxscore= json.loads(boxjsondata.read())["data"]["boxscore"]
    boxscore= json.loads(boxjsondata.data)

    for team in boxscore["teams"]:
        #  Print batting stats
        sys.stdout.write("   %-20s  PA   H  BB   R  HR  SO    OBP    OPS\n" %
                         boxscore["teams"][team]["team"]["name"] )
                          
        # batter variables we want to sum
        keystosum = ["atBats", "hits", "baseOnBalls", "runs", "homeRuns", "strikeOuts", "hitByPitch", "sacFlies", "sacBunts"]
        sums = {}
        for k in keystosum: 
            sums[k] = 0

        batters = boxscore["teams"][team]["batters"] 

        for pid in batters:
            p = boxscore["teams"][team]["players"]["ID"+str(pid)]

            bstats = p["stats"]["batting"]
            sstats = p["seasonStats"]["batting"]

            # Vars that may not be defined
            for k in keystosum:
                if not k in bstats:
                    bstats[k] = 0

            try:
                sys.stdout.write("%-23s %3d %3d %3d %3d %3d %3d  %5.3f  %5.3f\n" % (
                    "%2s %s" % (p["position"]["abbreviation"], p["person"]["fullName"] ), \
                    int(bstats["atBats"]) + int(bstats["baseOnBalls"]) + int(bstats["hitByPitch"]) + int(bstats["sacFlies"])+int(bstats["sacBunts"]), int(bstats["hits"]), int(bstats["baseOnBalls"]), int(bstats["runs"]),\
                    int(bstats["homeRuns"]), int(bstats["strikeOuts"]), float(sstats['obp']), float(sstats['obp']) + float(sstats['slg'])) )
            except Exception as e:
                print(e)

            for k in sums.keys():
                try:
                    sums[k] += float(bstats[k])
                except:
                    sums[k] += 0.0
        sys.stdout.write("   %-20s %3d %3d %3d %3d %3d %3d\n\n" % ("TOTAL", \
            int(sums["atBats"]) + int(sums["baseOnBalls"]) + int(sums["hitByPitch"]) + int(sums["sacFlies"]) + int(sums["sacBunts"]), \
            int(sums["hits"]), int(sums["baseOnBalls"]), int(sums["runs"]), int(sums["homeRuns"]), int(sums["strikeOuts"]) ))

    

    #  Print pitchers IP count SO H, BB, R  HR, etc and sum
    for team in boxscore["teams"]:

        sys.stdout.write("   %-20s   IP  PC SO  H BB  R HR   ERA\n" %
                          boxscore["teams"][team]["team"]["name"] )                
                          
        keystosum = ["pitchesThrown", "inningsPitched", "strikeOuts", "hits", "baseOnBalls", "runs", "homeRuns"]
        # pitcher variables we want to sum
        sums = {}
        for k in keystosum: 
            sums[k] = 0

        pitchers = boxscore["teams"][team]["pitchers"] 

        for pid in pitchers:
            p = boxscore["teams"][team]["players"]["ID"+str(pid)]

            pstats = p["stats"]["pitching"]
            sstats = p["seasonStats"]["pitching"]

            try:
                sys.stdout.write("   %-20s %4.1f %3d %2d %2d %2d %2d %2d %5.2f\n" % \
                    (p["person"]["fullName"],  #float(pstats["outs"])/3, float(pstats["inningsPitched"]), \
                    float(pstats["inningsPitched"]),  int(pstats["pitchesThrown"]), \
                      int(pstats["strikeOuts"]), int(pstats["hits"]), int(pstats["baseOnBalls"]), int(pstats["runs"]), int(pstats["homeRuns"]), float(sstats["era"] )))
            except Exception as e:
                print(e)

            for k in sums.keys():
                sums[k] += float(pstats[k])
        sys.stdout.write("   %-20s      %3d %2d %2d %2d %2d %2d\n\n" % ("TOTAL", \
            #float(sums["outs"])/3, float(sums["inningsPitched"]),
            int(sums["pitchesThrown"]), int(sums["strikeOuts"]), int(sums["hits"]), \
            int(sums["baseOnBalls"]), int(sums["runs"]), int(sums["homeRuns"])))

def load_standings(uri):
    standingsjson = ''
    if USE_CERTIFI:
        standingsjson = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where()).request('GET', uri)
    else:
        standingsjson = urllib3.PoolManager().request('GET', uri)

    standings = json.loads(standingsjson.data)["records"]
    return standings


def print_standings():
    # Print standings
    now = datetime.datetime.now()

    standings_uri = base_standings_uri % (now.strftime("%Y"))
    
    loaded_standings = False
    nretry = 0
    while not loaded_standings and nretry < max_uri_retry:
        try :
            standings = load_standings(standings_uri)
            loaded_standings = True
        except ValueError:
            nretry += 1
            if nretry > 1:
                sys.stderr.write("Standings JSON data not returned... retry %d\n" % nretry)
            time.sleep(wait_until_retry)

    if not loaded_standings:
        sys.stderr.write("Cannot load JSON standing data after %d retries\n" % max_uri_retry)
        raise URIException("Cannot load JSON standing data after %d retries" % max_uri_retry)

    orderedkeys = []
    divdict = {}

    sys.stdout.write("\n")
    for division in standings:
#        if division['standingsType'] == "regularSeason":
        if division['standingsType'] == "springTraining":
            for team in division["teamRecords"]:
                try:
                    divdict[division['division']['name']].append(team)
                except:
                    orderedkeys.append( (division['division']['name'], division['division']['id']) )
                    divdict[division['division']['name']] = [team]

#    for divpair in sorted(orderedkeys, key= lambda k: k[1] ):
#        div = divpair[0]
    #  Just hardcode an order...
    for div in [u'American League East', u'American League Central',u'American League West', u'National League East',  u'National League Central', u'National League West']:
        sys.stdout.write("%-24s    W    L       %%   GB WCGB   L10 Strk\n" % div)
        # Clean up entries first
        for team in divdict[div]:
            try:
                float(team['pct'])
            except:
                team['pct'] = 0.0

            try:
                team['streak']['streakCode']
            except:
                team['streak'] = {}
                team['streak']['streakCode'] = "-"

        for team in sorted(divdict[div], key= lambda d: d['divisionRank'] ):
            sys.stdout.write("%-24s %4d %4d   %5.3f %4s %4s %2d-%2d %4s\n" \
                % (team['team']['name'], int(team['wins']), int(team['losses']), float(team['winningPercentage']), \
#                    team['gamesBack'], team['wildCardGamesBack'], team['records']['splitRecords'][4]['wins'], team['records']['splitRecords'][4]['losses'],  team['streak']['streakCode']) )
                    0, 0, team['records']['splitRecords'][4]['wins'], team['records']['splitRecords'][4]['losses'], team['streak']['streakCode']))

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
    scoreboardjson = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where()).request('GET',scoreboard_url)
    gamejson       = json.loads(scoreboardjson.data)["dates"][0]["games"]
    
    # Presort games
    bestgames      = []
    remaininggames = []
    
    if len(gamejson) == 0:
        sys.stdout.write("No games scheduled for " + now.strftime("%A %B %d, %Y") + "\n\n")
        return

# If there's a single game JSON just has it as a key rather than
# an array.  We recast it like such so we can process it as normal
    games = []
        
    # Filter by date
    #thisdate = now.strftime("%Y/%m/%d")
    #for game in gamesjson:
    #    if game['original_date'] == thisdate:
    #        games.append(game)

    for game in gamejson:
        if any( game["teams"]["away"]["team"]["abbreviation"] == s for s in bestteams ) or \
            any( game["teams"]["home"]["team"]["abbreviation"] == s for s in bestteams ):
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
