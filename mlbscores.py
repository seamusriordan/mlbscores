#!/usr/bin/python3

# mlb scores and standing utility
#
# Seamus Riordan
# seamus@riordan.io
# March 23, 2019
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
import argparse

# FIXME - read in from file
bestteams = ["CHC"]
# Switch from previous scores to today's scores at 10AM
daytime_rollover = 10 

base_scoreboard_url = "https://statsapi.mlb.com/api/v1/schedule?sportId=1,51&date=%04d-%02d-%02d&leagueId=103,104,420&hydrate=team,linescore(matchup,runners),flags,person,probablePitcher,stats,game(summary)&useLatestGames=false&language=en"
base_boxscore_url   = "http://statsapi.mlb.com/api/v1/game/%s/boxscore"
base_standings_uri  = "https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season=%4s&standingsTypes=regularSeason,springTraining&hydrate=division,conference,league"

class gameDay:
    def __init__(self, dayOffset = 0):
        self.games = []
        self.bestGames = []
        self.gameDayDate = datetime.datetime.now()
        self.loadGameData(dayOffset)

    def loadGameData(self, dayOffset):
        if dayOffset == None:
            dayOffset = 0
        self.setScoreboardDate(dayOffset)
        jsonData = self.tryToGetJSON()
        for aGame in jsonData:
            self.fillGameData(aGame)

    def setScoreboardDate(self, offset):
        now = datetime.datetime.now()
        rolledOverDate    = self.modifyDateForRollover(now)
        dateForScoreboard = self.modifyDateForOffset(rolledOverDate, offset)
        self.gameDayDate = dateForScoreboard
        
    def modifyDateForRollover(self, date):
        rolledOverDate = date
        if date.hour < daytime_rollover:
            rolledOverDate = date - datetime.timedelta(1)
        return rolledOverDate

    def modifyDateForOffset(self, date, offset):
        return date + datetime.timedelta(1)*offset


    def tryToGetJSON(self):
        rawJSON = self.getRecordsFromURL()
        try:
            gameData = rawJSON["dates"][0]["games"]
        except:
            sys.stdout.write("\nNo games scheduled for " + self.gameDayDate.strftime("%A %B %d, %Y") + "\n\n")
            #raise Exception("No games scheduled for " + self.gameDayDate.strftime("%A %B %d, %Y") )
            gameData = {}
        return gameData
    

    def getRecordsFromURL(self):
        scoreboard_url = self.formScoreBoardURL()
        loader = JSONloader(scoreboard_url)
        JSONtoReturn = loader.loadJSON()
        return JSONtoReturn

    def formScoreBoardURL(self):
        return base_scoreboard_url %\
             (self.gameDayDate.year, self.gameDayDate.month, self.gameDayDate.day)
    

    def fillGameData(self, gameJSON):
        aGame = game()
        aGame.unpackJSON(gameJSON)
        if self.hasBestTeam(aGame):
            self.bestGames.append(aGame)
        else:
            self.games.append(aGame)

    def hasBestTeam(self, aGame):
        return self.hasTeam(aGame, bestteams)

    def hasTeam(self, aGame, teams):
        teamIsInGame = False
        for side in ['home', 'away']:
            teamIsInGame = teamIsInGame or any( aGame.teams[side].nameAbbreviation == s for s in teams ) 
        return teamIsInGame

    def printGameDay(self, showBoxScore, teams = [] ):
        if self.getNumberOfGames() > 0:
            self.printGameDayHeader()
            
            if len(teams) == 0:
                self.printAllGames(showBoxScore)
            else:
                self.printCertainGames(teams, showBoxScore)

    def getNumberOfGames(self):
        return len(self.bestGames + self.games)
   
    def printGameDayHeader(self):
        sys.stdout.write("\nBaseball for " + self.gameDayDate.strftime("%A %B %d, %Y") + "\n\n")
        return
    
    def printAllGames(self, showBoxScore):
        for aGame in self.bestGames:
            aGame.printGameSummary()
            aGame.printGameDetails()
            if showBoxScore:
                aGame.printBoxScore()
        for aGame in self.games:
            aGame.printGameSummary()

    def printCertainGames(self, teams, showBoxScore):
        for aGame in self.bestGames + self.games:
            if self.hasTeam(aGame, teams):
                aGame.printGameSummary()
                aGame.printGameDetails()
                if showBoxScore:
                    aGame.printBoxScore()

    
