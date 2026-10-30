#! /usr/bin/env python3
"""Code64 command line: code64 <asmFile> -o <outFile>, or code64 -d <prgFile> -o <asmFile>, with -i <none | stable | all>"""

import argparse
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from . import __version__
from . import assemble
from . import cpu
from . import disassemble
from .context import Context


def printMemoryUse(context: Context):
    """Print the memory range used, the global labels, and a page map."""

    if len(context.memory) > 0:
        first = min(context.memory.keys())
        last = max(context.memory.keys())
        total = last-first+1
        use = f"${first:04x}-${last:04x} ({total} bytes)"
    else:
        use = 'None'

    print(f'Memory used: {use}')

    # global labels, sorted by address
    lst = sorted(map(lambda label: (context.symbols[label], label), context.labels))
    for value, label in lst:
        if not label.startswith('_'):
            print(f'${value:04x}: {label}')

    # one symbol for each 256-byte page: unused, partly used, or full
    def _pageSymbol(used):
        if used <= 0: return '░'
        elif used > 0 and used < 256: return '▒'
        elif used >= 256: return '█'

    pages = [0]*256
    for address in context.memory:
        pages[int(address>>8)] += 1
    pageString = "".join(map(_pageSymbol, pages))

    fullPagesUsed = len(list(filter(lambda x: x>=256, pages)))
    partialPagesUsed = len(list(filter(lambda x: x>0 and x<256, pages)))

    print(f'Pages used: {fullPagesUsed} full, {partialPagesUsed} partial')
    for i in range(16): # 16 pages per line
        print(f"${i*16*256:04x}: {pageString[i*16:(i+1)*16]}")


