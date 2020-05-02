import logging
from shutil import copyfile
import subprocess
import time
import json
import re

def generalCmd(cmdArgsList, description, readStdError = False):
    logging.info("starting %s" % description)
    logging.debug(' '.join(cmdArgsList))
    #print(' '.join(cmdArgsList))
    startTime = time.time()
    if readStdError:
        process = subprocess.Popen(cmdArgsList, stderr=subprocess.PIPE)
        processStdOut = process.stderr.read()
    else:
        process = subprocess.Popen(cmdArgsList, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        processStdOut = process.stdout.read()
    retcode = process.wait()
    if retcode != 0:
        print ( "ERROR: %s did not complete successfully (error code is %s)" % (description, retcode) )

    logging.info("finished %s in %s seconds" % ( description, '{0:.3g}'.format(time.time() - startTime) ) )
    return processStdOut.decode('utf-8')

# thanks to: https://stackoverflow.com/questions/38085408/complex-audio-volume-changes-with-ffmpeg
def applyFilter(inputPath, filterParamsPath, outputPath):
    cmd = [
        'ffmpeg', '-hide_banner', '-v', 'quiet', '-stats', '-y',
        '-i', str(inputPath), '-filter_complex_script', str(filterParamsPath),
        str(outputPath)
    ]
    generalCmd(cmd, 'apply filter', True)


def mergeMonosToStereo(inputPathLeft, inputPathRight, outputPath, sampleRate = None, codec = None):
    if sampleRate == None:
        sampleRate = readAudioProperty(inputPathLeft, 'sample_rate')
    if codec == None:
        codec = readAudioProperty(inputPathLeft, 'codec_name')

    cmd = [
        'ffmpeg', '-hide_banner', '-v', 'quiet', '-stats', '-y',
        '-i', str(inputPathLeft), '-i', str(inputPathRight),
        '-filter_complex', '[0:a][1:a]amerge', '-c:a', f'{codec}', '-ar', f'{sampleRate}',
        str(outputPath)
    ]
    generalCmd(cmd, 'merge mono to stereo', True)  

def removePops(inputPath, outputPath):
    # TODO make params configurabele
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-stats',
        '-i', str(inputPath),
        '-af', 'adeclick=t=40',
        str(outputPath)
    ]
    return generalCmd(cmd, 'pop removal', True)


def muteNoiseSections(inputPath, outputPath, silences):
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-stats', '-i', str(inputPath),
        '-af', f', '.join(silences),
        str(outputPath)
    ]
    return generalCmd(cmd, 'muting noise sections', True)


'''
    propName: duration, codec_name, sample_rate
'''
def readAudioProperty(filePath, propName):
    cmd = [
        'ffprobe', '-i', str(filePath),
        '-show_entries', f'stream={propName}',
        '-v', 'quiet', '-of', 'csv=p=0'
    ]
    processStdOut = generalCmd(cmd, f'readAudioProperty {propName}')

    if propName in ['duration']:
        return float(processStdOut.strip())
    if propName in ['sample_rate']:
        return int(processStdOut.strip())
    return str(processStdOut.strip())

def detectSilences(inputPath, dbLevel = '-45dB', silenceDuration = 2):
    # TODO move args to config
    cmd = [
        'ffmpeg', '-hide_banner', '-stats', '-i', str(inputPath),
        '-af', ('silencedetect=noise=%s:d=%i' % (dbLevel, silenceDuration) ),
        '-f','null', '-'
    ]
    return generalCmd(cmd, 'silence detection', True)


def isSilenceFile(inputPath, inputFileDuration):
    # TODO move dbLevel to config
    dbLevel = '-40dB'
    silenceDuration = inputFileDuration - 0.1
    cmd = [
        'ffmpeg', '-hide_banner', '-stats', '-i', str(inputPath),
        '-af', ('silencedetect=noise=%s:d=%s' % (dbLevel, silenceDuration) ),
        '-f','null', '-'
    ]
    processStdOut = generalCmd(cmd, 'silence detection')
    if 'silence_start:' in processStdOut.split():
        return True
    return False


''' parse the result of silence detect and create filter lines for ffmpeg'''
def silenceDetectResultToSilenceBoundries(resultLines, silencePadding = 1):
    foundSilences = []
    splittedSilence = resultLines.split('\n')
    for line in splittedSilence:
        if line.find('silencedetect') < 0:
            continue

        lineArgs = line.strip().split()

        # TODO: unexplainable list modification with some stdout stuff which should be skipped by condition above
        # sometimes we need to remove the first few list items to can relay on the indices
        for idx,arg in enumerate(lineArgs):
            if arg == '[silencedetect':
                lineArgs = lineArgs[idx:]
                break

        if line.find('silence_start') >= 0:
            currentStart = float(lineArgs[4])
            continue

        if line.find('silence_end') >= 0 or line.find('silence_duration') >= 0:
            currentEnd = float(lineArgs[4])

            # 1st: fade out (within {silencePadding} seconds)
            # 2nd: mute
            # 3rd: fade in (within {silencePadding} seconds)
            foundSilences.append(
                re.sub('\s+', '',
                    f'''
                    afade=enable='between(
                        t, {currentStart}, {currentStart + silencePadding}
                    )':t=out:st={currentStart}:d={silencePadding},
                    volume=enable='between(
                        t,{currentStart + silencePadding}, {currentEnd - silencePadding}
                    )':volume=0,
                    afade=enable='between(
                        t,{currentEnd - silencePadding}, {currentEnd}
                    )':t=in:st={currentEnd - silencePadding}:d={silencePadding}
                    '''
                )
            )
            continue

    return foundSilences

