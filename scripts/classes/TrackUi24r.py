#!/bin/env python3
# TODO extend Track instead of having TrackUi24r as a separate class
# refactoring this ugly piece of shit


import json
import re
from pathlib import Path

from ..helpers.Filesystem import *
from colorclass import Color, Windows
from terminaltables import SingleTable

class Param(object):
    def __init__(self, paramList):
        self.time = float(paramList[0])
        self.name = str(paramList[1])
        self.value = paramList[2]

class Stem:
    def __init__(self, fileName):
        self.fileName = fileName
        self.isSilence = False
        self.channelIndex = False
        self.applyParamsPossible = False
        self.monoToStereoPossible = False
        self.stereoLinkIndex = -1
        self.ffmpegFilterArgs = []

        self.fileToCopy = None

class TrackUi24r:
    def __init__(self, parentDir):
        self.title = ''
        self.absPath = parentDir
        self.targetDirName = None
        self.stems = []
        self.uiRecsessionFile = None
        self.uiRecsessionJson = None
        self.paramRecordingsFile = None
        self.recordedParams = []

        self.requestedApplyParams = False
        self.requestedPopRemoval = False
        self.requestedNoiseMute = False
        self.requestedSkipIfSilence = False
        self.requestedMonoToStereo = False

        self.runStereoMergeFor = []

    def setUiRecSessionFile(self, filePath):
        self.uiRecsessionFile = filePath
        try:
            self.uiRecsessionJson = json.loads(getFileContent( str(filePath) ) )
        except json.decoder.JSONDecodeError:
            self.uiRecsessionFile = None
            self.uiRecsessionJson = None

    def attachParamRecordingsFile(self, filePath):
        if filePath == None:
            return

        self.paramRecordingsFile = filePath
        self.recordedParams = getFileContent(str(filePath)).split('\n')

    def checkWhatsPossible(self):
        if self.uiRecsessionJson == None:
            return

        for key,stem in enumerate(self.stems):
            self.stems[key].channelIndex = self.findInputChannelIndex(stem.fileName)
            if self.stems[key].channelIndex < 0:
                continue

            self.stems[key].ffmpegFilterArgs = self.getFFmpegFilterArgsForIndex(self.stems[key].channelIndex)
            if len(self.stems[key].ffmpegFilterArgs) > 0:
                self.stems[key].applyParamsPossible = True
            self.stems[key].stereoLinkIndex = self.getStereoIndexValue(self.stems[key].channelIndex)


        # check if stereo merge is possible
        previousChannelIndex = -1
        for key,stem in enumerate(self.stems):
            if key == 0:
                # we havn't processed mergeable files yet but we need a pair of channels
                previousChannelIndex = stem.stereoLinkIndex
                continue
            if stem.stereoLinkIndex == -1 or previousChannelIndex == -1:
                # stereoLink wasn't enabled during recording
                previousChannelIndex = stem.stereoLinkIndex
                continue

            if stem.stereoLinkIndex - previousChannelIndex != 1:
                # Ui24R can only activate stereoLink on channels next to each other
                previousChannelIndex = stem.stereoLinkIndex
                continue

            self.stems[key].monoToStereoPossible = True
            self.stems[key-1].monoToStereoPossible = True
            # this iteration is not allowed to be previous in next iteration
            previousChannelIndex = -1



    def checkMergeMonoToStereo(self, channelIndex, previousChannelIndex):

        if previousChannelIndex == -1:
            # we havn't processed mergeable files yet
            return False

        if channelIndex - previousChannelIndex != 1:
            # Ui24R can only activate stereoLink on channels next to each other
            return

        if not stereoLinkEnabled(previousChannelIndex, channelIndex):
            # stereoLink settings has not been enabled during param recording
            return 


    def findInputChannelIndex(self, stemFileName):
        for key, channelString in enumerate(self.uiRecsessionJson['mapping']):
            audioFileName = self.uiRecsessionJson["files"][key] + self.uiRecsessionJson["ext"]
            if audioFileName == stemFileName:
                return int(re.sub("[^0-9]", "", channelString))

        return False

    def getStereoIndexValue(self, channelIndex):
        if len(self.recordedParams) == 0:
            return -1

        paramNameWhitelist = [
            f'i.{channelIndex}.stereoIndex'
        ]
        for paramLine in self.recordedParams:
            paramList = paramLine.split(' ' ,2)
            if len(paramList) != 3 or paramList[1] not in paramNameWhitelist:
                continue
            return int(float(str(paramList[2]))) # WTF!!!

        return -1

    def getFFmpegFilterArgsForIndex(self, channelIndex):
        filteredParams = self.grabVolumeParametersForInput(channelIndex)
        if len(filteredParams) == 0:
            return []

        return self.convertVolumeParamsToFilterArguments(filteredParams, channelIndex)


    '''
        convertVolumeParamsToFilterArguments()
        based on volume relevant parameters we have to build audio filter settings for ffmpeg
        @param list filteredParams: a list with paramater instances. already filtered for a single input channel
        @param int currentInputIndex: the inputIndex of the current channel
        @return list the list with the actual audio filter syntax for ffmpeg
    '''
    def convertVolumeParamsToFilterArguments(self, filteredParams, currentInputIndex):

        # the list that gets returned by this method
        filterLines = []

        # helper var to maybe ignore volume changes
        currentlyMuted = "0"

        # helper vars to track whats already persisted as a filter argument
        lastPersistedEndtime = 0
        lastPersistedVolume = 0

        # actual volume may gets overriden because of mute
        volumeToCheck = 0
        lastCheckedVolume = 0

        # after unmuting we have to apply the last tracked volume again
        lastTrackedVolume = 0

        # loop over all params and apply the volume value as soon as it changes
        for param in filteredParams:

            if param.name == f'i.{currentInputIndex}.mix':
                volumeToCheck = param.value
                lastTrackedVolume = param.value

            if param.name == f'i.{currentInputIndex}.mute':
                currentlyMuted = param.value
                if param.value == '0':
                    volumeToCheck = lastTrackedVolume

            if currentlyMuted == '1':
                volumeToCheck = 0

            if lastPersistedVolume != volumeToCheck and param.time > 0:
                filterLines.append(
                    self.volumeFilterLine(
                        lastPersistedEndtime,
                        param.time,
                        self.convertVolumeValue(lastCheckedVolume)
                    )
                )
                lastPersistedEndtime = param.time
                lastPersistedVolume = volumeToCheck

            lastCheckedVolume = volumeToCheck

        # apply the very last line until end position of the audio file.
        filterLines.append(
            self.volumeFilterLine(
                lastPersistedEndtime,
                self.getEndPosition(),
                self.convertVolumeValue(lastCheckedVolume)
            )
        )
        return filterLines

    def volumeFilterLine(self, start, end, volValue):
        return re.sub(
            '\s+',
            '',
            f'''volume=enable='between(t, {start}, {end})':volume='{volValue}':eval=frame'''
        )

    '''
        getEndPosition()
        WARNING: current return value is FAKE
        @see comments of the 3 possibilities

        possibility 1: read duration from input file via ffprobe
          duration = detectDuration(inputFile)

        possibility 2: read duration from json created by Ui24R
          duration = parse file .uirecsession for key "lengthSeconds"

        possibility 3: return a very high number
          as an out-of-range value seems to be no problem for ffmpeg go with this fastest approach
          hopefully 100000 seconds is higher than the actual length of the audio file
    '''
    def getEndPosition(self):
        return 100000

    '''
        filterParamsForInput()
        pick only the params that are relevant for the single audio file to process
        defined by the index of the input
        currently only "i.<inputIndex>.mix" and "i.<inputIndex>.mute" gets processed
        @TODO: we should also take a look onto "i.<all-other-inputs>.solo" because this will cause silence for this track as well
        @param int inputIndex the index of the audio input [0-22]
        @return list a list of Parameter instances
    '''
    def grabVolumeParametersForInput(self, channelIndex):
        paramsForInput = []

        # define all params that affects our audio processing for this single input
        paramNameWhitelist = [
            f'i.{channelIndex}.mix',
            f'i.{channelIndex}.mute'
        ]
        for paramLine in self.recordedParams:
            paramList = paramLine.split(' ' ,2)
            if len(paramList) != 3 or paramList[1] not in paramNameWhitelist:
                continue
            paramsForInput.append(Param(paramList))
        return paramsForInput


    '''
        @TODO check if we have to tweak the value (between 0.0 and 1.0) provided by the Ui24R for ffmpeg's volume filter
        @see https://ffmpeg.org/ffmpeg-filters.html#volume
        based on some analysis and measurings https://mycurvefit.com came to this formula
        y = 1932499 + (0.2518983 − 1932499)/(1 + (x/13.36283)^5.177893)
        measurings
        ---------------------------------------------------------------------
        fader value (x)     |  value of ffmpeg's volume filter to apply (y)
        ---------------------------------------------------------------------
        1                    | 3.181
        0.9566074950690335   | 2.461
        0.897435897435897    | 1.815
        0.857988165680473    | 1.535
        0.808678500986193    | 1.22
        0.7647058823529421   | 1
        0.7120315581854044   | 0.8
        0.6469428007889547   | 0.597
        0.5877712031558187   | 0.441
        0.5069033530571994   | 0.254
        0.4240631163708088   | 0.158
        0.345167652859960    | 0.078
        0.22879684418145974  | 0.02
        0.12031558185404356  | 0
        0.061143984220907464 | 0
        ---------------------------------------------------------------------
    '''
    def convertVolumeValue(self, inputValue):
        return 1932499 + (0.2518983-1932499)/(1 + (float(inputValue)/13.36283)**5.177893)
        #zeroDB = .7647058823529421
        #newValue = float(inputValue) * ( 1/zeroDB)
        #return newValue
        #return math.log1p(float(inputValue))


    def printTaskList(self):
        tableData = [
            [
                Color('{autoyellow} TRACK: ' + self.targetDirName + ' {/autoyellow}'),
                'apply params',
                'pop removal',
                'noisemute',
                'skip if silence',
                'mono2stereo',
                'outputfile'
            ]
        ]

        ok = Color('{autogreen}✔{/autogreen}')
        cant = Color('{autored}NOT POSSIBLE{/autored}')
        disabled = Color('{autoblack}disabled{/autoblack}')

        for key,stem in enumerate(self.stems):
            tableRow = [stem.fileName]
            tableRow.append(
                (ok if stem.applyParamsPossible else cant) if self.requestedApplyParams else disabled
            )
            tableRow.append(ok if self.requestedPopRemoval else disabled)
            tableRow.append(ok if self.requestedNoiseMute else disabled)
            tableRow.append(ok if self.requestedSkipIfSilence else disabled)
            tableRow.append(
                (ok if stem.monoToStereoPossible else cant) if self.requestedMonoToStereo else disabled
            )

            tPath = f'{self.targetDirName}/{stem.fileName}'
            if stem.stereoLinkIndex == 1 and self.requestedMonoToStereo:
                tableRow.append(Color('{autoblack}' + tPath + ' *{/autoblack}'))
            else:
                tableRow.append(f'{tPath}')
            
            tableData.append(tableRow)

        table_instance = SingleTable(tableData)

        table_instance.inner_heading_row_border = True
        table_instance.inner_row_border = False
        table_instance.justify_columns = {1: 'center', 2: 'center', 3: 'center', 4: 'center'}


        return table_instance.table