class game:
    def __init__(self):
        self.gamePk = 0
        self.gameTime = datetime.datetime.now()
        self.gameStatus = ""
        self.gameStatusReason = ""
        self.inningState = ""
        self.innings = 0
        self.currentInningOrdinal= ""
        self.teams = {'home': gameTeam(), 'away': gameTeam()}
        
    def unpackJSON(self, jsonData):
        self.gamePk = jsonData["gamePk"]
        self.gameStatus = jsonData["status"]["detailedState"]
        try:
            self.gameStatusReason  = jsonData['status']['reason']
        except:
            self.gameStatusReason  = ""
        try:
            self.currentInningOrdinal = jsonData['linescore']['currentInningOrdinal']
        except:
            self.currentInningOrdinal = ""
        self.gameTime = self.extractGameTime(jsonData)

        try:
            self.innings = len(jsonData['linescore']['innings'])
        except:
            self.innings = 0

        try: 
            self.inningState = jsonData['linescore']['inningState'][:3]
        except:
            self.inningState = ""
        self.teams['home'].loadJSON(jsonData['teams']['home'])
        self.teams['away'].loadJSON(jsonData['teams']['away'])
        try:
            linescoreJSON = jsonData['linescore']
            self.loadRunsForAllInnings(linescoreJSON['innings'])
            self.loadHitsAndErrors(linescoreJSON)
        except:
            pass

    def extractGameTime(self, jsonData):
        try:
            #  Cast JSON time format to datime object
            #  Example "2019-03-03T18:05:00Z"
            gtime = datetime.datetime.strptime(jsonData["gameDate"], "%Y-%m-%dT%H:%M:%SZ")
            # Convert to local time zone
            gtime = gtime.replace(tzinfo= timezone.utc).astimezone(tz=None)
            timeString = gtime.strftime("%H:%M %Z")
        except:
            timeString = "Good thing time does not exist"
        return timeString

    def loadRunsForAllInnings(self, linescore):
        nInnings = len(linescore)
        for i in range(nInnings):
            for side in ['home' ,'away']:
                self.teams[side].runsByInning.append(self.loadRunsForAnInning(linescore, side, i))

    def loadRunsForAnInning(self, linescore, teamKey, inning):
        try:
            runs = int(linescore[inning][teamKey]['runs'])
        except:
            runs = 0
        return runs

    def loadHitsAndErrors(self, linescore):
        for side in ['home' ,'away']:
            try:
                self.teams[side].hits   = int(linescore['teams'][side]['hits'])
            except:
                self.teams[side].hits   = 0
            try:
                self.teams[side].errors = int(linescore['teams'][side]['errors'])
            except:
                self.teams[side].errors = 0

    def loadBoxScore(self):
        jsonData = self.loadBoxJSON()
        for side in ['home', 'away']:
            self.teams[side].loadBoxScore(jsonData['teams'][side])
        return
 
    def loadBoxJSON(self):
        boxscore_url = self.formBoxScoreURL()
        loader = JSONloader(boxscore_url)
        jsondata = loader.loadJSON()
        if len(jsondata.keys()) == 0:
            sys.stdout.write("   No box score data available                \n")
        return jsondata
    
    def formBoxScoreURL(self):
        return base_boxscore_url % self.gamePk
        

    def printGameSummary(self):
        self.printGameHeader()
        if self.isWaitingToStart():
            self.printTimeAndPitcher()
        else:
            self.printGameUpdate()
        sys.stdout.write("\n")

    def printGameHeader(self):
        awayAbbrevName = self.teams['away'].nameAbbreviation
        homeAbbrevName = self.teams['home'].nameAbbreviation
        sys.stdout.write("%-3s @ %-3s   " % (awayAbbrevName, homeAbbrevName))

    
    def isWaitingToStart(self):
        waitingToStartKeys = ["Preview", "Pre-Game", "Scheduled"]
        isWaiting = False
        for k in waitingToStartKeys:
            if self.gameStatus == k:
                isWaiting = True
        return isWaiting

    def printTimeAndPitcher(self):
        sys.stdout.write("  %s" % (self.gameTime))
        sys.stdout.write("%12s (%s) vs %12s (%s)" % ( \
                     self.teams['away'].probablePitcher.lastName,\
                     self.teams['away'].probablePitcher.stats['era'],\
                     self.teams['home'].probablePitcher.lastName, \
                     self.teams['home'].probablePitcher.stats['era']) )

    def printGameUpdate(self):
        if self.isInProgress():
            self.printProgress()
        else:
            self.printStatus()
        self.printScore()

    def printProgress(self):
        sys.stdout.write( "  %3s %-9s" %( self.inningState, self.currentInningOrdinal ))
        

    def printStatus(self):
        self.printStatusPrefix()
        if self.isPostponed():
            self.printStatusReason()

    def printStatusPrefix(self):
        sys.stdout.write( "  %-13s" %( self.gameStatus ))

    def printStatusReason(self):
        sys.stdout.write( "  (%s)" %(self.gameStatusReason))

    def isInProgress(self):
        return self.gameStatus == 'In Progress'

    def isPostponed(self):
        return self.gameStatus == 'Postponed'

    def printScore(self):
        if self.hasLineScore():
            homeTeamRuns = self.teams['home'].getTotalRuns()
            awayTeamRuns = self.teams['away'].getTotalRuns()
            sys.stdout.write("%2d-%-2d" %( awayTeamRuns, homeTeamRuns ))
        else:
            sys.stdout.write("     -    ")

    def hasLineScore(self):
        return len(self.teams['away'].runsByInning)>0

    def printGameDetails(self):
        self.printLineScore()
            
    def printLineScore(self):
        inningsToPrint = max(9, self.innings)
        self.printLineScoreHeader(inningsToPrint)
        self.teams['away'].printLineScore(inningsToPrint)
        self.teams['home'].printLineScore(inningsToPrint)
        self.printLineScoreFooter()
        
    def printLineScoreHeader(self, inningsToPrint):
        sys.stdout.write("    ")
        for i in range(inningsToPrint):
            sys.stdout.write("%2d " % (i+1))
        sys.stdout.write("|  H  R  E\n")

    def printLineScoreFooter(self):
        sys.stdout.write("\n")

    def printBoxScore(self):
        self.loadBoxScore()
        self.teams['away'].printBoxScore('batters')
        self.teams['home'].printBoxScore('batters')
        self.teams['away'].printBoxScore('pitchers')
        self.teams['home'].printBoxScore('pitchers')


