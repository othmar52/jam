#!/bin/env python3
from __future__ import print_function
import sys



import re
import os
from shutil import copyfile, rmtree
import glob
import hashlib
import concurrent.futures


from ..TrackUi24r import *
from ...helpers.Strings import uniqueOrSuffix
from ...helpers.Filesystem import ensureExistingEmptyDirectory
from ...helpers.AudioProcessing import *



class JamConfPreprocessUi24r():

    def __init__(self, pConf):
        self.pConf = pConf
        self.runStereoMergeFor = []

    def buildTracksAndStems(self):
        tracks = {}
        trackDirNames = []
        for audioFile in self.pConf.audioFiles:
            uniqueKey = hashlib.sha224(f'{audioFile.parent}'.encode('utf-8')).hexdigest()
            if not uniqueKey in tracks:
                track = TrackUi24r(audioFile.parent)
                # as we do a recursive directory search we may have dupes of dir name
                track.targetDirName = uniqueOrSuffix(track.absPath.stem, trackDirNames)
                trackDirNames.append(track.targetDirName)
                uiRecSessionFile = Path(f'{audioFile.parent}/.uirecsession')
                if uiRecSessionFile.is_file():
                    track.setUiRecSessionFile(uiRecSessionFile)

                track.attachParamRecordingsFile(
                    self.guessBestParamRecordingsFile(
                        audioFile.parent.stem,
                        self.pConf.paramRecordingFiles
                    )
                )
                tracks[uniqueKey] = track

            tracks[uniqueKey].stems.append( Stem(audioFile.name))


        for key,track in tracks.items():
            tracks[key].requestedApplyParams = self.pConf.preprocess['applyParams']
            tracks[key].requestedPopRemoval = self.pConf.preprocess['popRemoval']
            tracks[key].requestedNoiseMute = self.pConf.preprocess['noiseMute']
            tracks[key].requestedSkipIfSilence = self.pConf.preprocess['skipSilenceFiles']
            tracks[key].requestedMonoToStereo = self.pConf.preprocess['mergeMonoToStereo']
            tracks[key].checkWhatsPossible()

        self.pConf.tracks = tracks



    def processStem(self, trackKey, stemKey):

        track = self.pConf.tracks[trackKey]
        stem = track.stems[stemKey]
        stem.fileToCopy = Path(f'{track.absPath}/{stem.fileName}')

        stemID = f'{track.targetDirName}/{stem.fileName}'

        if track.requestedApplyParams and stem.applyParamsPossible:
            print(f'{stemID} apply params...')
            filterArgFile = Path(f'{self.pConf.targetDir}/tmp-ui24rprocess-filter-{trackKey}-{stemKey}.txt')
            filterArgFile.write_text(',\n'.join(stem.ffmpegFilterArgs))
            targetPath = Path(f'{self.pConf.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKey}-params.flac')
            applyFilter(stem.fileToCopy, filterArgFile, targetPath)
            stem.fileToCopy = targetPath


        if track.requestedPopRemoval:
            # TODO: properly implement configurable filename filter for different operations
            pattern = '.*' + self.pConf.cnf.get('musicians', f'was.pattern') + '.*'
            if re.search(pattern.lower(), stem.fileName.lower()):
                print(f'{stemID} pop removal...')
                targetPath = Path(f'{self.pConf.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKey}-popsremoved.flac')
                removePops(
                    stem.fileToCopy,
                    targetPath
                )
                stem.fileToCopy = targetPath


        if track.requestedNoiseMute:
            print(f'{stemID} detect silence...')
            silencesRaw = detectSilences(
                stem.fileToCopy,
                #'-50dB', # TODO: move to config
                '-60dB', # TODO: move to config
                #'-70dB', # TODO: move to config
                5        # TODO: move to config
            )

            silences = silenceDetectResultToSilenceBoundries(silencesRaw)
            if len(silences) > 0:
                targetPath = Path(f'{self.pConf.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKey}-noisemute.flac')
                print(f'{stemID} apply noise removal...')
                muteNoiseSections(
                    stem.fileToCopy,
                    targetPath,
                    silences
                )
                stem.fileToCopy = targetPath

        if track.requestedSkipIfSilence:
            print(f'{stemID} check if file is silence...')
            duration = readAudioProperty(stem.fileToCopy, 'duration')
            #codec_name = readAudioProperty(stem.fileToCopy, 'codec_name')
            #sample_rate = readAudioProperty(stem.fileToCopy, 'sample_rate')
            if isSilenceFile(stem.fileToCopy, duration - 1):
                #print('track is silence')
                stem.isSilence = True
                stem.fileToCopy = None
                print(f'{stemID} is silence...')
            else:
                print(f'{stemID} is not silence...')

        self.pConf.tracks[trackKey].stems[stemKey] = stem
        if not track.requestedMonoToStereo:
            return stem, trackKey, stemKey, False
        if stem.stereoLinkIndex != 1:
            return stem, trackKey, stemKey, False
        if stem.isSilence == True:
            return stem, trackKey, stemKey, False
        if self.pConf.tracks[trackKey].stems[stemKey-1].isSilence == True:
            return stem, trackKey, stemKey, False

        return stem, trackKey, stemKey, [stemKey-1, stemKey]


    def printForConfirmation(self):
        for key,track in self.pConf.tracks.items():
            print(track.printTaskList())

    def processStemCallback(self, processedStem):
        stem, trackKey, stemKey, skipPrevious = processedStem.result()
        self.processStemCallbackInternal(stem, trackKey, stemKey, skipPrevious)


    def processStemCallbackInternal(self, stem, trackKey, stemKey, runStereoMergeFor):
        self.pConf.tracks[trackKey].stems[stemKey] = stem
        #print('processStemCallbackInternal', skipPrevious)
        if runStereoMergeFor:
            #print('############ disabling prev', self.pConf.tracks[trackKey].stems[stemKey-1].fileToCopy)
            self.pConf.tracks[trackKey].runStereoMergeFor.append(runStereoMergeFor)

    def processStereoMergeCallback(self, processedStereoMerge):
        trackKey, stemKeyLeft, stemKeyRight, mergedAudioPath = processedStereoMerge.result()
        self.processStereoMergeCallbackInternal(trackKey, stemKeyLeft, stemKeyRight, mergedAudioPath)

    def processStereoMergeCallbackInternal(self, trackKey, stemKeyLeft, stemKeyRight, mergedAudioPath):
        self.pConf.tracks[trackKey].stems[stemKeyLeft].fileToCopy = mergedAudioPath
        self.pConf.tracks[trackKey].stems[stemKeyRight].fileToCopy = None


    def executePreProcessing(self):
        tracks = self.pConf.tracks

        maxWorkers = int(self.pConf.cnf.get('general', 'maxWorkers'))

        if maxWorkers <= 1:
            # non parallelized version
            for trackKey,track in tracks.items():
                for stemKey,stem in enumerate(track.stems):
                    stem2, trackKey2, stemKey2, runStereoMergeFor2 = self.processStem(trackKey, stemKey)
                    self.processStemCallbackInternal(
                        stem2, trackKey2, stemKey2, runStereoMergeFor2
                    )
            for trackKey,track in tracks.items():
                for stereoPair in track.runStereoMergeFor:
                    trackKey2, stemKeyLeft2, stemKeyRight2, mergedAudioPath2 = self.runStereoMerge(trackKey, stereoPair[0], stereoPair[1])
                    self.processStereoMergeCallbackInternal(
                        trackKey2, stemKeyLeft2, stemKeyRight2, mergedAudioPath2
                    )
        else:
            # paralellized tryout
            with concurrent.futures.ProcessPoolExecutor(max_workers=maxWorkers) as executor:
                for trackKey,track in tracks.items():
                    for stemKey,stem in enumerate(track.stems):

                        #f = executor.map(processStem, [self, trackKey, stemKey])
                        #processedStem = executor.submit(processStem, (funcArgs))
                        processedStem = executor.submit(self.processStem, trackKey, stemKey)
                        processedStem.add_done_callback(self.processStemCallback)

            with concurrent.futures.ProcessPoolExecutor(max_workers=maxWorkers) as executor:
                for trackKey,track in tracks.items():
                    for stereoPair in track.runStereoMergeFor:

                        #f = executor.map(processStem, [self, trackKey, stemKey])
                        #processedStem = executor.submit(processStem, (funcArgs))
                        processedStereoMerge = executor.submit(self.runStereoMerge, trackKey, stereoPair[0], stereoPair[1])
                        processedStereoMerge.add_done_callback(self.processStereoMergeCallback)

        self.copyProcessedFiles()

    def runStereoMerge(self, trackKey, stemKeyLeft, stemKeyRight):
        # print (trackKey, stemKeyLeft, stemKeyRight)
        print(f'{self.pConf.tracks[trackKey].targetDirName}/{self.pConf.tracks[trackKey].stems[stemKeyLeft].fileName} merge stereo...')
        targetPath = Path(f'{self.pConf.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKeyLeft}-{stemKeyRight}-stereo.flac')
        mergeMonosToStereo(
            self.pConf.tracks[trackKey].stems[stemKeyLeft].fileToCopy,
            self.pConf.tracks[trackKey].stems[stemKeyRight].fileToCopy,
            targetPath
        )
        return trackKey, stemKeyLeft, stemKeyRight, targetPath

    def copyProcessedFiles(self):
        #global self
        for trackKey,track in self.pConf.tracks.items():
            print('copying processed files', track.targetDirName)

            trackTargetPath = Path(f'{self.pConf.targetDir}/{track.targetDirName}')
            
            ensureExistingEmptyDirectory(trackTargetPath)

            anyStemCopied = False
            for stemKey,stem in enumerate(track.stems):
                if stem.fileToCopy == None:
                    print('skipping', stem.fileName, str(stem.fileToCopy))
                    continue

                if stem.fileToCopy.name == stem.fileName:
                    #print(' copy original', stem.fileName)
                    copyfile(str(stem.fileToCopy), str(Path(f'{trackTargetPath}/{stem.fileName}')))
                else: 
                    #print(' move tempfile', stem.fileName)
                    os.rename(str(stem.fileToCopy), str(Path(f'{trackTargetPath}/{stem.fileName}')))

                anyStemCopied = True

            if anyStemCopied == False:
                print(' all stems are silences. this track will not end up in the output dir...')
                rmtree(trackTargetPath)

        print('deleting temp files')
        tmpFiles = glob.glob(f'{self.pConf.targetDir}/tmp-ui24rprocess*')
        for filePath in tmpFiles:
            try:
                os.remove(filePath)
            except:
                print("Error while deleting file : ", filePath)



        #print(audioFiles)
        #print(paramRecordingsFiles)
        # lets search for audiofiles in inputDir
        print('done')


    def guessBestParamRecordingsFile(self, sessionName, allParamRecordingFiles):

        if len(allParamRecordingFiles) == 0:
            return None

        possibleMatches = []
        for paramRecFile in allParamRecordingFiles:
            if re.search(f'-recsession-{sessionName}.uiparamrecording.txt', paramRecFile.name):
                possibleMatches.append(paramRecFile)
                continue

        if len(possibleMatches) == 0:
            return None

        if len(possibleMatches) == 1:
            # nothing to guess. its very likely that we found the matching param recording
            return possibleMatches.pop()

        # TODO: theoretically we can have multiple paramRecordings with this key as its a number between 0000 and 9999
        #   we are able to compare fileName with "i.<index>.name" and/or audio file duration with paramRecording duration
        #   probably the very last file is the latest and most relevant file?

        # for now give a shit on this edge case and return the last found file
        possibleMatches.sort()
        return possibleMatches.pop()