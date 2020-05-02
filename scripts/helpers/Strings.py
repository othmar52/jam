#!/bin/env python3
import re
import math
import time
import datetime
from .Filesystem import getFileContent

'''
   in case inputString exists in existingStrings append a suffix until it is unique
'''
def uniqueOrSuffix(inputString, existingStrings):
    if not inputString in existingStrings:
        return inputString
    
    for i in range(1, 1000):
        newString = f'{inputString}.{i}'
        if not newString in existingStrings:
            return newString
    
    # TODO how to handle this very unlikely edge case?
    return inputString


def replaceCommonPlaceholders(inputString, jamConf):
    returnString = str(inputString)
    returnString = returnString.replace(
        '{SCRIPT_PATH}', str(jamConf.rootDir)
    )
    if not hasattr(jamConf, 'jamSession'):
        return returnString

    if hasattr(jamConf.jamSession, 'bandName'):
        returnString = returnString.replace(
            '{bandname}', jamConf.jamSession.bandName
        )
    if hasattr(jamConf.jamSession, 'paddedCounter'):
        returnString = returnString.replace(
            '{paddedCounter}', jamConf.jamSession.paddedCounter
        )
    if hasattr(jamConf.jamSession, 'dateString'):
        returnString = returnString.replace(
            '{sessionDate}', jamConf.jamSession.dateString
        )
    # TODO replace '{shorties}'
    return returnString


'''
 replaces exotic characters with similar [A-Za-z0-9] and removes all
 other characters of a string
'''
def az09(string, preserve = '', strToLower = False):
    charGroup = [
        ["_", " "],
        ["a","à","á","â","ã","ä","å","ª","а"],
        ["A","À","Á","Â","Ã","Ä","Å","А"],
        ["b","Б","б"],
        ["c","ç","¢","©"],
        ["C","Ç"],
        ["d","д"],
        ["D","Ð","Д"],
        ["e","é","ë","ê","è","е","э"],
        ["E","È","É","Ê","Ë","€","Е","Э"],
        ["f","ф"],
        ["F","Ф"],
        ["g","г"],
        ["G","Г"],
        ["h","х"],
        ["H","Х"],
        ["i","ì","í","î","ï","и","ы"],
        ["I","Ì","Í","Î","Ï","¡","И","Ы"],
        ["k","к"],
        ["K","К"],
        ["l","л"],
        ["L","Л"],
        ["m","м"],
        ["M","М"],
        ["n","ñ","н"],
        ["N","Н"],
        ["o","ò","ó","ô","õ","ö","ø","о"],
        ["O","Ò","Ó","Ô","Õ","Ö","О"],
        ["p","п"],
        ["P","П"],
        ["r","®","р"],
        ["R","Р"],
        ["s","ß","š","с"],
        ["S","$","§","Š","С"],
        ["t","т"],
        ["T","т"],
        ["u","ù","ú","û","ü","у"],
        ["U","Ù","Ú","Û","Ü","У"],
        ["v","в"],
        ["V","В"],
        ["W","Ь"],
        ["w","ь"],
        ["x","×"],
        ["y","ÿ","ý","й","ъ"],
        ["Y","Ý","Ÿ","Й","Ъ"],
        ["z","з"],
        ["Z","З"],
        ["ae","æ"],
        ["AE","Æ"],
        ["tm","™"],
        ["(","{", "[", "<"],
        [")","}", "]", ">"],
        ["0","Ø"],
        ["2","²"],
        ["3","³"],
        ["and","&"],
        ["zh","Ж","ж"],
        ["ts","Ц","ц"],
        ["ch","Ч","ч"],
        ["sh","Ш","ш","Щ","щ"],
        ["yu","Ю","ю"],
        ["ya","Я","я"]
    ]
    for cgIndex,charGroupItem in enumerate(charGroup):
        for charIndex,char in enumerate(charGroupItem):
            # TODO "preserve" currently works only with a single char, right?
            #if charGroup[cgIndex][charIndex].find(preserve) != -1:
            #    continue

            string = string.replace(charGroup[cgIndex][charIndex], charGroup[cgIndex][0])

    string = re.sub( (r'[^a-zA-Z0-9\-._%s]' % preserve), '', string)
    if strToLower == True:
        string = string.lower()
    return string
  

def sortByCustomOrdering(itemsToSort, priorityStrings, removeDuplicates=False):
    #print ("sortByPriority()") 
    result = {}
    gappedArray = []
    for i in range(0, (len(priorityStrings)*len(itemsToSort))):
        #print(i)
        #gappedArray[i] = 0
        gappedArray.insert(i,0)
    
    #print(gappedArray)
    itemStringCounter=-1
    for itemString in itemsToSort:
        ++itemStringCounter
        #print ( "itemString: %s" % itemString )
        prioStringCounter=-1
        for prioString in priorityStrings:
            prioStringCounter = prioStringCounter + 1
            #print( "prioStringCounter %s" % prioStringCounter)
            weightedStartKey = prioStringCounter*len(itemsToSort)
            #print ( "prioString: %s" % prioString )
            if prioString == itemString:
                #print ("FOUND: %s" % prioString)
                if gappedArray[weightedStartKey] == 0:
                    #print( "weightedStartKey %s is FREE" % weightedStartKey)
                    gappedArray[weightedStartKey] = itemString
                    break
                #print( "weightedStartKey %s in use" % weightedStartKey)
                for newIndex in range(weightedStartKey, len(gappedArray)):
                    if gappedArray[newIndex] == 0:
                        gappedArray[newIndex] = itemString
                        break;
        #print ( itemString )
        
    finalArray = []
    for val in gappedArray:
        if val == 0:
            continue
        if removeDuplicates == False:
            finalArray += [val]
            continue
        if val in finalArray:
            continue
        finalArray += [val]
    #print( itemToSort )
    #print (finalArray)
    return finalArray

def nextLetter(currentLetter):
    return str(bytes([bytes(currentLetter, 'utf-8')[0] + 1]))[2]

def secondsToMinutes(seconds, dropDecimals = True):
    minutes = '%02.1d' % ( seconds // 60 )
    if dropDecimals == False:
        remainingSeconds = '%04.1f' % (seconds % 60)
    else:
        remainingSeconds = '%02.1d' % math.floor(seconds % 60)
    return f'{minutes}:{remainingSeconds}'


'''
    MM:SS:BB
    minutes, seconds, blocks (1/75 sec)
'''
def formatSecondsForCueSheet(seconds):
    minutes = '%02.1d' % ( seconds // 60 )
    remainingSeconds = '%02.1d' % math.floor(seconds % 60)
    # TODO: calculate blocks from decimals. for now give  shit
    return f'{minutes}:{remainingSeconds}:00'

''' it seems to be common to have filenames like YYYYMMDD_HHMMSS.jpg '''
def detectTimestampFromString(inputString):
    dateTime = None
    match = re.match('.*([0-9]{8}\_[0-9]{6}).*', str(inputString))
    if match:
        dateTime = time.mktime(datetime.datetime.strptime(match.group(1), '%Y%m%d_%H%M%S').timetuple())

    return dateTime


def replaceMarkersInString(searchReplace, inputString):
    for search in searchReplace:
        inputString = inputString.replace(search, str(searchReplace[search]))
    return inputString

def replaceMarkersFromFile(searchReplace, filePath):
    return replaceMarkersInString(
        searchReplace,
        getFileContent(filePath)
    )