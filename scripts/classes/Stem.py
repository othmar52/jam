
from pathlib import Path
import re
from configparser import NoOptionError

class Stem(object):
    def __init__(self, pathObj):
        self.path = Path(f'{pathObj}')
        self.uniqueStemName = ''
        self.originalName = ''
        self.musicianShorty = None
        self.duration = 0
        self.byteSize = 0
        self.color = 'default'
        self.sorting = 0
        self.silencePercent = 0
        self.volume = 1
        self.normLevels = {
            'vanilla': {},      # volume levels of original file
            'normalized': {}    # volume levels of normalized file
        }
        self.tmpFileNormalized = None
        self.wavPeaks = []

        self.webstem = {
            'targetPath': None
        }

    '''
        check if we have configuration about musician based on filename
        also set the color in case it is configured
    '''
    def applyConfigStuff(self, jamConf):
        self.originalName = self.path.stem
        self.uniqueStemName = self.path.stem
        if jamConf.cnf.get('general', 'removeNumericPrefixFromStems') == '1':
            match = re.match('^([0-9]{2})\ (.*)$', self.path.stem)
            if match:
                self.uniqueStemName = match[2]

        for shorty in jamConf.allMusicianShorties:
            try:
                pattern = '.*' + jamConf.cnf.get('musicians', f'{shorty}.pattern') + '.*'
            except NoOptionError:
                continue

            if pattern == '.**.*':
                pattern = '.*'

            # print ( 'shorty: %s, pattern: %s' % (shorty, pattern) )
            # TODO john vs. johnny may gives invalid sorting when first match is shorter
            if not re.search(pattern.lower(), self.uniqueStemName.lower()):
                continue

            self.musicianShorty = shorty
            self.sorting = self.getNumericDictIndex(
                shorty,
                jamConf.allMusicianShorties
            )
            
            try:
                self.color = jamConf.cnf.get('musicians', f'{shorty}.color')
            except NoOptionError:
                self.color = 'default'
            break


    '''
        based on the wavpeaks we can identify audio tracks whith very much silence
        this information will be used for sorting the audiotracks im webstem GUI
    '''
    def calculateSilencePercent(self):
        if len(self.wavPeaks) == 0:
            return
        
        amountZeroValues = 0
        for val in self.wavPeaks:
            if val == 0:
                amountZeroValues += 1

        self.silencePercent = int(amountZeroValues / (len(self.wavPeaks)/100))


    def getNumericDictIndex(self, keyToSearch, dictToSearch):
        idx = 1
        for key in dictToSearch:
            if key == keyToSearch:
                return idx
            idx += 1
        return 0