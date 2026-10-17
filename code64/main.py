#! /usr/bin/env python3
"""Code64 command line: code64 -a <asmFile> -o <outFile>"""

import contextlib
import getopt
import io
import sys
import unittest
from unittest import mock

#--
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.absolute()))
#--

import assemble


__version__ = '0.1'


def printUsage():
    print('Usage: code64 -a <asmFile> -o <outFile>')


def main():
    """Assemble the file given on the command line. Exits with 1 on errors."""
    argv = sys.argv[1:]
    
    asmFile = None
    outFile = None

    print(f'Code64 v{__version__}  (c) Morten Perriard 2021')
    
    try:
        opts, args = getopt.getopt(argv, 'ha:o:')
    except getopt.GetoptError:
        printUsage()
        # exit code 2 means the command line was used incorrectly, a Unix convention also used
        # by Python's own argparse. 0 means success, and 1 is used for errors in the assembly.
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            printUsage()
            sys.exit()
        elif opt == '-a':
            asmFile = arg
        elif opt == '-o':
            outFile = arg
    
    if asmFile is None or args: # missing -a, or unexpected arguments
        printUsage()
        sys.exit(2) # the command line was used incorrectly, see above

    anyErrors = assemble.multiPass(asmFile, outFile)
    sys.exit(1 if anyErrors else 0)

################################################################################

class TestMain(unittest.TestCase):

    def testUsage(self):
        """Missing or incorrect arguments print the usage, and exit with 2."""
        for arguments in [[], ['-o', 'x.prg'], ['x.asm'], ['-a', 'x.asm', 'extra'], ['-x'], ['-a']]:
            with self.subTest(arguments=arguments):
                with mock.patch.object(sys, 'argv', ['code64'] + arguments), \
                     contextlib.redirect_stdout(io.StringIO()) as output, \
                     self.assertRaises(SystemExit) as exit:
                    main()
                self.assertEqual(exit.exception.code, 2)
                self.assertIn('Usage:', output.getvalue())


if __name__ == '__main__':
   main()