class gameTeam:
    def __init__(self):
        self.nameAbbreviation = ""
        self.name = ""
        self.probablePitcher = pitcher()
        self.runsByInning = []
        self.errors = 0
        self.hits = 0
        self.players = {'batters': [], 'pitchers': []}
        self.boxStatKeys = {
            'batters': ['plateAppearances', 'hits', 'baseOnBalls', \
                       'runs', 'homeRuns', 'strikeOuts', 'obp', 'ops'],  \
            'pitchers': ['inningsPitched','pitchesThrown',  'strikeOuts',\
                          'hits', 'baseOnBalls', 'runs', 'homeRuns', 'era']}

        self.boxSumStatKeys = {
            'batters': ['plateAppearances', 'hits', 'baseOnBalls', \
                       'runs', 'homeRuns', 'strikeOuts'],  \
            'pitchers': ['pitchesThrown', 'strikeOuts',\
                          'hits', 'baseOnBalls', 'runs', 'homeRuns']}
        
        self.boxScoreHeaderFormatString = { \
            'batters':  "   %-20s  PA   H  BB   R  HR  SO    OBP    OPS\n", \
            'pitchers': "   %-20s   IP  PC SO  H BB  R HR   ERA\n"}

        self.boxScoreFormatString = {\
            'batters':  "%-23s %3d %3d %3d %3d %3d %3d  %5.3f  %5.3f\n", \
            'pitchers': "   %-20s %4.1f %3d %2d %2d %2d %2d %2d %5.2f\n"  }

        self.boxScoreFooterFormatString = { \
            'batters' : "   %-20s %3d %3d %3d %3d %3d %3d\n\n", \
            'pitchers': "   %-20s      %3d %2d %2d %2d %2d %2d\n\n"}

    def unpackJSON(self, jsonData):
        self.nameAbbreviation = jsonData['team']["abbreviation"]
        self.name = jsonData['team']["name"]
        try:
            pitcherJSON = jsonData["probablePitcher"]
            self.probablePitcher.lastName = pitcherJSON['lastName']
        except:
            self.probablePitcher.lastName = "TBD"

        try:
            self.probablePitcher.stats['era'] = str(pitcherJSON['stats'][1]['stats']['era'])
        except:
            self.probablePitcher.stats['era'] = "-"
        
    def loadBoxScore(self, jsonData):
        self.loadBatterBoxes(jsonData)
        self.loadPitcherBoxes(jsonData)
    
    def loadBatterBoxes(self, jsonData):
        for playerID in jsonData['batters']:
            playerJSON = jsonData['players']["ID"+str(playerID)]
            self.addBatter(playerJSON)

    def addBatter(self, playerJSON):
        newBatter = batter()
        newBatter.loadStats(playerJSON)
        self.players['batters'].append(newBatter)

    def loadPitcherBoxes(self, jsonData):
        for playerID in jsonData['pitchers']:
            playerJSON = jsonData['players']["ID"+str(playerID)]
            self.addPitcher(playerJSON)

    def addPitcher(self, playerJSON):
        newPitcher = pitcher()
        newPitcher.loadStats(playerJSON)
        self.players['pitchers'].append(newPitcher)


    def getTotalStat(self, playerSetKey, statKey):
        statsByPlayers = [aPlayer.stats[statKey] for aPlayer in self.players[playerSetKey]]
        return sum(statsByPlayers) 

    def printInningRunsWithData(self):
        inningsWithData    = self.getLineScoreLength()
        for i in range(inningsWithData):
            sys.stdout.write("%2d " % self.runsByInning[i])
    
    def getLineScoreLength(self):
        return len(self.runsByInning)

    def printLineScore(self, nInningsToPrint):
        sys.stdout.write("%-4s" %  self.nameAbbreviation )
        self.printInningRuns(nInningsToPrint)
        self.printHRE()

    def printInningRuns(self, nInningsToPrint):
        inningsWithoutData = nInningsToPrint - self.getLineScoreLength()
        self.printInningRunsWithData()
        self.printNBlankInnings(nBlanks = inningsWithoutData)

    def printHRE(self):
        sys.stdout.write("| %2d %2d %2d\n" % \
            (self.getTotalHits(), self.getTotalRuns(), self.getTotalErrors()))
 
    def printNBlankInnings(self, nBlanks):
        for i in range(nBlanks):
            sys.stdout.write("   ")
    
    def printBoxScore(self, playerSet):
        self.printBoxScoreHeader(playerSet)
        self.printBoxScoreForAll(playerSet)
        self.printBoxScoreFooter(playerSet)

    def printBoxScoreHeader(self, playerSet):
        sys.stdout.write(self.boxScoreHeaderFormatString[playerSet] % self.name)

    def printBoxScoreForAll(self, playerSet):
        for aPlayer in self.players[playerSet]:
            formatVals = self.formBoxScoreTuple(aPlayer, playerSet)
            sys.stdout.write(self.boxScoreFormatString[playerSet] % formatVals)

    def formBoxScoreTuple(self, aPlayer, playerSet):
        boxScoreTuple = (aPlayer.boxName, )
        boxScoreTuple += self.getBoxScoreStats(aPlayer, self.boxStatKeys[playerSet])
        return boxScoreTuple
    
    def getBoxScoreStats(self, aPlayer, keys):
        statmap = [aPlayer.stats[k] for k in keys]
        return tuple(statmap)

    def printBoxScoreFooter(self, playerSet):
        boxSumTuple = ("TOTAL", ) + self.formBoxScoreSumTuple(playerSet)
        sys.stdout.write(self.boxScoreFooterFormatString[playerSet] % boxSumTuple )

    def formBoxScoreSumTuple(self, playerSet ):
        statmap = [self.getTotalStat(playerSet, k) for k in self.boxSumStatKeys[playerSet]]
        return tuple(statmap)

    def getTotalRuns(self):
        return sum(self.runsByInning)

    def getTotalHits(self):
        return self.hits

    def getTotalErrors(self):
        return self.errors

