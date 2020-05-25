
from pathlib import Path
import random
#import sys
#import re
#from configparser import NoOptionError
from ..helpers.Filesystem import getFileContent


class TracktitleGenerator():
    def __init__(self, prefixes, suffixes, usedTrackTitlesFilePath = None):
        self.allPrefixes = prefixes.split()
        self.allSuffixes = suffixes.split()
        self.prefixes = []
        self.suffixes = []

        self.usedTrackTitlesFilePath = None
        if usedTrackTitlesFilePath != '':
            self.usedTrackTitlesFilePath = Path(usedTrackTitlesFilePath)
        self.usedTrackTitles = []
        self.usedTrackTitleWords = []

    def getRandomTrackName(self):
        self.prepareData()

        # shuffle words list
        random.shuffle(self.prefixes)
        random.shuffle(self.suffixes)

        # pick the first
        chosenPrefix = self.prefixes[0]
        chosenSuffix = self.suffixes[0]
        
        # remove chosen item to avoid duplicates
        self.prefixes.remove(chosenPrefix)
        self.suffixes.remove(chosenSuffix)
        
        # drop prefix or suffix sometimes
        if random.randint(1,100) > 85:
            finalTrackTitle = chosenPrefix if random.randint(1,100) < 20 else chosenSuffix
        else:
            # TODO avoid endless recursion caused by configuration quirks
            if chosenPrefix == chosenSuffix:
                return self.getRandomTrackName()
            finalTrackTitle = f'{chosenPrefix} {chosenSuffix}'
        
        # vice versa check against ".usedTracktitles"
        if finalTrackTitle in self.usedTrackTitles:
            # TODO avoid endless recursion caused by configuration quirks
            return self.getRandomTrackName()

        return finalTrackTitle

    def prepareData(self):
        self.checkUsedTrackTitles()
        self.preparePrefixes()
        self.prepareSuffixes()

    def preparePrefixes(self):
        if len(self.prefixes) > 0:
            return

        items = self.removeOftenUsedListItems(
            self.allPrefixes,
            self.usedTrackTitleWords,
            50
        )
        self.prefixes = list(set(items))

    def prepareSuffixes(self):
        if len(self.suffixes) > 0:
            return

        items = self.removeOftenUsedListItems(
            self.allSuffixes,
            self.usedTrackTitleWords,
            50
        )
        self.suffixes = list(set(items))

    def checkUsedTrackTitles(self):
        if len(self.usedTrackTitleWords) > 0:
            return
        if self.usedTrackTitlesFilePath == None:
            return
        if not self.usedTrackTitlesFilePath.is_file():
            return

        self.usedTrackTitles = getFileContent(
            str(self.usedTrackTitlesFilePath)
        ).split('\n')
        self.usedTrackTitleWords = ' '.join(self.usedTrackTitles).split()


    def removeOftenUsedListItems(self, allItems, usedItems, neededAmount):
        if len(allItems) < neededAmount:
            return allItems

        if len(usedItems) == 0:
            return allItems

        # collect all existing items as {term: count} pair
        weighted = {}
        for item in allItems:
            weighted[item] = 0

        # increase counter to all existing items
        for usedItem in usedItems:
            if usedItem == '':
                continue

            if not usedItem in weighted:
                # skip used items that are not in the available list
                continue
            weighted[usedItem] = weighted[usedItem] +1

        # group items by count
        groupedByCount = {}
        for term, counter in weighted.items():
            if not counter in groupedByCount:
                groupedByCount[counter] = []
            groupedByCount[counter].append(term)

        finalItems = []
        # iterate over all counterpairs beginning with zero
        for counter in range(0, 1000):
            if counter in groupedByCount:
                finalItems += groupedByCount[counter]
                if len(finalItems) >= neededAmount:
                    # now we have enough items collected to choose from...
                    break

        # randomize list and return first n items
        random.shuffle(finalItems)
        return finalItems[:neededAmount]

    def tracktitlesToBlacklist(self, jamSession):
        if self.usedTrackTitlesFilePath == None:
            # disabled by config
            return

        fileContentLines = []
        if self.usedTrackTitlesFilePath.is_file():
            fileContentLines = getFileContent(
                str(self.usedTrackTitlesFilePath)
            ).split('\n')

        for key, track in jamSession.tracks.items():
            fileContentLines.append(track.trackTitle)

        # add a blank line as session separator
        fileContentLines.append('')

        # persist blacklist in filesystem
        self.usedTrackTitlesFilePath.write_text(
            '\n'.join(fileContentLines)
        )
