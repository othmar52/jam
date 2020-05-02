
import os
import time
import datetime
from shutil import rmtree
from PIL import Image, ImageOps, ExifTags

def getFileContent(pathAndFileName):
    with open(pathAndFileName, 'r') as theFile:
        data = theFile.read()
        return data

def ensureExistingDirectory(dirPath):
    dirPath.mkdir(parents=True, exist_ok=True)

def ensureExistingEmptyDirectory(dirPath):
    ensureExistingDirectory(dirPath)
    rmtree(dirPath)
    ensureExistingDirectory(dirPath)

def symlink(pathFrom, pathTo):
    try:
        os.symlink(str(pathFrom), str(pathTo))
    except FileExistsError:
        return

def detectTimestampFromExif(inputPath):
    try:
        image = Image.open(str(inputPath))
        exif = {
            ExifTags.TAGS[k]: v
            for k, v in image._getexif().items()
            if k in ExifTags.TAGS
        }
        dateTime = time.mktime(datetime.datetime.strptime(exif['DateTimeOriginal'], '%Y:%m:%d %H:%M:%S').timetuple())
    except (FileNotFoundError, KeyError, ValueError, AttributeError):
        dateTime = None

    return dateTime

def createThumbnail(inputPath, targetPath, thumbWidth, thumbHeight):
    thumbTarget = ImageOps.fit(
        Image.open(str(inputPath)),
        (
            int(thumbWidth),
            int(thumbHeight)
        ),
        Image.ANTIALIAS
    )
    thumbTarget.save(str(targetPath))

def doubleRotateImage(inputPath, targetPath):
    
    img = Image.open(str(inputPath))
    exif = img.info['exif']
    out = img.rotate(90, expand=True)
    out.save(str(targetPath))

    img = Image.open(str(targetPath))
    out = img.rotate(270, expand=True)
    out.save(str(targetPath), exif=exif)
