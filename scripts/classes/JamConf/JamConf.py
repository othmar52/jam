#!/bin/env python3
import datetime
import secrets
import sys
import re
from pathlib import Path
from configparser import NoOptionError
from configparser import NoSectionError
#from ..helpers.Filesystem import *

from .JamConfBase import JamConfBase
from ..JamSession import JamSession
from ..Track import Track
from ..Stem import Stem
from ..TracktitleGenerator import TracktitleGenerator
from ...helpers.Strings import az09
from ...helpers.Strings import uniqueOrSuffix
from ...helpers.Strings import sortByCustomOrdering
from ...helpers.Strings import nextLetter
from ...helpers.Strings import replaceCommonPlaceholders
from ...helpers.AudioProcessing import readAudioProperty

'''
    all the stuff the user wants to be created
'''
class Basket():
    def __init__(self):
        self.album = False
        self.stem = False
        self.webstem = False
        self.cuemix = False

class JamConf(JamConfBase):
    def __init__(self):
        JamConfBase.__init__(self)

        self.basket = Basket()
        self.jamSession = JamSession()

        self.trackMergeRequired = False
        self.normalizeStemSplits = False
        self.normalizeTrackMergeRequired = False

        self.cuemix = None
        self.cuemixNormalized = None
        self.cuesheet = None

        self.usedTracktitlesFile = None
        # TODO persist session counter in file
        self.lastSessionCounterFile = None

        self.totalDuration = 0

        self.images = []
        self.videos = []

        self.generator = None

        # required for webstem and others... 
        self.allMusicianShorties = {}


    def collectDataAndValidate(self):
        print('collecting data...')
        self.collectAllFiles()
        self.audioFilesInInputDirOrExit()
        self.targetDirOrExit()
        self.ensureBandName()
        self.ensureSessionCounter()
        self.ensureSessionDate()
        self.allMusicianShorties = self.getAllMusicianShorties()
        self.generator = TracktitleGenerator(
            self.cnf.get('tracktitles', 'prefixes'),
            self.cnf.get('tracktitles', 'suffixes'),
            replaceCommonPlaceholders(
                self.cnf.get('general', 'usedTrackTitlesFile'),
                self
            )
        )
        self.buildTracksAndStems()

    def confirmAndRun(self):
        print(self.jamSession.printForConfirmation())
        choice = input(f'press r for new random tracknames\npress 0-n for single trackname randomizer\npress return to start processing')
        if choice.isnumeric():
            self.otherRandomTitleForTrackNumber(int(choice))
            return self.confirmAndRun()
        if choice == 'r':
            self.otherRandomTitleForTrackNumber()
            return self.confirmAndRun()

        if choice != '':
            print('exiting...')
            sys.exit()

        self.processTracks()

    def ensureBandName(self):
        if self.cnf.get('general', 'bandname') != '':
            self.jamSession.bandName = self.cnf.get('general', 'bandname')
            return

        choice = input('bandname required. consider to add it to your config')
        if choice.strip() != '':
            self.jamSession.bandName = choice.strip()
            return
        return self.ensureBandName()

    def ensureSessionCounter(self):
        # TODO read fallback counter by increment last counter from previous session
        # parse counter and add padded zeroes in case it starts with a number
        # example inputs "4" "0004" "000005.2" "5 part 2" "Custom Session Counter #66"
        if self.cnf.get('general', 'sessionCounter') != '':
            self.jamSession.setCounter(
                self.cnf.get('general', 'sessionCounter'),
                self.cnf.get('general', 'counterPadding')
            )
            return

        choice = input('session counter required')
        if choice.strip() != '':
            self.jamSession.setCounter(
                choice.strip(),
                self.cnf.get('general', 'counterPadding')
            )
            return
        return self.ensureSessionCounter()


    def ensureSessionDate(self):
        dateString = self.cnf.get('general', 'sessionDate', fallback=str(datetime.datetime.now().year))
        if dateString != '':
            self.jamSession.setDate(dateString)
            return

        choice = input('date required (YYYY.MM.DD) or (YYYY.MM) or (YYYY)')
        if choice.strip() != '':
            self.jamSession.setDate(choice)

    def getAllMusicianShorties(self):
        unique = {}
        for key,val in self.cnf.items("musicians"):
            shorty = key.split('.')
            # guest is fallback whichs wildcard maches all
            # we have to make shure its at the very end of the list...
            if shorty[0] == 'guests':
                continue
            unique[shorty[0]] = shorty[0]

        unique['guests'] = 'guests'
        return unique


    '''
        we assume that files already went through the preprocess step
        *) no need to check for dir-name duplicates because we already have a 2-level hierarchy
        *) silence check already done - so its not possible to get a gap within tracknumbers due to 100% silence track deletion
    '''
    def buildTracksAndStems(self):
        tracks = {}
        trackNumber = 1
        trackLetter = 'A'
        for audioFile in self.audioFiles:
            uniqueKey = audioFile.parent.stem
            if not uniqueKey in tracks:
                track = Track()
                track.dirName = uniqueKey
                track.trackLetter = trackLetter
                track.trackNumber = trackNumber
                track.trackNumberPaddedZero = ("%02d" ) % trackNumber
                track.trackTitle = self.getTrackTitle(uniqueKey)
                track.genre = self.getTrackGenre(uniqueKey)
                track.bpm = self.getTrackBpm(uniqueKey)
                tracks[uniqueKey] = track
                trackNumber += 1
                trackLetter = nextLetter(trackLetter)

            stem = Stem(audioFile)
            stem.applyConfigStuff(self)
            stem.duration = readAudioProperty(stem.path, 'duration')

            tracks[uniqueKey].duration = stem.duration
            tracks[uniqueKey].stems.append(stem)

        self.jamSession.tracks = tracks
        self.ensureUniqueStemNames()

    '''
    in case we choosed random colors we have to ensure that the picked random color
    is the same in all tracks
    '''
    def addMissingColorsToInputFiles(self):
        allColors = self.cnf.get('webstem.gui', 'colors').split()
        availableColors = allColors[:]

        for inputFile in self.jamSession.inputFiles:
            if inputFile.color != '' and inputFile.color in availableColors:
                availableColors.remove(inputFile.color)
        
        for i,inputFile in enumerate(self.jamSession.inputFiles):
            if inputFile.color != '':
                continue
            if len(availableColors) == 0:
                availableColors = allColors[:]
            randomColor = secrets.choice(availableColors)
            self.jamSession.inputFiles[i].color = randomColor
            availableColors.remove(randomColor)

    def otherRandomTitleForTrackNumber(self, trackIndex = None):
        for key, track in self.jamSession.tracks.items():
            if not trackIndex or track.trackNumber == trackIndex:
                track.trackTitle = self.getTrackTitle(track.dirName)


    def getTrackTitle(self, dirName):
        try:
            # priority 1: persisted tracktitle in config
            persistedTrackName = self.cnf.get(f'track.{dirName}', 'title')
            if persistedTrackName != '':
                return persistedTrackName
        except (NoSectionError, NoOptionError) as e:
            if self.cnf.get('general', 'useTrackTitleGenerator') == '1':
                return self.generator.getRandomTrackName()

        return dirName

    def getTrackBpm(self, dirName):
        try:
            # check if we already have persisted bpm - so we can skip bpm detection
            persistedBpm = self.cnf.get(f'track.{dirName}', 'bpm')
            if persistedBpm != '':
                return persistedBpm
        except (NoSectionError, NoOptionError) as e:
            return ''

        return ''

    def getTrackGenre(self, dirName):
        try:
            # check if we already have a persisted genre for this track
            persistedGenre = self.cnf.get(f'track.{dirName}', 'genre')
            if persistedGenre != '':
                return persistedGenre
        except (NoSectionError, NoOptionError) as e:
            pass

        return self.cnf.get('general', 'genre')


    def processTracks(self):
        self.jamSession.runProcessing(self)

    def ensureUniqueStemNames(self):
        for key, track in self.jamSession.tracks.items():
            usedStemNames = []
            for stem in track.stems:
                # append number suffix in case stem name is already used within this track
                stem.uniqueStemName = uniqueOrSuffix(stem.uniqueStemName, usedStemNames)
                usedStemNames.append(stem.uniqueStemName)
