#!/bin/env python3

from scripts.ConfigStuff import *

def main():
    jamConf = getJamConf()
    jamConf.collectDataAndValidate()
    # TODO: add smth like a systemcheck (non standard python libs available?, binaries ffmpeg, bpmdetect,... available?)
    jamConf.confirmAndRun()


if __name__ == "__main__":
    main()