class player:
    def __init__(self):
        self.firstName = ""
        self.lastName = "TBD"
        self.fullName = "TBD"
        self.boxName  = "TBD"
        self.PID = 0

class pitcher(player):
    def __init__(self):
        super(pitcher, self).__init__()
        self.stats = {"pitchesThrown":0, "inningsPitched":0, "strikeOuts":0,\
                           "hits":0, "baseOnBalls":0, "runs":0, "homeRuns":0, \
                            "era": 0.0}

    def loadStats(self, json):
        self.fullName = json['person']['fullName']
        self.loadGameStats(json['stats']['pitching'])
        self.loadSeasonStats(json['seasonStats']['pitching'])
        self.loadDerivedStats()

    def loadGameStats(self, jsonData):
        gameStatKeys = ['pitchesThrown', 'inningsPitched', 'strikeOuts',\
                           'hits', 'baseOnBalls', 'runs', 'homeRuns']
        gameStatType = [int, float, int, int, int, int, int]
        for key, keyType in zip(gameStatKeys, gameStatType):
            try:
                self.stats[key] = keyType(jsonData[key])
            except:
                self.stats[key] = keyType(0)

    def loadSeasonStats(self, jsonData):
        seasonStatKeys = ['era']
        seasonStatType = [float]
        for key, keyType in zip(seasonStatKeys, seasonStatType):
            try:
                self.stats[key] = keyType(jsonData[key])
            except:
                self.stats[key] = keyType(0)
        
    def loadDerivedStats(self):
        self.setBoxName()

    def setBoxName(self):
        self.boxName = self.fullName[:23]
        

