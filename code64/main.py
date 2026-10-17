#! /usr/bin/env python3
"""Code64 command line: code64 -a <asmFile> -o <outFile>"""

import argparse
import contextlib
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


def main():
    """Assemble the file given on the command line. Exits with 1 on errors, and 2 on incorrect arguments."""
    print(f'Code64 v{__version__}  (c) Morten Perriard 2021')
    parser = argparse.ArgumentParser(prog='code64', description='A 6502/Python hybrid assembler for C64 cross development.')
    parser.add_argument('-a', dest='asmFile', required=True, help='the source file to assemble')
    parser.add_argument('-o', dest='outFile', help='the .prg file to write')
    arguments = parser.parse_args()
    anyErrors = assemble.multiPass(arguments.asmFile, arguments.outFile)
    sys.exit(1 if anyErrors else 0)

################################################################################

class TestMain(unittest.TestCase):

    def _main(self, arguments: list):
        """Run main() with the arguments. Returns the exit code, and the output and error output."""
        with mock.patch.object(sys, 'argv', ['code64'] + arguments), \
             contextlib.redirect_stdout(io.StringIO()) as output, \
             contextlib.redirect_stderr(io.StringIO()) as errors, \
             self.assertRaises(SystemExit) as raised:
            main()
        return raised.exception.code, output.getvalue(), errors.getvalue()

    def testUsage(self):
        """Missing or incorrect arguments print the usage, and exit with 2."""
        for arguments in [[], ['-o', 'x.prg'], ['x.asm'], ['-a', 'x.asm', 'extra'], ['-x'], ['-a']]:
            with self.subTest(arguments=arguments):
                code, output, errors = self._main(arguments)
                self.assertEqual(code, 2)
                self.assertIn('usage: code64', errors)

    def testHelp(self):
        """-h prints the help, with each option, and exits with 0."""
        code, output, errors = self._main(['-h'])
        self.assertEqual(code, 0)
        self.assertIn('-a ASMFILE', output)
        self.assertIn('-o OUTFILE', output)


if __name__ == '__main__':
   main()
