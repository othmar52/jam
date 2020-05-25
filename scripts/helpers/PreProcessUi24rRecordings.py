
from __future__ import print_function
import re
import os
from shutil import copyfile, rmtree
import glob
import hashlib
import concurrent.futures


from ..classes.TrackUi24r import *
from ..helpers.Strings import uniqueOrSuffix
from ..helpers.Filesystem import ensureExistingEmptyDirectory
from .AudioProcessing import *

def buildTracksAndStems(self):
    tracks = {}
    trackDirNames = []
    for audioFile in self.audioFiles:
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
                guessBestParamRecordingsFile(
                    audioFile.parent.stem,
                    self.paramRecordingFiles
                )
            )
            tracks[uniqueKey] = track

        tracks[uniqueKey].stems.append( Stem(audioFile.name))


    for key,track in tracks.items():
        tracks[key].requestedApplyParams = self.preprocess['applyParams']
        tracks[key].requestedPopRemoval = self.preprocess['popRemoval']
        tracks[key].requestedNoiseMute = self.preprocess['noiseMute']
        tracks[key].requestedSkipIfSilence = self.preprocess['skipSilenceFiles']
        tracks[key].requestedMonoToStereo = self.preprocess['mergeMonoToStereo']
        tracks[key].checkWhatsPossible()

    self.tracks = tracks


def processStem____HMMMM(funcArgs):
    track = funcArgs['track']
    trackKey = funcArgs['trackKey']
    stem = funcArgs['stem']
    stemKey = funcArgs['stemKey']
    self = funcArgs['self']

    stem.fileToCopy = f'{track.absPath}/{stem.fileName}'
    #stem.fileToCopy = f'{track.absPath}/{stem.fileName}'
    #print(f' track {track.targetDirName}  stem {stem.fileName}')
    return stem, trackKey, stemKey

    if track.requestedApplyParams and stem.applyParamsPossible:
        filterArgFile = Path(f'{self.targetDir}/tmp-ui24rprocess-filter-{trackKey}-{stemKey}.txt')
        filterArgFile.write_text(',\n'.join(stem.ffmpegFilterArgs))
        targetPath = Path(f'{self.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKey}-params.flac')
        applyFilter(stem.fileToCopy, filterArgFile, targetPath)
        stem.fileToCopy = targetPath


    if track.requestedPopRemoval:
        # TODO: properly implement configurable filename filter for different operations
        pattern = '.*' + self.cnf.get('musicians', f'was.pattern') + '.*'
        if re.search(pattern.lower(), stem.fileName.lower()):
            print(f'pop removal for: {stem.fileName}')
            targetPath = Path(f'{self.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKey}-popsremoved.flac')
            removePops(
                stem.fileToCopy,
                targetPath
            )
            stem.fileToCopy = targetPath


    if track.requestedNoiseMute:
        silencesRaw = detectSilences(
            stem.fileToCopy,
            #'-50dB', # TODO: move to config
            '-60dB', # TODO: move to config
            5        # TODO: move to config
        )

        silences = silenceDetectResultToSilenceBoundries(silencesRaw)
        if len(silences) == 0:
            print(" no silences found. will not apply noisemute")
        else:
            targetPath = Path(f'{self.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKey}-noisemute.flac')
            muteNoiseSections(
                stem.fileToCopy,
                targetPath,
                silences
            )
            stem.fileToCopy = targetPath

    if track.requestedSkipIfSilence:
        duration = readAudioProperty(stem.fileToCopy, 'duration')
        #codec_name = readAudioProperty(stem.fileToCopy, 'codec_name')
        #sample_rate = readAudioProperty(stem.fileToCopy, 'sample_rate')
        if isSilenceFile(stem.fileToCopy, duration - 1):
            print('track is silence')
            stem.isSilence = True
            stem.fileToCopy = None

    if not track.requestedMonoToStereo:
        return True
    if stem.stereoLinkIndex != 1:
        return True
    if stem.isSilence == True:
        return True
    if self.tracks[trackKey].stems[stemKey-1].isSilence == True:
        return True
    
    return True
    targetPath = Path(f'{self.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKey-1}-{stemKey}-stereo.flac')
    mergeMonosToStereo(
        self.tracks[trackKey].stems[stemKey-1].fileToCopy,
        stem.fileToCopy,
        targetPath
    )
    self.tracks[trackKey].stems[stemKey-1].fileToCopy = targetPath
    stem.fileToCopy = None
    return True



def processStem(self, trackKey, stemKey):
    global jamConf
    #print('args', arg2, arg3)
    #return
