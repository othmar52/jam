#!/bin/env python3

import sys
from .JamConfBase import JamConfBase

class JamConfPreprocess(JamConfBase):
    def __init__(self):
        JamConfBase.__init__(self)
        self.action = 'preprocess'

        # required for preprocessing
        #self.noiseMute = {
        #    'duration': 0,
        #    'dB': 0
        #}

        self.preprocess = {
            'scheme': None,
            'targetFormat': None,
            'targetCodec': None,
            'targetRate': None,

            'applyParams': False,
            'popRemoval': False,
            'noiseMute': False,
            'skipSilenceFiles': False,
            'mergeMonoToStereo': False
        }
        self.tracks = {}

    def collectDataAndValidate(self):
        self.collectAllFiles()
        self.audioFilesInInputDirOrExit()
        self.targetDirOrExit()
        self.readOrGuessDataScheme() # ui24r or zoomr24
        self.checkProcessingFeaturesForDataScheme()
        if self.preprocess['scheme'] == 'ui24r':
            from ...helpers.PreProcessUi24rRecordings import buildTracksAndStems
        else:
            # this makes no sense! but currently zoomr24 is not implemented yet
            from ...helpers.PreProcessUi24rRecordings import buildTracksAndStems

        buildTracksAndStems(self)

    def confirmAndRun(self):
        if self.preprocess['scheme'] == 'ui24r':
            from ...helpers.PreProcessUi24rRecordings import printForConfirmation
            from ...helpers.PreProcessUi24rRecordings import executePreProcessing
        else:
            # this makes no sense! but currently zoomr24 is not implemented yet
            from ...helpers.PreProcessUi24rRecordings import printForConfirmation
            from ...helpers.PreProcessUi24rRecordings import executePreProcessing

        printForConfirmation(self)
        choice = input(f'press return to start processing...')
        if choice != '':
            print('exiting...')
            sys.exit()

        executePreProcessing(self)


    def readOrGuessDataScheme(self):
        validRecTypes = [
            x.strip() for x in self.cnf.get('preprocess', 'supportedSchemes').split(',')
        ]

        if self.cnf.get('preprocess', 'dataScheme') in validRecTypes:
            # no need to guess as its already provided by configuration
            self.preprocess['scheme'] = self.cnf.get('preprocess', 'dataScheme')
            return

        for recType in validRecTypes:
            for metaFile in self.recorderMetaFiles:
                if metaFile.name.find(self.cnf.get(f'preprocess.{recType}', 'recMetaFile')) > -1:
                    self.preprocess['scheme'] = recType
                    return

        # TODO guess by other typical indicators
        # TODO handle some kind of generic/configurable filesystem scheme
        # for now force a probably invalid scheme...
        self.preprocess['scheme'] = 'zoomr24'

    def checkProcessingFeaturesForDataScheme(self):
        if self.preprocess['scheme'] == 'ui24r':
            self.ensureConfigFor(
                'preprocess',
                'applyParams',
                'try to find *.uiparamrecording.txt and apply params? [Y,n]'
            )

        self.ensureConfigFor(
            'preprocess',
            'noiseMute',
            'enable noise mute? [Y,n]'
        )

        self.ensureConfigFor(
            'preprocess',
            'popRemoval',
            'enable pop removal? [Y,n]'
        )
        # TODO: validate thise 2 values in case pop removal is enabled....
        # jamConf.cnf.get('preprocess', 'popRemovalProfile'),
        # jamConf.cnf.get('preprocess', 'popRemovalSensitivity')
        self.ensureConfigFor(
            'preprocess',
            'skipSilenceFiles',
            'skip silence files? [Y,n]'
        )
        if self.preprocess['scheme'] == 'ui24r':
            self.ensureConfigFor(
                'preprocess',
                'mergeMonoToStereo',
                'try to merge mono files to stereo? [Y,n]'
            )
