
from __future__ import print_function
import re
import os
from shutil import copyfile, rmtree
import glob
import hashlib

from ..classes.TrackUi24r import *
from ..helpers.Strings import uniqueOrSuffix
from ..helpers.Filesystem import ensureExistingEmptyDirectory
from .AudioProcessing import *

def buildTracksAndStems(jamConf):
    tracks = {}
    trackDirNames = []
    for audioFile in jamConf.audioFiles:
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
                    jamConf.paramRecordingFiles
                )
            )
            tracks[uniqueKey] = track

        tracks[uniqueKey].stems.append( Stem(audioFile.name))


    for key,track in tracks.items():
        tracks[key].requestedApplyParams = jamConf.preprocess['applyParams']
        tracks[key].requestedPopRemoval = jamConf.preprocess['popRemoval']
        tracks[key].requestedNoiseMute = jamConf.preprocess['noiseMute']
        tracks[key].requestedSkipIfSilence = jamConf.preprocess['skipSilenceFiles']
        tracks[key].requestedMonoToStereo = jamConf.preprocess['mergeMonoToStereo']
        tracks[key].checkWhatsPossible()

    jamConf.tracks = tracks

def processTrack(track, jamConf):


def printForConfirmation(jamConf):
    for key,track in jamConf.tracks.items():
        print(track.printTaskList())

def executePreProcessing(jamConf):
    tracks = jamConf.tracks
    for key,track in tracks.items():
        print('processing track', track.targetDirName)

        trackTargetPath = Path(f'{jamConf.targetDir}/{track.targetDirName}')
        for stemKey,stem in enumerate(track.stems):
            tracks[key].stems[stemKey].fileToCopy = f'{track.absPath}/{stem.fileName}'
            print('  stem', stem.fileName)

            if track.requestedApplyParams and stem.applyParamsPossible:
                filterArgFile = Path(f'{jamConf.targetDir}/tmp-ui24rprocess-filter-{key}-{stemKey}.txt')
                filterArgFile.write_text(',\n'.join(stem.ffmpegFilterArgs))
                targetPath = Path(f'{jamConf.targetDir}/tmp-ui24rprocess-{key}-{stemKey}-params.flac')
                applyFilter(tracks[key].stems[stemKey].fileToCopy, filterArgFile, targetPath)
                tracks[key].stems[stemKey].fileToCopy = targetPath


            if track.requestedPopRemoval:
                # TODO: properly implement configurable filename filter for different operations
                pattern = '.*' + jamConf.cnf.get('musicians', f'was.pattern') + '.*'
                if re.search(pattern.lower(), stem.fileName.lower()):
                    print(f'pop removal for: {stem.fileName}')
                    targetPath = Path(f'{jamConf.targetDir}/tmp-ui24rprocess-{key}-{stemKey}-popsremoved.flac')
                    removePops(
                        tracks[key].stems[stemKey].fileToCopy,
                        targetPath
                    )
                    tracks[key].stems[stemKey].fileToCopy = targetPath


            if track.requestedNoiseMute:
                silencesRaw = detectSilences(
                    tracks[key].stems[stemKey].fileToCopy,
                    #'-50dB', # TODO: move to config
                    '-60dB', # TODO: move to config
                    5        # TODO: move to config
                )

                silences = silenceDetectResultToSilenceBoundries(silencesRaw)
                if len(silences) == 0:
                    print(" no silences found. will not apply noisemute")
                else:
                    targetPath = Path(f'{jamConf.targetDir}/tmp-ui24rprocess-{key}-{stemKey}-noisemute.flac')
                    muteNoiseSections(
                        tracks[key].stems[stemKey].fileToCopy,
                        targetPath,
                        silences
                    )
                    tracks[key].stems[stemKey].fileToCopy = targetPath

            if track.requestedSkipIfSilence:
                duration = readAudioProperty(tracks[key].stems[stemKey].fileToCopy, 'duration')
                #codec_name = readAudioProperty(tracks[key].stems[stemKey].fileToCopy, 'codec_name')
                #sample_rate = readAudioProperty(tracks[key].stems[stemKey].fileToCopy, 'sample_rate')
                if isSilenceFile(tracks[key].stems[stemKey].fileToCopy, duration - 1):
                    print('track is silence')
                    tracks[key].stems[stemKey].isSilence = True
                    tracks[key].stems[stemKey].fileToCopy = None

            if not track.requestedMonoToStereo:
                continue
            if stem.stereoLinkIndex != 1:
                continue
            if tracks[key].stems[stemKey].isSilence == True:
                continue
            if tracks[key].stems[stemKey-1].isSilence == True:
                continue
            
            targetPath = Path(f'{jamConf.targetDir}/tmp-ui24rprocess-{key}-{stemKey-1}-{stemKey}-stereo.flac')
            mergeMonosToStereo(
                tracks[key].stems[stemKey-1].fileToCopy,
                tracks[key].stems[stemKey].fileToCopy,
                targetPath
            )
            tracks[key].stems[stemKey-1].fileToCopy = targetPath
            tracks[key].stems[stemKey].fileToCopy = None



    for key,track in tracks.items():
        print('copying processed files', track.targetDirName)

        trackTargetPath = Path(f'{jamConf.targetDir}/{track.targetDirName}')
        
        ensureExistingEmptyDirectory(trackTargetPath)

        anyStemCopied = False
        for stemKey,stem in enumerate(track.stems):
            if stem.fileToCopy == None:
                print('skipping', stem.fileName)
                continue
            print(' copy stem', stem.fileName)
            os.rename(str(stem.fileToCopy), str(Path(f'{trackTargetPath}/{stem.fileName}')))
            anyStemCopied = True

        if anyStemCopied == False:
            print(' all stems are silences. this track will not end up in the output dir...')
            rmtree(trackTargetPath)

    print('deleting temp files')
    tmpFiles = glob.glob(f'{jamConf.targetDir}/tmp-ui24rprocess*')
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