class batter(player):
    def __init__(self):
        super(batter, self).__init__()
        self.stats = {"atBats":0, "hits":0, "baseOnBalls":0, \
                             "runs" :0, "homeRuns": 0, "strikeOuts": 0, \
                             "hitByPitch" :0, "sacFlies":0, "sacBunts":0, \
                             "plateAppearances": 0,\
                              "obp": 0.0, "slg": 0.0, "ops": 0.0}
        self.position = ""

    def loadStats(self, json):
        self.fullName = json['person']['fullName']
        self.position = json['position']['abbreviation']
        self.loadGameStats(json['stats']['batting'])
        self.loadSeasonStats(json['seasonStats']['batting'])
        self.loadDerivedStats()

    def loadGameStats(self, jsonData):
        gameStatKeys = ["atBats", "hits", "baseOnBalls", "runs", "homeRuns",\
                         "strikeOuts", "hitByPitch", "sacFlies", "sacBunts"]
        gameStatType = [int, int, int, int, int, int, int, int, int]
        for key, keyType in zip(gameStatKeys, gameStatType):
            try:
                self.stats[key] = keyType(jsonData[key])
            except:
                self.stats[key] = keyType(0)

    def loadSeasonStats(self, jsonData):
        seasonStatKeys = ['obp', 'slg']
        seasonStatType = [float, float]
        for key, keyType in zip(seasonStatKeys, seasonStatType):
            try:
                self.stats[key] = keyType(jsonData[key])
            except:
                self.stats[key] = keyType(0)
        
    def loadDerivedStats(self):
        self.setBoxName()
        self.setOPS()
        self.setPlateAppearances()

    def setBoxName(self):
        self.boxName = self.getPositionNameString()[:23]
        
    def setOPS(self):
        self.stats['ops'] = self.stats['obp'] + self.stats['slg']

    def setPlateAppearances(self):
        plateAppearanceKeys = ['atBats', 'baseOnBalls', 'hitByPitch',\
                                'sacFlies', 'sacBunts']
        totalPlateAppearances = sum([self.stats[k] for k in plateAppearanceKeys])
        self.stats['plateAppearances'] = totalPlateAppearances

    def getPositionNameString(self):
        return "%2s %s" % (self.position, self.fullName)


    
