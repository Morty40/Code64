#! /usr/bin/env python3
"""Code64 command line: code64 -a <asmFile> -o <outFile>, or code64 -d <prgFile> -o <asmFile>"""

import argparse
import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

#--
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.absolute()))
#--

import assemble
import disassemble


__version__ = '0.1'


def main():
    """Assemble or disassemble the file given on the command line. Exits with 1 on errors, and 2 on incorrect arguments."""
    print(f'Code64 v{__version__}  (c) Morten Perriard 2021')
    parser = argparse.ArgumentParser(prog='code64', description='A 6502/Python hybrid assembler for C64 cross development.')
    files = parser.add_mutually_exclusive_group(required=True)
    files.add_argument('-a', dest='asmFile', help='the source file to assemble')
    files.add_argument('-d', dest='binFile', help='the .prg or binary file to disassemble')
    parser.add_argument('-o', dest='outFile', help='the .prg file to write, or the source file when disassembling')
    arguments = parser.parse_args()
    if arguments.binFile and not arguments.outFile:
        parser.error('-d requires -o') # exits with 2
    if arguments.binFile:
        anyErrors = disassemble.disassembleFile(arguments.binFile, arguments.outFile)
    else:
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
        for arguments in [[], ['-o', 'x.prg'], ['x.asm'], ['-a', 'x.asm', 'extra'], ['-x'], ['-a'],
                          ['-d', 'x.prg'], ['-a', 'x.asm', '-d', 'x.prg']]:
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
        self.assertIn('-d BINFILE', output)

    def testDisassemble(self):
        """-d disassembles to the -o file, and exits with 1 on errors."""
        with tempfile.TemporaryDirectory() as directory:
            prgFile, asmFile = os.path.join(directory, 'a.prg'), os.path.join(directory, 'a.asm')
            with open(prgFile, 'wb') as f:
                f.write(bytes([0x00, 0x10, 0x60])) # rts at $1000
            code, output, errors = self._main(['-d', prgFile, '-o', asmFile])
            self.assertEqual(code, 0)
            with open(asmFile) as f:
                self.assertIn('rts', f.read())
            code, output, errors = self._main(['-d', os.path.join(directory, 'missing.prg'), '-o', asmFile])
            self.assertEqual(code, 1)


if __name__ == '__main__':
   main()
