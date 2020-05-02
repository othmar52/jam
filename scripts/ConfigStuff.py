#!/bin/env python3

import argparse
import configparser
import os
from pathlib import Path
import sys
from .classes.JamConf.JamConfPreprocess import JamConfPreprocess
from .classes.JamConf.JamConf import JamConf
from .helpers.Filesystem import *

runPreprocessAction = False
runAnyOtherAction = False


def actionIsPreprocessOrOther(actionArg):
    global runPreprocessAction, runAnyOtherAction
    if actionArg == 'preprocess':
        runPreprocessAction = True
    else:
        runAnyOtherAction = True

    if runPreprocessAction == True and runAnyOtherAction == True:
        raise argparse.ArgumentTypeError(
            'combination of action "preprocess" with other actions is not supported!\nuse either preprocess or any other action(s)'
        )
    return actionArg

def isExistingDirectoryArgument(string):
    if os.path.isdir(string):
        return string

    raise argparse.ArgumentTypeError(f'{string} is not a valid directory')

def programDescription ():
    return '''DESCRIPTION:
process audiofiles of multitrack recordings
---------------------------------------------------------------
TODO: add discription of supported recorder filetree
  Soundcraft Ui24R
  Zoom R-24
    '''

def getJamConf():
    parser = argparse.ArgumentParser(
        description=programDescription(),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser._action_groups.pop()
    required = parser.add_argument_group('required arguments'.upper())
    optional = parser.add_argument_group('optional arguments'.upper())
    required.add_argument(
        'action',
        nargs = '*',
        type=actionIsPreprocessOrOther,
        help='what to do',
        choices=['preprocess', 'album', 'stem', 'webstem', 'cuemix']
    )
    required.add_argument(
        '-i', '--inputdir',
        type=isExistingDirectoryArgument,
        help='input directory containing your audio files',
        required=True
    )
    optional.add_argument(
        '--targetdir',
        type=str,
        help='target directory for the processed files'
    )
    args = parser.parse_args()

    jamConf = JamConfPreprocess()
    if args.action[0] != 'preprocess':
        jamConf = JamConf()
        if 'album' in args.action:
            jamConf.basket.album = True
        if 'stem' in args.action:
            jamConf.basket.stem = True
        if 'webstem' in args.action:
            jamConf.basket.webstem = True
        if 'cuemix' in args.action:
            jamConf.basket.cuemix = True

    jamConf.inputDir = Path(args.inputdir)
    jamConf.cnf = configparser.ConfigParser(strict=False)

    try:
        jamConf.cnf.read([
            f'{jamConf.rootDir}/config/general.ini',       # shipped with gitrepo
            f'{jamConf.rootDir}/config/preprocess.ini',    # shipped with gitrepo
            f'{jamConf.rootDir}/config/album.ini',         # shipped with gitrepo
            f'{jamConf.rootDir}/config/stem.ini',          # shipped with gitrepo
            f'{jamConf.rootDir}/config/webstem.ini',       # shipped with gitrepo
            f'{jamConf.rootDir}/config/cuemix.ini',        # shipped with gitrepo
            f'{jamConf.rootDir}/config/tracktitles.ini',   # shipped with gitrepo
            f'{jamConf.rootDir}/config/local.ini',         # optional gitignored local configuration
            f'{jamConf.inputDir}/config.ini',              # optional config in input directory with audio files
            f'{jamConf.inputDir}/config.txt'               # optional config in input directory with audio files
        ])
    except configparser.ParsingError as parsingError:
        choice = input(f'parsing error: {parsingError}.\ncontinue anyway? [Y,n]')
        if choice.lower() != 'y' and choice != '':
            sys.exit()

    # maybe not used for requested action but provide it anyway...
    if args.targetdir:
        jamConf.targetDir = Path(args.targetdir)

    return jamConf