#
    #global self
    #self = funcArgs['self']
    #trackKey = funcArgs['trackKey']
    #stemKey = funcArgs['stemKey']
    #track = self.tracks[trackKey]
    #stem = self.tracks[trackKey].stems[stemKey]

    print('processStem', trackKey, stemKey)
    track = self.tracks[trackKey]
    stem = track.stems[stemKey]

    #track = funcArgs['track']
    #trackKey = funcArgs['trackKey']
    #stem = funcArgs['stem']
    #stemKey = funcArgs['stemKey']
    #self = funcArgs['self']

    stem.fileToCopy = f'{track.absPath}/{stem.fileName}'
    print('stem.fileToCopy1111', stem.fileToCopy)
    #stem.fileToCopy = f'{track.absPath}/{stem.fileName}'
    #print(f' track {track.targetDirName}  stem {stem.fileName}')
    #return stem, stemKey

    if track.requestedApplyParams and stem.applyParamsPossible:
        filterArgFile = Path(f'{self.targetDir}/tmp-ui24rprocess-filter-{trackKey}-{stemKey}.txt')
        filterArgFile.write_text(',\n'.join(stem.ffmpegFilterArgs))
        targetPath = Path(f'{self.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKey}-params.flac')
        applyFilter(stem.fileToCopy, filterArgFile, targetPath)
        stem.fileToCopy = targetPath


    if track.requestedPopRemoval:
        # TODO: properly implement configurable filename filter for different operations
        pattern = '.*' + self.cnf.get('musicians', f'was.pattern') + '.*'
        if re.search(pattern.lower(), stem.fileName.lower()):
            print(f'pop removal for: {stem.fileName}')
            targetPath = Path(f'{self.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKey}-popsremoved.flac')
            removePops(
                stem.fileToCopy,
                targetPath
            )
            stem.fileToCopy = targetPath


    if track.requestedNoiseMute:
        silencesRaw = detectSilences(
            stem.fileToCopy,
            #'-50dB', # TODO: move to config
            '-60dB', # TODO: move to config
            5        # TODO: move to config
        )

        silences = silenceDetectResultToSilenceBoundries(silencesRaw)
        if len(silences) == 0:
            print(" no silences found. will not apply noisemute")
        else:
            targetPath = Path(f'{self.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKey}-noisemute.flac')
            muteNoiseSections(
                stem.fileToCopy,
                targetPath,
                silences
            )
            stem.fileToCopy = targetPath

    if track.requestedSkipIfSilence:
        duration = readAudioProperty(stem.fileToCopy, 'duration')
        #codec_name = readAudioProperty(stem.fileToCopy, 'codec_name')
        #sample_rate = readAudioProperty(stem.fileToCopy, 'sample_rate')
        if isSilenceFile(stem.fileToCopy, duration - 1):
            print('track is silence')
            stem.isSilence = True
            stem.fileToCopy = None

    self.tracks[trackKey].stems[stemKey] = stem
    #jamConf.tracks[trackKey].stems[stemKey] = stem
    print('stem.fileToCopy', stem.fileToCopy)
    if not track.requestedMonoToStereo:
        return# stem, trackKey, stemKey
    if stem.stereoLinkIndex != 1:
        return #stem, trackKey, stemKey
    if stem.isSilence == True:
        return #stem, trackKey, stemKey
    if self.tracks[trackKey].stems[stemKey-1].isSilence == True:
        return #stem, trackKey, stemKey
    
    #return True
    targetPath = Path(f'{self.targetDir}/tmp-ui24rprocess-{trackKey}-{stemKey-1}-{stemKey}-stereo.flac')
    mergeMonosToStereo(
        self.tracks[trackKey].stems[stemKey-1].fileToCopy,
        stem.fileToCopy,
        targetPath
    )
    self.tracks[trackKey].stems[stemKey-1].fileToCopy = targetPath
    stem.fileToCopy = None
    self.tracks[trackKey].stems[stemKey] = stem
    return #stem, trackKey, stemKey


def printForConfirmation(self):
    for key,track in self.tracks.items():
        print(track.printTaskList())

def processStemCallback(processedStem):
    #global self
    #stem, trackKey, stemKey = processedStem.result()
    #self.tracks[trackKey].stems[stemKey] = stem


    print('processStemCallback()', processedStem.result())

def executePreProcessing(self):
    tracks = self.tracks

    maxWorkers = 6

    if maxWorkers == 1:
        # non parallelized version
        for trackKey,track in tracks.items():
            for stemKey,stem in enumerate(track.stems):
                funcArgs['stem'] = stem
                funcArgs['stemKey'] = stemKey
                funcArgs = {
                    #'track': track,
                    'trackKey': trackKey,
                    #'stem': stem,
                    'stemKey': stemKey,
                    'self': self
                }
                processStem(funcArgs)
    else:
        # paralellized tryout
        with concurrent.futures.ProcessPoolExecutor(max_workers=maxWorkers) as executor:
            for trackKey,track in tracks.items():
                for stemKey,stem in enumerate(track.stems):
                    funcArgs = {
                        #'track': track,
                        'trackKey': trackKey,
                        #'stem': stem,
                        'stemKey': stemKey,
                        'self': self
                    }
                    #f = executor.map(processStem, [self, trackKey, stemKey])
                    #processedStem = executor.submit(processStem, (funcArgs))
                    processedStem = executor.submit(processStem, self, trackKey, stemKey)
                    #processedStem.add_done_callback(processStemCallback)

    copyProcessedFiles(self)

def copyProcessedFiles(self):
    #global self
    for trackKey,track in self.tracks.items():
        print('copying processed files', track.targetDirName)

        trackTargetPath = Path(f'{self.targetDir}/{track.targetDirName}')
        
        ensureExistingEmptyDirectory(trackTargetPath)

        anyStemCopied = False
        for stemKey,stem in enumerate(track.stems):
            if stem.fileToCopy == None:
                print('skipping', stem.fileName, str(stem.fileToCopy))
                continue
            print(' copy stem', stem.fileName)
            os.rename(str(stem.fileToCopy), str(Path(f'{trackTargetPath}/{stem.fileName}')))
            anyStemCopied = True

        if anyStemCopied == False:
            print(' all stems are silences. this track will not end up in the output dir...')
            rmtree(trackTargetPath)

    print('deleting temp files')
    tmpFiles = glob.glob(f'{self.targetDir}/tmp-ui24rprocess*')
    for filePath in tmpFiles:
        try:
            os.remove(filePath)
        except:
            print("Error while deleting file : ", filePath)



    #print(audioFiles)
    #print(paramRecordingsFiles)
    # lets search for audiofiles in inputDir
    print('done')


def guessBestParamRecordingsFile(sessionName, allParamRecordingFiles):

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