class standings:
    def __init__(self):
        self.divisionOrder = \
         [u'American League East', u'American League Central',u'American League West',\
          u'National League East',  u'National League Central', u'National League West']
        self.divisions = {}

        #Set up some arrays in a dictionary for team data
        for k in self.divisionOrder:
            self.divisions[k] = []
        self.loadStandings()
        
        self.divisionHeaderString = "%-24s    W    L       %%   GB WCGB   L10 Strk\n" 
        self.divisionFooterString = "\n" 

        self.standingsHeaderString = "\n" 
        self.standingsFooterString = "" 
        
    def loadStandings(self):
        jsonData = self.tryToGetJSON()
        for divData in jsonData:
            self.loadDivisionData(divData)
        return 
        
    def tryToGetJSON(self):
        now = datetime.datetime.now()
        standings_uri = base_standings_uri % (now.strftime("%Y"))
        standingsData = self.getRecordsFromURI(standings_uri)
        return standingsData

    def getRecordsFromURI(self, uri):
        standingsjson = ''
        if USE_CERTIFI:
            standingsjson = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where()).request('GET', uri)
        else:
            standingsjson = urllib3.PoolManager().request('GET', uri)

        standingsRecords = json.loads(standingsjson.data)["records"]
        return standingsRecords

    def loadDivisionData(self, divisionData):
        divisionKey = divisionData['division']['name']
        if divisionData['standingsType'] == "regularSeason":
            for teamJSONData in divisionData["teamRecords"]:
                aTeam = self.loadTeamData(teamJSONData) 
                self.divisions[divisionKey].append(aTeam)

    def loadTeamData(self, teamData):
        thisTeam = seasonTeam()
        try:
            thisTeam.name         = teamData['team']['name']
        except:
            thisTeam.name         = 'fail'

        try:
            thisTeam.wins         = int(teamData['wins'])
        except:
            thisTeam.wins  = 0

        try:
            thisTeam.losses       = int(teamData['losses'])
        except:
            thisTeam.losses = 0

        try:
            thisTeam.gb = teamData['gamesBack']
        except:
            thisTeam.gb = '-'

        try:
            thisTeam.wcgb = teamData['wildCardGamesBack']
        except:
            thisTeam.wcgb = '-'

        try:
            thisTeam.last10wins   = int(teamData['records']['splitRecords'][4]['wins'])
        except:
            thisTeam.last10wins   = 0

        try:
            thisTeam.last10losses = int(teamData['records']['splitRecords'][4]['losses'])
        except:
            thisTeam.last10losses = 0

        try:
            thisTeam.winningPercentage = float(teamData['winningPercentage'])
        except:
            thisTeam.winningPercentage = 0.0

        try:
            thisTeam.streakCode = teamData['streak']['streakCode']
        except:
            thisTeam.streakCode = '-'

        return thisTeam

    def printStandings(self):
        self.printStandingsHeader()
        for divisionKey in self.divisionOrder:
            self.printDivision(divisionKey)
        self.printStandingsFooter()

    def printStandingsHeader(self):
        sys.stdout.write(self.standingsHeaderString)

    def printDivision(self, divisionKey):
        self.printDivisionHeader(divisionKey)
        for team in self.divisions[divisionKey]:
            team.printStanding()
        self.printDivisionFooter()
    
    def printDivisionHeader(self, divisionKey):
        sys.stdout.write(self.divisionHeaderString % divisionKey)

    def printDivisionFooter(self):
        sys.stdout.write(self.divisionFooterString)

    def printStandingsFooter(self):
        sys.stdout.write(self.standingsFooterString)
   
    
    
        
