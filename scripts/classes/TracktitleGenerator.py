
#from pathlib import Path
import random
#import re
#from configparser import NoOptionError

class TracktitleGenerator():
    def __init__(self, prefixes, suffixes, usedTrackTitlesFilePath = None):
        self.allPrefixes = prefixes.split()
        self.allSuffixes = suffixes.split()
        self.prefixes = []
        self.suffixes = []

        self.usedTrackTitlesFilePath = usedTrackTitlesFilePath
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
        if self.usedTrackTitlesFilePath.is_file():
            return

        self.usedTrackTitles = getFileContent(
            str(self.usedTracktitlesFile)
        ).split('\n')
        self.usedTrackTitleWords = ' '.join(self.usedTrackTitles).split()


    def removeOftenUsedListItems(self, allItems, usedItems, neededAmount):
        if len(allItems) < neededAmount:
            return allItems

        if len(usedItems) == 0:
            return allItems

        weighted = {}
        for item in allItems:
            for usedItem in usedItems:
                if not item in weighted:
                    weighted[item] = 0
                if item == usedItem:
                    weighted[item] = weighted[item] +1
                    
        # group itmes by count
        groupedByCount = {}
        for key,value in sorted(enumerate(weighted), reverse=True):
            if not weighted[value] in groupedByCount:
                groupedByCount[ weighted[value] ] = []
                groupedByCount[ weighted[value] ].append(value)
        
        finalItems = []
        for key in sorted(groupedByCount.keys()):
            finalItems = finalItems + groupedByCount[key]
            if len(finalItems) >= neededAmount:
                return finalItems
                
        return finalItems
