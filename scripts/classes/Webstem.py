#!/bin/env python3

import re
import os
import secrets
import concurrent.futures
from shutil import copytree
from pathlib import Path
from ..helpers.Strings import *
from ..helpers.Filesystem import *
from ..helpers.AudioProcessing import *
from ..helpers.AudioWaveform import getWaveformValues

# requires "Pillow" package
from PIL import Image

class Webstem(object):
    def __init__(self, templateDir):
        self.templateDir = templateDir
        self.htmlTemplate = Path(f'{templateDir}/index.htm')
        self.playerDir = Path(f'{templateDir}/data/stemplayer')
        self.launcherDir = Path(f'{templateDir}/launcher')
        self.trackConfigTemplate = Path(f'{templateDir}/jstemplates/track.js')
        self.stemConfigTemplate = Path(f'{templateDir}/jstemplates/stem.js')
        self.imageConfigTemplate = Path(f'{templateDir}/jstemplates/image.js')
        self.videoConfigTemplate = Path(f'{templateDir}/jstemplates/video.js')
        self.tracklistConfigTemplate = Path(f'{templateDir}/jstemplates/tracklist.js')

        self.targetDir = None
        self.baseHtmlName = ''
        self.baseHtml = None
        self.tracklistJsFile = None

        self.imagesJs = []
        self.videosJs = []

    def run(self, jamConf):

        # TODO: move directory check + creation to previous run
        self.targetDir = Path(
            replaceCommonPlaceholders(
                jamConf.cnf.get('webstem', 'targetDir'), jamConf
            )
        )
        ensureExistingDirectory(self.targetDir)
        self.addMissingColorsToStems(jamConf)

        dirScheme = jamConf.cnf.get('webstem', 'dirScheme')
        sessionDirName = replaceCommonPlaceholders(dirScheme, jamConf)
        jamConf.jamSession.webstem['targetDir'] = Path(
            f'{self.targetDir}/data/{az09(sessionDirName)}'
        )
        jamConf.jamSession.webstem['tracklistJsFile'] = Path(
            f'{jamConf.jamSession.webstem["targetDir"]}/data/tracklist.js'
        )

        self.ensureWebstemRootfilesExist(jamConf)

        # copy player on session level
        ensureExistingEmptyDirectory(
            Path(f'{jamConf.jamSession.webstem["targetDir"]}/data')
        )
        self.copyPlayerFiles(
            jamConf,
            Path(f'{jamConf.jamSession.webstem["targetDir"]}/data/stemplayer'),
            'session'
        )
        self.copyLauncherFiles(
            jamConf,
            Path(f'{jamConf.jamSession.webstem["targetDir"]}/launcher'),
            'session'
        )
        # copy html file on session level
        # TODO respect configured document name
        self.copyIndexDocument(
            jamConf,
            Path(f'{jamConf.jamSession.webstem["targetDir"]}/index.htm'),
            'session'
        )

        self.copyImageFiles(jamConf)
        self.copyVideoFiles(jamConf)


        maxWorkers = int(jamConf.cnf.get('general', 'maxWorkers'))
        maxWorkers = 1

        # TODO remove duplicate code
        if maxWorkers <= 1:

            for key, track in jamConf.jamSession.tracks.items():
                track.webstem['targetDir'] = Path(
                    f'{jamConf.jamSession.webstem["targetDir"]}/data/{track.trackLetter}-{az09(track.trackTitle)}/data'
                )
                track.webstem['configJsFile'] = Path(f'{track.webstem["targetDir"]}/config.js')
                track.webstem['tracklistJsFile'] = Path(f'{track.webstem["targetDir"]}/tracklist.js')
                track.byteSize = 0
                ensureExistingDirectory(track.webstem['targetDir'])
                self.processWebstemTrack(track, jamConf)

        else:
            # paralellized tryout
            with concurrent.futures.ProcessPoolExecutor(max_workers=maxWorkers) as executor:
                for key, track in jamConf.jamSession.tracks.items():
                    track.webstem['targetDir'] = Path(
                        f'{jamConf.jamSession.webstem["targetDir"]}/data/{track.trackLetter}-{az09(track.trackTitle)}/data'
                    )
                    track.webstem['configJsFile'] = Path(f'{track.webstem["targetDir"]}/config.js')
                    track.webstem['tracklistJsFile'] = Path(f'{track.webstem["targetDir"]}/tracklist.js')
                    track.byteSize = 0
                    ensureExistingDirectory(track.webstem['targetDir'])
                    processedTrack = executor.submit(self.processWebstemTrack, track, jamConf)
                    processedTrack.add_done_callback(self.processWebstemTrackCallback)

            #self.processWebstemTrack(track, jamConf)


        self.finishWebStemSession(jamConf)
        self.createZip(jamConf)


    def processWebstemTrackCallback(self, pr):
        print('done callback')
        track = pr.result()

    def processWebstemTrack(self, track, jamConf):
        trackProgessString = f'TRACK:{track.trackNumber}/{len(jamConf.jamSession.tracks)}'
        for stemIdx, stem in enumerate(track.stems):
            stemProgressString = f'STEM:{stemIdx+1}/{len(track.stems)}'
            print(f'WEBSTEM: {trackProgessString} {stemProgressString} converting to {jamConf.cnf.get("webstem.audio", "format")}')

            stemSrcPath = stem.path
            stem.webstem['targetPath'] = Path(
                f'{track.webstem["targetDir"]}/{az09(stem.uniqueStemName)}.{jamConf.cnf.get("webstem.audio", "format")}'
            )
            if jamConf.cnf.get('webstem.audio', 'normalize') == '1':
                stemSrcPath = stem.tmpFileNormalized
            convertAudio(
                stemSrcPath,
                jamConf.cnf.get('webstem.audio', 'codec'),
                jamConf.cnf.get('webstem.audio', 'samplerate'),
                jamConf.cnf.get('webstem.audio', 'bitrate'),
                stem.webstem['targetPath']
            )
            stem.normLevels['vanilla'] = detectVolume(stem.path)
            stem.normLevels['normalized'] = detectVolume(stem.webstem['targetPath'])
            track.collectDbLevelsFromInputFile(stem.normLevels['vanilla'])
            stem.byteSize = stem.webstem['targetPath'].stat().st_size
            stem.wavPeaks = getWaveformValues(
                stemSrcPath,
                jamConf.cnf.get('webstem', 'waveformResolution')
            )
            stem.calculateSilencePercent()
            track.byteSize = track.byteSize + stem.byteSize

            #print (stem.uniqueStemName)
        self.finishWebStemTrack(track, jamConf)
        return track

    def finishWebStemTrack(self, track, jamConf):
        self.copyPlayerFiles(
            jamConf,
            Path(f'{track.webstem["targetDir"]}/stemplayer'),
            'track'
        )
        self.copyLauncherFiles(
            jamConf,
            Path(f'{track.webstem["targetDir"]}/../launcher'),
            'track'
        )
        # TODO respect configured document name
        self.copyIndexDocument(
            jamConf,
            Path(f'{track.webstem["targetDir"]}/../index.htm'),
            'track'
        )

        stemsJs = []
        moveDrumTracksToTop = jamConf.cnf.get('webstem.gui', 'moveDrumTracksToTop')
        moveSilentTracksToBottom = int(jamConf.cnf.get('webstem.gui', 'moveSilentTracksToBottom'))
        for stem in self.sortStems(track.stems, moveDrumTracksToTop, moveSilentTracksToBottom):
            stemVolume = self.guessInitalVolumeLevel(stem.normLevels, track.dbLevelsInputFiles)
            if jamConf.cnf.get('webstem.gui', 'drumsVolumeBoost') == '1':
                if stem.uniqueStemName.lower().find('drum') >= 0:
                    stemVolume = 1

            stemsJs.append(
                replaceMarkersFromFile(
                    {
                        '{stem.path}': str(stem.webstem['targetPath'].name),
                        '{stem.rawDataPath}': f'{track.dirName}/{stem.path.name}',
                        '{stem.peaks}': self.lineBreakedJoin(stem.wavPeaks, ','),
                        '{stem.title}': stem.uniqueStemName,
                        '{stem.volume}': stemVolume,
                        '{stem.color}': stem.color,
                        '{stem.sorting}': stem.sorting,
                        '{stem.normalizationLevels}': json.dumps(stem.normLevels),
                        '{stem.byteSize}': str(stem.byteSize)
                    },
                    self.stemConfigTemplate
                )
            )

        track.webstem['configJsFile'].write_text(
            replaceMarkersFromFile(
                {
                    '{session.counter}': jamConf.jamSession.counter,
                    '{session.paddedCounter}': jamConf.jamSession.paddedCounter,
                    '{session.date}': jamConf.jamSession.dateString,
                    '{session.day}': jamConf.jamSession.day,
                    '{session.month}': jamConf.jamSession.month,
                    '{session.year}': jamConf.jamSession.year,
                    '{track.letter}': track.trackLetter,
                    '{track.number}': track.trackNumber,
                    '{track.title}': track.trackTitle,
                    '{track.artist}': track.artist,
                    '{track.genre}': track.genre,
                    '{track.duration}': track.duration,
                    '{track.byteSize}': str(track.byteSize),
                    '{track.bpm}': track.bpm,
                    '{track.dbLevelsInputFiles}': track.dbLevelsInputFiles,
                    '{stems}': ','.join(stemsJs),
                    '{images}': ','.join(self.imagesJs),
                    '{videos}': ','.join(self.videosJs)
                },
                self.trackConfigTemplate
            )
        )

    '''
        the sorting should be same as defined in config.general.musicians
        but the term 'drum' in stem filename affects the sorting
        having a lot of silence in stem's audio may affect the sorting as well
    '''
    def sortStems(self, stemsList, moveDrumTracksToTop, moveSilentTracksToBottom):
        dictToSort = {0:[]}
        # TODO use filename as 2nd sort priority (currently: xxx3, xxx1, xxx4)
        for stem in stemsList:
            if moveDrumTracksToTop == '1' and stem.uniqueStemName.lower().find('drum') >= 0:
                stem.sorting = 0
            if stem.silencePercent > moveSilentTracksToBottom:
                stem.sorting = stem.silencePercent
            if not stem.sorting in dictToSort:
                dictToSort[stem.sorting] = []
            dictToSort[stem.sorting].append(stem)

        final = []
        for key in sorted(dictToSort):
            for stem in dictToSort[key]:
                final.append(stem)
                
        return final

    '''
        tricky task to decide what volume level should be applied
        because maybe all stems are normalized via dynaudionorm
        this approach makes use of measuring the volume levels before and after normalisation
        based on all those measurings a decision will be made.
        but maybe it shouldn't be done that linear how it currently is :/
        TODO: improve!!! any suggestions?
    '''
    def guessInitalVolumeLevel(self, stemLevels, trackLevelBoundries):
        stemMeanValue = float(stemLevels['vanilla']['mean_volume'])
        foundMax = float(trackLevelBoundries['meanVolumeMax'])
        foundMin = float(trackLevelBoundries['meanVolumeMin'])
        foundMin = -50

        targetMax = 1
        targetMin = 0.2
        
        onePercent = (foundMin*-1) - (foundMax*-1)
        targetPercent = 1 - (((stemMeanValue*-1) - (foundMax*-1)) / onePercent) * (targetMax - targetMin)
        if targetPercent < targetMin:
            return self.limitToMax(targetMin)

        return self.limitToMax(targetPercent)

    def limitToMax(self, inputValue, limit = 1):
        if(inputValue > limit):
            return limit
        return inputValue

    '''
        make editors with a 4096 characters per line limit happy
        by adding a linebrak every 45 items

    '''
    def lineBreakedJoin(self, listItems, joinChar):
        nthItem = 30
        listLines = [
            joinChar.join(
                map(str, listItems[nthItem * i: nthItem * i + nthItem])
            ) for i in range(0, int(len(listItems) / nthItem))
        ]
        return ('%s\n        ' % joinChar).join(listLines)


    def finishWebStemSession(self, jamConf):
        trackJsTemplate = '    { trackIndex: "{track.trackLetter}", trackDir: "{track.dirName}" }'
        allTracksJs = []
        for idx, track in jamConf.jamSession.tracks.items():
            trackJs = replaceMarkersInString(
                {
                    '{track.dirName}': track.webstem['targetDir'].parent.name,
                    '{track.trackLetter}': track.trackLetter
                },
                trackJsTemplate
            )
            allTracksJs.append(trackJs)
            
            # create single config in trackdirectory
            singleTrackJs = replaceMarkersFromFile(
                {
                    '{session.paddedCounter}': jamConf.jamSession.paddedCounter,
                    '{session.dirName}': jamConf.jamSession.webstem['targetDir'].name,
                    '{trackItems}': trackJs,
                    '{hostLevel}': 'track'
                },
                self.tracklistConfigTemplate
            )
            track.webstem['tracklistJsFile'].write_text(singleTrackJs)

        # create another config in sessions directory
        trackListNoHostlevel = replaceMarkersFromFile(
            {
                '{session.paddedCounter}': jamConf.jamSession.paddedCounter,
                '{session.dirName}': jamConf.jamSession.webstem['targetDir'].name,
                '{trackItems}': ',\n'.join(allTracksJs)
            },
            self.tracklistConfigTemplate
        )
        trackJs = replaceMarkersInString(
            { '{hostLevel}': 'tracklist' },
            trackListNoHostlevel
        )
        jamConf.jamSession.webstem['tracklistJsFile'].write_text(trackJs)
        

        # create another config for all sessions to append
        trackJs = replaceMarkersInString(
            { '{hostLevel}': 'sessionlist' },
            trackListNoHostlevel
        )

        sessionlistJsFile = Path(f'{self.targetDir}/data/tracklist.js')
        self.replaceOrPrependSessionListJs(trackJs, jamConf.jamSession.paddedCounter)

    '''
        in case the session counter already exists in sesssion list js: replace
        otherwise add it to beginning of the file
    '''
    def replaceOrPrependSessionListJs(self, jsSnippet, paddedCounter):

        existingFileContent = ''
        sessionlistJsFile = Path(f'{self.targetDir}/data/tracklist.js')
        if sessionlistJsFile.is_file():
            existingFileContent = getFileContent(str(sessionlistJsFile))
        
        # prepend new session to the beginning of the file
        newFileContent = ''.join([jsSnippet, existingFileContent])

        matchBegin = f'\/\*\ session{paddedCounter}\ begin\ \*\/'
        matchEnd = f'\/\*\ session{paddedCounter}\ end\ \*\/'
        pattern = f'(.*){matchBegin}(.*){matchEnd}(.*)'

        # check if it already exists and replace the config for specific session
        match = re.match( pattern, existingFileContent, re.DOTALL)
        if match:
            newFileContent = ''.join([ match[1], jsSnippet.strip(), match[3]])

        sessionlistJsFile.write_text(newFileContent)



    def ensureWebstemRootfilesExist(self, jamConf):
        playerRoot = Path(f'{self.targetDir}/data/stemplayer')
        if not playerRoot.is_dir():
            copytree(str(self.playerDir), str(playerRoot))

        # TODO respect configured filename
        indexDocument = Path(f'{self.targetDir}/index.htm')
        if not indexDocument.is_file():
            copyfile(str(self.htmlTemplate), str(indexDocument))

        launcherRoot = Path(f'{self.targetDir}/launcher')
        if not launcherRoot.is_dir():
            copytree(str(self.launcherDir), str(launcherRoot))

    '''
        symlinks or hardcopy?
    '''
    def copyPlayerFiles(self, jamConf, targetPath, hostLevel):
        if os.name == 'nt':
            self.hardcopyPlayerFiles(jamConf, targetPath)
            return
        if jamConf.cnf.get('webstem.filesystem', 'useSymlinks') != '1':
            self.hardcopyPlayerFiles(jamConf, targetPath)
            return

        self.symlinkPlayerFiles(jamConf, targetPath, hostLevel)

    def hardcopyPlayerFiles(self, jamConf, targetPath):
        copytree(str(self.playerDir), str(targetPath))

    def symlinkPlayerFiles(self, jamConf, targetPath, hostLevel):
        relativeTarget = '../../../../stemplayer'
        if hostLevel == 'session':
            relativeTarget = '../../stemplayer'
        symlink(
            relativeTarget,
            targetPath
        )

    '''
        symlinks or hardcopy?
    '''
    def copyLauncherFiles(self, jamConf, targetPath, hostLevel):
        if os.name == 'nt':
            self.hardcopyPlayerFiles(jamConf, targetPath)
            return
        if jamConf.cnf.get('webstem.filesystem', 'useSymlinks') != '1':
            self.hardcopyLauncherFiles(jamConf, targetPath)
            return

        self.symlinkLauncherFiles(jamConf, targetPath, hostLevel)

    def hardcopyLauncherFiles(self, jamConf, targetPath):
        copytree(str(self.launcherDir), str(targetPath))

    def symlinkLauncherFiles(self, jamConf, targetPath, hostLevel):
        relativeTarget = '../../../../launcher'
        if hostLevel == 'session':
            relativeTarget = '../../launcher'
        symlink(
            relativeTarget,
            targetPath
        )

    def copyIndexDocument(self, jamConf, targetPath, hostLevel):
        if os.name == 'nt':
            self.hardcopyIndexDocument(jamConf, targetPath)
            return
        if jamConf.cnf.get('webstem.filesystem', 'useSymlinks') != '1':
            self.hardcopyIndexDocument(jamConf, targetPath)
            return

        self.symlinkIndexDocument(jamConf, targetPath, hostLevel)

    def hardcopyIndexDocument(self, jamConf, targetPath):
        copy(str(self.playerDir), str(targetPath))

    def symlinkIndexDocument(self, jamConf, targetPath, hostLevel):
        # TODO respect configured document name
        relativeTarget = '../../../../index.htm'
        if hostLevel == 'session':
            relativeTarget = '../../index.htm'
        symlink(
            relativeTarget,
            targetPath
        )

    '''
        copy images
        generate thumbnails
        persist paths & more in a json
    '''
    def copyImageFiles(self, jamConf):
        if jamConf.cnf.get('webstem', 'includeMedia') != '1':
            return

        if len(jamConf.imageFiles) == 0:
            return

        # copy images
        imagesTargetDir = Path(f'{jamConf.jamSession.webstem["targetDir"]}/data/images')
        ensureExistingEmptyDirectory(imagesTargetDir)

        maxWorkers = int(jamConf.cnf.get('general', 'maxWorkers'))

        if maxWorkers <= 1:
            # non parallelized version
            for image in jamConf.imageFiles:
                self.handleImage(image, imagesTargetDir)
        else:
            # paralellized tryout
            with concurrent.futures.ProcessPoolExecutor(max_workers=maxWorkers) as executor:
                for image in jamConf.imageFiles:
                    #track.runProcessing(jamConf)
                    processedImage = executor.submit(self.handleImage, image, imagesTargetDir, jamConf)
                    processedImage.add_done_callback(self.handleImageCallback)



    def handleImageCallback(self, pr):
        self.imagesJs.append(pr.result())

    def handleImage(self, image, imagesTargetDir, jamConf):
        print(image)
        relativeMediaPath = str(image.resolve()).replace(str(jamConf.inputDir.resolve()), '')
        newFileName = az09(
            relativeMediaPath.replace('/', '-').lstrip('-')
        )

        if jamConf.cnf.get('webstem', 'mediaRotate') == '1':
            doubleRotateImage(
                image,
                f'{jamConf.targetDir}/tmp-{newFileName}'
            )
            image = Path(f'{jamConf.targetDir}/tmp-{newFileName}')

        imageTargetPath = f'{imagesTargetDir}/{newFileName}'
        copyfile(str(image), imageTargetPath)

        createThumbnail(
            imageTargetPath,
            f'{imageTargetPath}.thumb.png',
            jamConf.cnf.get('webstem.gui', 'thumbWidth'),
            jamConf.cnf.get('webstem.gui', 'thumbHeight')
        )

        # persist in json
        imageJsTemplate = replaceMarkersFromFile(
            {
                '{image.path}': f'data/images/{newFileName}',
                '{image.byteSize}': str(image.stat().st_size),
                '{image.timestamp}': detectTimestampFromExif(image),
                '{image.thumbPath}': f'data/images/{newFileName}.thumb.png',
                '{image.title}': '' # TODO which title makes sense?
            },
            self.imageConfigTemplate
        )
        self.imagesJs.append(imageJsTemplate)
        return imageJsTemplate

    '''
        copy videos
        generate a picture from video
        create thumbnail from extracted picture
        persist paths & more in a json
    '''
    def copyVideoFiles(self, jamConf):
        if jamConf.cnf.get('webstem', 'includeMedia') != '1':
            return

        if len(jamConf.videoFiles) == 0:
            return

        # copy videos
        videosTargetDir = Path(f'{jamConf.jamSession.webstem["targetDir"]}/data/videos')
        ensureExistingEmptyDirectory(videosTargetDir)
        for video in jamConf.videoFiles:
            relativeMediaPath = str(video.resolve()).replace(str(jamConf.inputDir.resolve()), '')
            newFileName = az09(
                relativeMediaPath.replace('/', '-').lstrip('-')
            )

            videoTargetPath = f'{videosTargetDir}/{newFileName}'
            copyfile(str(video), videoTargetPath)

            # take a snapshot from video file
            stillTargetPath = f'{videoTargetPath}.still.png'
            captureVideoFrame(video, stillTargetPath )

            createThumbnail(
                stillTargetPath,
                f'{stillTargetPath}.thumb.png',
                jamConf.cnf.get('webstem.gui', 'thumbWidth'),
                jamConf.cnf.get('webstem.gui', 'thumbHeight')
            )

            # persist in json
            videoJsTemplate = replaceMarkersFromFile(
                {
                    '{video.path}': f'data/videos/{newFileName}',
                    '{video.byteSize}': str(video.stat().st_size),
                    '{video.stillPath}': f'data/videos/{newFileName}.still.png',
                    '{video.thumbPath}': f'data/videos/{newFileName}.still.png.thumb.png'
                },
                self.videoConfigTemplate
            )
            self.videosJs.append(videoJsTemplate)


    '''
        those stems, that have no configuration in [musitians] gets a random color
        preferably a color that is currently not used by others
        further we want to have the same chosen random color for all tracks within the session
    '''
    def addMissingColorsToStems(self, jamConf):
        allColors = jamConf.cnf.get('webstem.gui', 'colors').split()
        availableColors = allColors[:]

        filenamesWithoutColors = {}
        # we assume that all audiofiles have the same filename
        for key, track in jamConf.jamSession.tracks.items():
            for stem in track.stems:
                if stem.color == 'default':
                    # add stem name to list, that we have to assign a random color
                    filenamesWithoutColors[stem.path.name] = ''
                    continue
                if stem.color in availableColors:
                    # remove already used color from random colors list
                    availableColors.remove(stem.color)

        # in case all available colors are already assigned we have no other chance to have color dupes
        if len(availableColors) == 0:
            availableColors = allColors[:]

        # define which random color to use
        for i, stemFileName in enumerate(filenamesWithoutColors):
            if len(availableColors) == 0:
                availableColors = allColors[:]
            randomColor = secrets.choice(availableColors)
            filenamesWithoutColors[stemFileName] = randomColor
            availableColors.remove(randomColor)

        # assign the color to all stems of all tracks
        for key, track in jamConf.jamSession.tracks.items():
            for stem in track.stems:
                if stem.color != 'default':
                    continue
                stem.color = filenamesWithoutColors[stem.path.name]

    def createZip(self, jamConf):
        if jamConf.cnf.get('webstem.filesystem', 'createZip') != '1':
            # disabled by config
            return
        print('creating zip archive of webstem filesystem')
        webStemZip(jamConf.targetDir, jamConf.jamSession.webstem['targetDir'])