def main():
    """Assemble or disassemble the file given on the command line. Exits with 1 on errors, and 2 on incorrect arguments."""
    parser = argparse.ArgumentParser(prog='code64', description=f'Code64 v{__version__}: a 6502/Python hybrid assembler for C64 cross development.')
    parser.add_argument('file', help='the source file to assemble, or with -d the .prg or binary file to disassemble')
    parser.add_argument('-d', '--disassemble', dest='disassemble', action='store_true', help='disassemble the file instead of assembling it')
    parser.add_argument('-o', '--output', dest='outFile', help='the .prg file to write, or the source file when disassembling (default: print it)')
    parser.add_argument('-i', '--illegal', dest='illegal', choices=['none', 'stable', 'all'], default='stable',
                        help='the illegal instructions to use: none, the stable ones (default), or all')
    parser.add_argument('--version', action='version', version=f'Code64 v{__version__} (c) Morten Perriard 2021-2026')
    arguments = parser.parse_args()
    cpu.setIllegalInstructions(arguments.illegal)
    try:
        if arguments.disassemble:
            source = disassemble.disassembleFile(arguments.file, arguments.outFile)
            if not arguments.outFile:
                print(source, end='')
            anyErrors = False
        else:
            context = assemble.assembleFile(arguments.file, arguments.outFile)
            for message in context.printed:
                print(message)
            sys.stdout.flush() # keep the order when stdout and stderr go to the same pipe or file
            for message in context.warnings + context.errors:
                print(message, file=sys.stderr)
            anyErrors = len(context.errors) > 0
            if not anyErrors:
                printMemoryUse(context)
    except OSError as exception:
        print(f'error: {exception.strerror}: "{exception.filename}"', file=sys.stderr)
        anyErrors = True
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
        for arguments in [[], ['-o', 'x.prg'], ['-d'], ['x.asm', 'extra'], ['-x'], ['-a', 'x.asm'],
                          ['x.asm', '-i', 'some'], ['x.asm', '-i']]:
            with self.subTest(arguments=arguments):
                code, output, errors = self._main(arguments)
                self.assertEqual(code, 2)
                self.assertIn('usage: code64', errors)

    def testHelp(self):
        """-h prints the help, with each option, and exits with 0."""
        code, output, errors = self._main(['-h'])
        self.assertEqual(code, 0)
        self.assertIn('[-d] [-o OUTFILE]', output)
        self.assertIn('] file', output) # the file is positional
        self.assertIn('-d, --disassemble', output)
        self.assertIn('--output OUTFILE', output) # Python 3.13 shows '-o, --output OUTFILE', older versions '-o OUTFILE, --output OUTFILE'
        self.assertIn('--illegal {none,stable,all}', output)
        self.assertIn('--version', output)
        self.assertIn(f'Code64 v{__version__}', output)

    def testVersion(self):
        """--version prints the package version and copyright, and exits with 0."""
        import code64
        code, output, errors = self._main(['--version'])
        self.assertEqual(code, 0)
        self.assertEqual(output, f'Code64 v{code64.__version__} (c) Morten Perriard 2021-2026\n')

    def testIllegalInstructions(self):
        """-i chooses the illegal instructions: none, stable (the default) or all."""
        self.addCleanup(cpu.setIllegalInstructions, 'stable')
        with tempfile.TemporaryDirectory() as directory:
            for arguments, source, expected in [([], 'lax $10', 0), (['-i', 'stable'], 'lax $10', 0), (['-i', 'none'], 'lax $10', 1),
                                                (['-i', 'stable'], 'sha $1000,y', 1), (['-i', 'all'], 'sha $1000,y', 0),
                                                (['--illegal', 'none'], 'lax $10', 1), (['--illegal=all'], 'sha $1000,y', 0)]:
                with self.subTest(arguments=arguments, source=source):
                    asmFile = os.path.join(directory, 'test.asm')
                    with open(asmFile, 'w') as f:
                        f.write(source + '\n')
                    code, output, errors = self._main([asmFile] + arguments)
                    self.assertEqual(code, expected, output)

    def testAssemble(self):
        """Assembling prints the .print output, and with no errors the memory use, and saves the -o file.
        Warnings and errors go to stderr. Exits with 1 on errors."""
        with tempfile.TemporaryDirectory() as directory:
            prgFile = os.path.join(directory, 'a.prg')
            for name, source, expected, printed, diagnostics in [
                ('ok.asm',    '.print "hi"\n.warning "careful"\nlda #1\n', 0, ['hi', 'Memory used: $1000-$1001 (2 bytes)'], ['ok.asm:2: warning: careful']),
                ('error.asm', '.print "hi"\n.error "stop"\n',               1, ['hi'],                                       ['error.asm:2: error: stop'])]:
                with self.subTest(source=source):
                    asmFile = os.path.join(directory, name)
                    with open(asmFile, 'w') as f:
                        f.write(source)
                    code, output, errors = self._main([asmFile, '-o', prgFile])
                    self.assertEqual(code, expected, output + errors)
                    lines = [line.split('/')[-1] for line in output.splitlines()]
                    self.assertEqual([line for line in lines if line.startswith(tuple(printed))], printed)
                    self.assertEqual([line.split('/')[-1] for line in errors.splitlines()], diagnostics)
            with open(prgFile, 'rb') as f:
                self.assertEqual(f.read(), bytes([0x00, 0x10, 0xa9, 0x01])) # saved by the first source only

    def testOutputOrder(self):
        """With stderr in the same pipe as stdout (2>&1), .print output comes before the warnings, as on a terminal."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with tempfile.TemporaryDirectory() as directory:
            asmFile = os.path.join(directory, 'test.asm')
            with open(asmFile, 'w') as f:
                f.write('.print "hi"\n.warning "careful"\n')
            output = subprocess.run([sys.executable, '-m', 'code64.main', asmFile], cwd=root,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout
        lines = [line.split('/')[-1] for line in output.splitlines()]
        self.assertEqual(lines[:2], ['hi', 'test.asm:2: warning: careful'])

    def testMissingSource(self):
        """A missing source exits with 1, and an error on stderr."""
        with tempfile.TemporaryDirectory() as directory:
            missingFile = os.path.join(directory, 'missing.asm')
            code, output, errors = self._main([missingFile])
            self.assertEqual(code, 1)
            self.assertEqual(errors, f'error: No such file or directory: "{missingFile}"\n')

    def testMemoryUse(self):
        """The page map shows each page as unused, partly used, or full."""
        context = Context({})
        context.memory = {address: 0 for address in range(0x1000, 0x1180)} # page $10 full, page $11 partly used
        with contextlib.redirect_stdout(io.StringIO()) as output:
            printMemoryUse(context)
        self.assertIn('Pages used: 1 full, 1 partial', output.getvalue())
        self.assertIn('$1000: █▒░░░░░░░░░░░░░░', output.getvalue())

    def testDisassemble(self):
        """-d disassembles to the -o file, and exits with 1 and an error on stderr if a file can't be read or written."""
        with tempfile.TemporaryDirectory() as directory:
            prgFile, asmFile = os.path.join(directory, 'a.prg'), os.path.join(directory, 'a.asm')
            with open(prgFile, 'wb') as f:
                f.write(bytes([0x00, 0x10, 0x60])) # rts at $1000
            code, output, errors = self._main(['-d', prgFile, '-o', asmFile])
            self.assertEqual(code, 0)
            with open(asmFile) as f:
                self.assertIn('rts', f.read())
            code, output, errors = self._main(['--disassemble', prgFile, '--output', asmFile]) # the long names
            self.assertEqual(code, 0)
            with open(asmFile) as f:
                self.assertEqual(f.read(), disassemble.disassembleFile(prgFile))
            code, output, errors = self._main(['-d', prgFile]) # without -o, only the source is printed
            self.assertEqual(code, 0)
            self.assertEqual(output, disassemble.disassembleFile(prgFile))
            self.assertEqual(errors, '')
            missingFile = os.path.join(directory, 'missing.prg')
            code, output, errors = self._main(['-d', missingFile, '-o', asmFile])
            self.assertEqual(code, 1)
            self.assertIn(f'error: No such file or directory: "{missingFile}"', errors)
            missingFolder = os.path.join(directory, 'missing', 'a.asm')
            code, output, errors = self._main(['-d', prgFile, '-o', missingFolder])
            self.assertEqual(code, 1)
            self.assertIn(f'error: No such file or directory: "{missingFolder}"', errors)

    def testPackageImports(self):
        """Importing the package keeps its modules inside it, e.g. code64.cpu, not a top level cpu."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        modules = subprocess.run([sys.executable, '-c', 'import sys, code64.main; print(*sorted(sys.modules))'],
                                 cwd=root, capture_output=True, text=True, check=True).stdout.split()
        self.assertIn('code64.cpu', modules)
        self.assertNotIn('cpu', modules)
        self.assertNotIn('assemble', modules)

    def testPublicApi(self):
        """The package exports assembleFile, disassembleFile and Context, and its modules stay importable."""
        import code64
        self.assertEqual(sorted(code64.__all__), ['Context', 'assembleFile', 'disassembleFile'])
        self.assertIs(code64.assembleFile, assemble.assembleFile)
        self.assertIs(code64.disassembleFile, disassemble.disassembleFile)
        self.assertIs(code64.Context, Context)
        self.assertIs(code64.disassemble, disassemble) # the module, not the function of the same name


if __name__ == '__main__':
   main()