class seasonTeam:
    def __init__(self):
        self.name = ""
        self.pct = 0.0
        self.streakCode = "-"
        self.wins = 0
        self.losses = 0
        self.last10wins = 0
        self.last10losses = 0
        self.gb = '-'
        self.wcgb = '-'
        self.winningPercentage = 0.0

        self.standingFormatString = "%-24s %4d %4d   %5.3f %4s %4s %2d-%2d %4s\n"
        
    def printStanding(self):

        standingVals = self.formStandingTuple()
        sys.stdout.write(self.standingFormatString % standingVals)
    def formStandingTuple(self):
        standingTuple = (self.name,  self.wins, self.losses,  self.winningPercentage, \
                         self.gb, self.wcgb,\
                         self.last10wins, self.last10losses, self.streakCode )
        return standingTuple

class JSONloader():
    def __init__(self, uri):
        self.uri = uri

    def loadJSON(self):
        if USE_CERTIFI:
            jsondata = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where()).request('GET', self.uri)
        else:
            jsondata = urllib3.PoolManager().request('GET', self.uri)
        try:
            readdata = json.loads(jsondata.data)
        except:
            raise URIException("Could not load ", self.uri)
            readdata = {}
        return readdata


class URIException( BaseException ):
    def __init__(self, value):
        self.value = value
        
def getExplicitTeams(passedTeams):
    explicitTeams = []
    if len(passedTeams) > 0:
        explicitTeams = [x.upper() for x in passedTeams]
    return explicitTeams

def configureArgParser():
    argparser = argparse.ArgumentParser(prog="mlbscores", description="MLB scores utility")

    #FIXME add in option for arbitrary day offset and specific dates?
    argparser.add_argument("-b",  action="store_true",  dest="boxscore",  help="Show boxscore output for best games")
    argparser.add_argument("-f",  action="store_true",  dest="full",      help="Show full output for all games")
    argparser.add_argument("-s",  action="store_true",  dest="standings", help="Show current standings")
    argparser.add_argument("teams", help="Show explicit teams only specified by space separated list of case insensitive abbreviated names  e.g. chc coL SF", nargs="*")
    argtgroup = argparser.add_mutually_exclusive_group()
    argtgroup.add_argument("-y",  action="store_const", dest="dayoffset", const=-1, help="Show for yesterday")
    argtgroup.add_argument("-t",  action="store_const", dest="dayoffset", const= 1, help="Show for tomorrow")
    argtgroup.add_argument("-tt", action="store_const", dest="dayoffset", const= 2, help="Show for two days from now")
    
    return argparser

def main(argv):
    global bestteams

    args = configureArgParser().parse_args()

    explicitTeams = getExplicitTeams(args.teams)
    
    if args.standings:
        theseStandings = standings()
        theseStandings.printStandings()
    else:
        thisGameDay = gameDay(args.dayoffset)
        thisGameDay.printGameDay(args.boxscore, explicitTeams)
    
if __name__ == "__main__":
    main(sys.argv)
