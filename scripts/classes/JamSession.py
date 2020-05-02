#!/bin/env python3

import glob
import os
import re
import datetime
import configparser
from pathlib import Path
from ..helpers.Strings import secondsToMinutes
from ..helpers.Strings import replaceCommonPlaceholders
from ..helpers.Strings import formatSecondsForCueSheet
from ..helpers.Filesystem import ensureExistingEmptyDirectory
from ..helpers.AudioProcessing import *
from .Webstem import Webstem
from colorclass import Color, Windows
from terminaltables import SingleTable, DoubleTable

class JamSession():
    def __init__(self):
        self.counter = None
        self.paddedCounter = ''
        self.dateString = ''
        self.day = '??'
        self.month = '???'
        self.year = '????'
        self.dirName = ''
        self.bandName = ''
        self.uniqueSortedShorties = []
        self.inputFiles = []
        self.tracks = {}
        self.duration = 0
        self.webstem = {
            'targetDir': None,
            'tracklistJsFile': None
        }

        self.tmpFileCueMix = None

    def setCounter(self, rawCounterInput, counterPadding):
        if rawCounterInput.isnumeric():
            self.counter = str(int(rawCounterInput))
            self.paddedCounter = ('%0' + counterPadding + 'd') % int(self.counter)
            return

        self.counter = rawCounterInput
        self.paddedCounter = rawCounterInput
        # lets see if the first captured group is numeric
        match = re.match('^([0-9]{1,20})([^0-9]{1,})(.*)$', rawCounterInput)
        if match:
            trailingNumbers = match.group(1)
            self.counter = str(int(trailingNumbers)) + match.group(2) + match.group(3)
            self.paddedCounter = ('%0' + counterPadding + 'd')%int(trailingNumbers) + match.group(2) + match.group(3)


    def setDate(self, dateString):
        self.dateString = dateString
        pattern = "(\d{4})\.?(\d{1,2})?\.?(\d{1,2})?"
        match = re.match( pattern, dateString)
        if match:
            self.day = ("%02d" )%int(match.group(3)) if match.group(3) else '??'
            self.month = datetime.date(1900, int(match.group(2)), 1).strftime('%b') if match.group(2)  else '???'
            self.year = match.group(1) if match.group(1)  else '????'

    
    def runProcessing(self, jamConf):
        self.runProcessingStage1(jamConf)
        self.runProcessingAlbum(jamConf)
        self.runProcessingStem(jamConf)
        self.runProcessingWebstem(jamConf)
        self.runProcessingCuemix(jamConf)
        self.persistTracknamesInInputDir(jamConf)
        self.deleteTempFiles(jamConf)

    '''
        do all the processing that leads to the acoustic content for all needed files
        in all possible result scenarios (but don't care about desired output format)
    '''
    def runProcessingStage1(self, jamConf):
        usedTrackTitles = []
        for key, track in self.tracks.items():
            track.runProcessing(jamConf)
            usedTrackTitles.append(track.trackTitle)

        trackPathsToMerge = []
        if jamConf.basket.cuemix == True:
            for key, track in self.tracks.items():
                if jamConf.cnf.get('cuemix', 'normalize') == '1':
                    trackPathsToMerge.append(track.tmpFileMergedStemsNormalized)
                    self.tmpFileCueMix = Path(f'{jamConf.targetDir}/tmp-cuemix-alltracks-normalized.wav')
                else:
                    trackPathsToMerge.append(track.tmpFileMergedStems)
                    self.tmpFileCueMix = Path(f'{jamConf.targetDir}/tmp-cuemix-alltracks.wav')

            print(f'SESSION: concatenating all {len(self.tracks)} single tracks to cuemix')
            concatAudioFiles(trackPathsToMerge, self.tmpFileCueMix)


    def runProcessingAlbum(self, jamConf):
        if jamConf.basket.album == False:
            return
        print('TODO: process album not implemented yet')

    def runProcessingStem(self, jamConf):
        if jamConf.basket.stem == False:
            return
        print('TODO: process stem not implemented yet')

    def runProcessingWebstem(self, jamConf):
        if jamConf.basket.webstem == False:
            return
        ws = Webstem(
            replaceCommonPlaceholders(
                jamConf.cnf.get('webstem', 'templateDir'),
                jamConf
            )
        )
        ws.run(jamConf)
        print('FINISHED action webstem')

    def runProcessingCuemix(self, jamConf):
        if jamConf.basket.cuemix == False:
            return

        dirScheme = jamConf.cnf.get('cuemix', 'dirScheme')
        dirName = replaceCommonPlaceholders(dirScheme, jamConf)
        targetDir = Path(f'{jamConf.targetDir}/{dirName}')
        targetFilenameAudio = f'{dirName}.{jamConf.cnf.get("cuemix", "format")}'
        cueSheetFile = Path(f'{targetDir}/{dirName}.cue')
        ensureExistingEmptyDirectory(targetDir)

        convertAudio(
            self.tmpFileCueMix,
            jamConf.cnf.get('cuemix', 'codec'),
            jamConf.cnf.get('cuemix', 'samplerate'),
            jamConf.cnf.get('cuemix', 'bitrate'),
            f'{targetDir}/{targetFilenameAudio}'
        )

        # *.flac, *.wav, *.aac needs WAVE
        fileTypeForCue = 'WAVE'
        if jamConf.cnf.get('cuemix', 'format').upper() == 'MP3':
            # but *.mp3 needs "MP3"
            fileTypeForCue = 'MP3'

        cueSheetContent = [
            f'PERFORMER "{self.bandName}"',
            f'TITLE "Session #{self.counter}"',
            f'REM DATE "{self.dateString}"',
            f'REM GENRE "{jamConf.cnf.get("general", "genre")}"',
            f'FILE "{targetFilenameAudio}" {fileTypeForCue}'
        ]
        trackStartTime = 0
        for key, track in self.tracks.items():
            cueSheetContent += [
                f'  TRACK {track.trackNumberPaddedZero} AUDIO',
                f'    TITLE "{track.trackTitle}"',
                f'    PERFORMER "{self.bandName}"',
                f'    INDEX 01 {formatSecondsForCueSheet(trackStartTime)}'
            ]
            trackStartTime += track.duration

        cueSheetFile.write_text(
            '\n'.join(cueSheetContent)
        )
        # TODO write metadata/tags
        print('FINISHED action cuemix')
        

    def printForConfirmation(self):
        content = self.printSessionPropsForConfirmation()
        content += '\n'
        content += self.printTracksForConfirmation()
        return content

    def printSessionPropsForConfirmation(self):
        ok = Color('{autogreen}✔{/autogreen}')
        disabled = Color('{autoblack}disabled{/autoblack}')

        tableData = [
            [
                'counter',
                Color('{autoyellow}' + self.counter + '{/autoyellow}'),
                ' ',
                'normalize',
                ok
            ],
            [
                'date',
                Color('{autoyellow}' + self.dateString + '{/autoyellow}'),
                ' ',
                'bpm detect',
                ok
            ]
        ]

        table_instance = DoubleTable(tableData, 'SESSION')
        table_instance.inner_heading_row_border = True
        table_instance.inner_row_border = False
        table_instance.justify_columns = {1: 'center', 2: 'center', 3: 'center', 4: 'center'}

        return table_instance.table


    def printTracksForConfirmation(self):
        tableData = [
            [
                'sourcedir',
                'nr.',
                'title',
                'duration',
                'duration [s]',
                'stemcount',
                'genre',
                'bpm'
            ]
        ]

        for key, track in self.tracks.items():
            tableData.append([
                track.dirName,
                f'{track.trackNumber} ({track.trackLetter})',
                track.trackTitle,
                secondsToMinutes(track.getLongestStemDuration()),
                '{:.1f}'.format(track.getLongestStemDuration()),
                len(track.stems),
                track.genre,
                track.bpm
            ])

        table_instance = SingleTable(tableData, 'TRACKS')

        table_instance.inner_heading_row_border = True
        table_instance.inner_row_border = False
        table_instance.justify_columns = {3: 'center', 4: 'center', 5: 'center'}

        return table_instance.table

    def persistTracknamesInInputDir(self, jamConf):
        configFilePath = Path(f'{jamConf.inputDir}/config.ini')
        if not configFilePath.is_file():
            configFilePath = Path(f'{jamConf.inputDir}/config.txt')

        # preserve possible existing config
        parser = configparser.ConfigParser(strict=False)
        parser.read([f'{configFilePath}'])
        if 'general' not in parser:
            parser['general'] = {}
        parser['general']['sessionCounter'] = self.counter
        parser['general']['sessionDate'] = self.dateString
        for key, track in self.tracks.items():
            trackSection = f'track.{track.dirName}'
            if trackSection not in parser:
                parser[trackSection] = {}
            parser[trackSection]['title'] = track.trackTitle
            if  track.bpm != '' and int(float(track.bpm)) > 0:
                parser[trackSection]['bpm'] = track.bpm

        with open(configFilePath, 'w') as configFile:
            parser.write(configFile)

        

    def deleteTempFiles(self, jamConf):
        print('deleting temp files')
        tmpFiles = glob.glob(f'{jamConf.targetDir}/tmp-*')
        for filePath in tmpFiles:
            try:
                os.remove(filePath)
            except:
                print("Error while deleting file : ", filePath)

        print('done')
