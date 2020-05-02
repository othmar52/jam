#!/bin/env python3

import os
import logging
from configparser import NoOptionError
from ...helpers.Strings import replaceCommonPlaceholders
import sys
from pathlib import Path

class JamConfBase:
    def __init__(self):
        self.cnf = None
        self.action = ''
        # required for all actions
        self.rootDir = Path(f'{os.path.dirname(os.path.abspath(__file__))}/../../..')
        self.inputDir = None
        self.targetDir = None
        self.tempDir = None
        self.maxWorkers = 1

        self.audioFiles = []
        self.imageFiles = []
        self.videoFiles = []
        self.recorderMetaFiles = []
        self.paramRecordingFiles = []
        self.otherFiles = []

    def collectDataAndValidate(self):
        print('JamConfBase::collectDataAndValidate() should never be called. override method in inherited class...')

    def confirmAndRun(self):
        print('JamConfBase::confirmAndRun() should never be called. override method in inherited class...')

    def audioFilesInInputDirOrExit(self):
        if len(self.audioFiles) > 0:
            return
        fileExt = self.cnf.get('fileext', 'audio')
        logging.critical(
            f'no audiofiles [{fileExt}] found in inputdir "{self.inputDir}".\nexiting now...'
        )
        sys.exit()

    def targetDirOrExit(self):
        if self.targetDir == None:
            # no arg given
            try:
                # try to read target dir from config
                targetDirFromConfig = self.cnf.get('general', 'targetDir')
            except NoOptionError:
                targetDirFromConfig = ''

            if targetDirFromConfig == '':
                logging.critical(
                    'targetdir neither configured nor provided as arg --targetdir\nexiting now...'
                )
                sys.exit()

            self.targetDir = Path(replaceCommonPlaceholders(targetDirFromConfig, self))

        if self.targetDir.is_dir():
            return

        choice = input(f'targetdir "{self.targetDir}" does not exist. create it? [Y,n]')
        if choice.lower() == 'y' or choice == '':
            self.targetDir.mkdir(parents=True, exist_ok=True)

        if self.targetDir.is_dir():
            return

        logging.critical(f'cant do anything without targetdir.\nexiting now...')
        sys.exit()

    def ensureConfigFor(self, confSection, confKey, message):
        if self.cnf.get(confSection, confKey) == '0':
            return

        if self.cnf.get(confSection, confKey) == '1':
            self.preprocess[confKey] = True
            return

        choice = input(message)
        if choice.lower() == 'y' or choice == '':
            self.preprocess[confKey] = True


    def collectAllFiles(self):
        allFiles = sorted(self.inputDir.rglob('*.*'))
        remainingFiles = self.assignAudioFiles(allFiles)
        remainingFiles = self.assignImageFiles(remainingFiles)
        remainingFiles = self.assignVideoFiles(remainingFiles)
        remainingFiles = self.assignRecorderMetaFiles(remainingFiles)
        remainingFiles = self.assignParamRecorderFiles(remainingFiles)
        self.otherFiles += [remainingFiles]

    def findFilesOfType(self, filesToSort, fileType):
        extList = ['.' + x.strip() for x in self.cnf.get('fileext', fileType).lower().split(',')]
        remainingFiles = []
        matchingFiles = []
        for foundFile in filesToSort:
            if foundFile.suffix.lower() in extList:
                matchingFiles += [ foundFile ]
                continue
            remainingFiles += [ foundFile ]
        return matchingFiles, remainingFiles

    def assignAudioFiles(self, filesToSort):
        matchingFiles, remainingFiles = self.findFilesOfType(filesToSort, 'audio')
        self.audioFiles = matchingFiles
        return remainingFiles

    def assignImageFiles(self, filesToSort):
        matchingFiles, remainingFiles = self.findFilesOfType(filesToSort, 'image')
        self.imageFiles = matchingFiles
        return remainingFiles

    def assignVideoFiles(self, filesToSort):
        matchingFiles, remainingFiles = self.findFilesOfType(filesToSort, 'video')
        self.videoFiles = matchingFiles
        return remainingFiles

    def assignRecorderMetaFiles(self, remainingFiles):

        validRecTypes = [
            x.strip() for x in self.cnf.get('preprocess', 'supportedSchemes').split(',')
        ]
        for recType in validRecTypes:
            remainingFiles = self.assignRecorderMetaFilesInternal(
                remainingFiles,
                recType,
                self.cnf.get(f'preprocess.{recType}', 'recMetaFile')
            )
        return remainingFiles

    def assignRecorderMetaFilesInternal(self, filesToSort, recType, pattern):
        remainingFiles = []
        for foundFile in filesToSort:
            if foundFile.name.find(pattern) > -1:
                self.recorderMetaFiles += [foundFile]
                continue
            remainingFiles += [ foundFile ]
        return remainingFiles

    def assignParamRecorderFiles(self, filesToSort):
        remainingFiles = []
        for foundFile in filesToSort:
            if foundFile.name.find(self.cnf.get('preprocess.ui24r', 'paramRecording')) > -1:
                self.paramRecordingFiles += [foundFile]
                continue
            remainingFiles += [ foundFile ]
        return remainingFiles