def detectVolume(filePath):
    cmd = [
        'ffmpeg', '-hide_banner', '-i', str(filePath),
        '-af', 'volumedetect', '-f', 'null', '/dev/null'
    ]
    processStdOut = generalCmd(cmd, 'volume detection', True)
    
    volJSON = json.loads('{}')
    pattern = ".*Parsed_volumedetect.*\]\ (.*)\:\ ([0-9.-]*)"
    for line in processStdOut.split('\n'):
        match = re.match( pattern, line)
        if match:
            volJSON[match.group(1)] = match.group(2)
    
    return volJSON

def convertAudio(inputPath, codec, sampleRate, bitRate, outputPath):
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-stats', '-i', str(inputPath),
        '-c:a', codec, '-ar', sampleRate
    ]
    if bitRate:
        cmd += [ '-ab', bitRate]

    cmd += [str(outputPath)]

    return generalCmd(cmd, f'converting audio to {codec}', True)

def normalizeAudio(inputFilePath, outputFilePath):
    cmd = [
        'ffmpeg', '-y', '-hide_banner',
        '-i', str(inputFilePath), '-af',
        'dynaudnorm=m=100',
        str(outputFilePath)
    ]
    generalCmd(cmd, 'normalize wav (dynaudionorm)')


def mergeAudioFilesToSingleFile(inputPaths, outputPath):
    if len(inputPaths) == 1:
        return copyAudioFileOrError(
            inputPaths[0],
            outputPath,
            'merge audio needs more than one inputfile'
        )

    cmd = ['ffmpeg', '-y', '-hide_banner', '-v', 'quiet', '-stats']
    for inputFile in inputPaths:
        cmd += [ '-i', str(inputFile)]

    # TODO why does amix decrease all volume levels? is "volume=2" or "volume=[N tracks]" correct???
    cmd += ['-filter_complex', ('amix=inputs=%d:duration=longest:dropout_transition=3,volume=2' % len(inputPaths) )]
    cmd += [str(outputPath)]
    
    generalCmd(cmd, 'merge audiofiles')

def concatAudioFiles(inputPaths, outputPath):
    if len(inputPaths) == 1:
        return copyAudioFileOrError(
            inputPaths[0],
            outputPath,
            'concat audio needs more than one inputfile'
        )

    cmd = ['ffmpeg', '-y', '-hide_banner', '-v', 'quiet', '-stats']
    for inputFile in inputPaths:
        cmd += [ '-i', str(inputFile)]
    cmd += ['-filter_complex', ('[0:0][1:0]concat=n=%d:v=0:a=1[out]' % len(inputPaths) ) , '-map', '[out]']
    cmd += [str(outputPath)]
    generalCmd(cmd, 'concatenate files')

def copyAudioFileOrError(inputPath, outputPath, errorMessage):
    if inputPath.suffix.lower() == outputPath.suffix.lower():
        logging.info(f'{errorMessage} - fallback to simply file copy')
        copyfile(inputPath, outputPath)
        return
    logging.error(errorMessage)

def detectBpm(inputPath, method):
    # available methods are soundstretch|bpmdetect
    # /usr/bin/soundstretch WAVFILE /dev/null -bpm=n 2>&1 | grep "Detected BPM rate" | awk '{ print $4 }' | xargs
    # /usr/bin/bpmdetect -c -p -d WAVFILE | sed -e 's:BPM::g' | xargs
    
    if method == 'soundstretch':
        cmd = [
            'soundstretch',
            str(inputPath),
            '/dev/null',
            '-bpm=n'
        ]
        processStdOut = generalCmd(cmd, 'bpm detection')

        pattern = "^(.*)Detected\ BPM\ rate\ ([0-9.]{1,5})(.*)$"
        searchIn = ' '.join(processStdOut.split())
        match = re.match( pattern, searchIn )
        if match:
            logging.info("BPM SUCCESS '%s'" % match.group(2))
            return str(bpmBoundries(float(match.group(2))))

        logging.warning(" no result of BPM detection")
        return 0
    
    if method == 'bpmdetect':
        print ("TODO: BPM detect method 'bpmdetect' not implemented yet. use soundstretch")
        return 0
    logging.warning("invalid method for bpm detect..." )
    return 0

def bpmBoundries(inputBpm):
    lowerBoundry = 70
    upperBoundry = 180
    if inputBpm < 0.1:
        return 0
    if inputBpm > lowerBoundry and inputBpm < upperBoundry:
        return inputBpm
    if inputBpm < lowerBoundry:
        # avoid endless recursion caused by too small range
        if (inputBpm*2) > upperBoundry:
            return inputBpm
        return bpmBoundries(inputBpm*2)
    if inputBpm > upperBoundry:
        # avoid endless recursion caused by too small range
        if (inputBpm/2) < lowerBoundry:
            return inputBpm
        return bpmBoundries(inputBpm/2)


def captureVideoFrame(inputPath, outputPath, second=5):
    # TODO second 5 does not exist on shorter videos
    cmd = [
        'ffmpeg', '-hide_banner', '-v', 'quiet', '-stats', '-y',
        '-i', str(inputPath), '-vcodec', 'png', '-ss', str(second),
        '-vframes', '1', '-an', '-f', 'rawvideo',
        str(outputPath)
    ]
    generalCmd(cmd, 'capture video frame')