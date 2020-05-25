
from pathlib import Path

from ..helpers.AudioProcessing import *
class Track(object):
    def __init__(self):
        self.dirName = ''
        self.startSecond = None
        self.endSecond = None
        self.duration = 0
        self.trackTitle = ''
        self.trackNumber = None
        self.trackLetter = None
        self.byteSize = 0
        self.trackNumberPaddedZero = None
        self.bpm = 0
        # TODO add more properties for tags...
        self.artist = ''
        self.album = ''
        self.genre = ''
        # @see https://ffmpeg.org/ffmpeg-filters.html#loudnorm
        # hopefully we can set initial volume levels for normalized stems based on one of those values
        self.dbLevelsInputFiles = {
            'meanVolumeMin': 0,
            'meanVolumeMax': -1000,
            'maxVolumeMin': 0,
            'maxVolumeMax': -1000
        }
        self.webstem = {
            'targetDir': None,
            'configJsFile': None,
            'tracklistJsFile': None
        }

        self.tmpFileMergedStems = None
        self.tmpFileMergedStemsNormalized = None

        self.stems = []

    def getLongestStemDuration(self):
        duration = 0
        for stem in self.stems:
            if stem.duration > duration:
                duration = stem.duration
        return duration


    def runProcessing(self, jamConf):
        mergeStems = False
        normalizeSingleStem = False
        normalizeMergedStems = False
        bpmDetection = False
        if jamConf.basket.album == True:
            mergeStems = True
            if jamConf.cnf.get('album', 'normalize') == '1':
                normalizeMergedStems = True

        if jamConf.basket.stem == True:
            mergeStems = True
            if jamConf.cnf.get('stem', 'normalize') == '1':
                normalizeMergedStems = True
                normalizeSingleStem = True

        if jamConf.basket.webstem == True:
            if jamConf.cnf.get('webstem.audio', 'normalize') == '1':
                normalizeSingleStem = True

            if self.bpm == '' or int(float(self.bpm)) < 1:
                if jamConf.cnf.get('webstem', 'detectBpm') == '1':
                    bpmDetection = True
                    mergeStems = True

        if jamConf.basket.cuemix == True:
            mergeStems = True
            # TODO: make it configuruable to normalize before or after merge
            # for now keep it simple and use (maybe) already normalized tmp-files
            if jamConf.cnf.get('cuemix', 'normalize') == '1':
                normalizeMergedStems = True

        stemPathsToMerge = []
        for stem in self.stems:
            stemPathsToMerge += [stem.path]
            if normalizeSingleStem == True:
                stem.tmpFileNormalized = Path(f'{jamConf.targetDir}/tmp-track-{self.trackLetter}-stem-{stem.path.stem}-normalized.wav')
                print(f'TRACK:{self.dirName} STEM:\'{stem.path.name}\' normalizing...')
                normalizeAudio(stem.path, stem.tmpFileNormalized)

        if mergeStems == True:
            self.tmpFileMergedStems = Path(f'{jamConf.targetDir}/tmp-track-{self.trackLetter}-mergedstems.wav')
            print(f'TRACK:{self.dirName} merging all {len(self.stems)} stems...')
            mergeAudioFilesToSingleFile(stemPathsToMerge, self.tmpFileMergedStems)


        if normalizeMergedStems == True:
            self.tmpFileMergedStemsNormalized = Path(f'{jamConf.targetDir}/tmp-track-{self.trackLetter}-mergedstems-normalized.wav')
            print(f'TRACK:{self.dirName} normalizing merged stems...')
            normalizeAudio(self.tmpFileMergedStems, self.tmpFileMergedStemsNormalized)

        if bpmDetection == True:
            print(f'TRACK:{self.dirName} detecting BPM...')
            self.bpm = detectBpm(self.tmpFileMergedStems, jamConf.cnf.get('bpmdetect', 'method'))

        return self

    '''
        based on before+after volume levels of normalized input-stems some upper and lower boundries gets collected
    '''
    def collectDbLevelsFromInputFile(self, volumeJSON):
        try:
            if float(volumeJSON['mean_volume']) < self.dbLevelsInputFiles['meanVolumeMin']:
                self.dbLevelsInputFiles['meanVolumeMin'] = float(volumeJSON['mean_volume'])
            if float(volumeJSON['mean_volume']) > self.dbLevelsInputFiles['meanVolumeMax']:
                self.dbLevelsInputFiles['meanVolumeMax'] = float(volumeJSON['mean_volume'])
            if float(volumeJSON['max_volume']) < self.dbLevelsInputFiles['maxVolumeMin']:
                self.dbLevelsInputFiles['maxVolumeMin'] = float(volumeJSON['max_volume'])
            if float(volumeJSON['max_volume']) > self.dbLevelsInputFiles['maxVolumeMax']:
                self.dbLevelsInputFiles['maxVolumeMax'] = float(volumeJSON['max_volume'])
        except KeyError:
            pass
