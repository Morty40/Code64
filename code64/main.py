#! /usr/bin/env python3

import getopt
import sys

#--
import pathlib, sys
sys.path.append(str(pathlib.Path(__file__).parent.absolute()))
#--

import assemble


__version__ = '0.1'


def printUsage():
    print('Usage: Code64.py -a <asmFile> -d <disFile> -o <outFile>')


def main():
    argv = sys.argv[1:]
    
    asmFile = None
    outFile = None

    print(f'Code64 v{__version__}  (c) Morten Perriard 2021')
    
    try:
        opts, args = getopt.getopt(argv, 'ha:d:o:')
    except getopt.GetoptError:
        printUsage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            printUsage()
            sys.exit()
        elif opt == '-a':
            asmFile = arg
        elif opt == '-o':
            outFile = arg
    
    if asmFile is not None:
        anyErrors = assemble.multiPass(asmFile, outFile)
    
    if anyErrors:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
   main()
