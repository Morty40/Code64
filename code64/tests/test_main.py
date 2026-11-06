#! /usr/bin/env python3
"""Tests of the command line."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from .. import __version__
from .. import assemble
from .. import cpu
from .. import disassemble
from ..context import Context
from ..main import main, printMemoryUse, sortedLabels


class TestMain(unittest.TestCase):
    """Tests of the command line."""

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
        for arguments in [[], ['-o', 'x.prg'], ['-d'], ['x.asm', 'extra'], ['-x'],
                          ['x.asm', '-i', 'some'], ['x.asm', '-i'], ['x.asm', '--vice'], ['x.asm', '-t'], ['x.asm', '-t', 'amiga'], ['-d', 'x.prg', '-t', 'c64'],
                          ['x.asm', '-l'], ['x.asm', '--labels']]:
            with self.subTest(arguments=arguments):
                code, output, errors = self._main(arguments)
                self.assertEqual(code, 2)
                self.assertIn('usage: code64', errors)

    def testInterrupted(self):
        """Ctrl-C prints a message, without a traceback, and exits with 130."""
        for module, function, arguments in [(assemble, 'assembleFile', ['x.asm']),
                                            (disassemble, 'disassembleFile', ['-d', 'x.prg'])]:
            with self.subTest(function=function), mock.patch.object(module, function, side_effect=KeyboardInterrupt):
                code, output, errors = self._main(arguments)
                self.assertEqual(code, 130)
                self.assertEqual(output, '')
                self.assertEqual(errors, 'error: Interrupted\n')

    def testHelp(self):
        """-h prints the help, with each option, and exits with 0."""
        code, output, errors = self._main(['-h'])
        self.assertEqual(code, 0)
        self.assertIn('[-d] [-o OUTFILE]', output)
        self.assertIn('positional arguments:\n  file ', output)
        self.assertIn('-d, --disassemble', output)
        self.assertIn('--output OUTFILE', output) # Python 3.13 shows '-o, --output OUTFILE', older versions '-o OUTFILE, --output OUTFILE'
        self.assertIn('--illegal {none,stable,all}', output)
        self.assertIn('--labels LABELSFILE', output)
        self.assertIn('--vice VICEFILE', output)
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

    def testTarget(self):
        """-t and --target choose the target imports, and without them there are none."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile = os.path.join(directory, 'test.asm')
            with open(asmFile, 'w') as f:
                f.write('.print BASIC_START_ADDRESS\n')
            for arguments, expected in [(['-t', 'c64'], '2049'), (['--target', 'vic20'], '4097'), (['-t', 'c16'], '4097'), (['--target=c64'], '2049')]:
                with self.subTest(arguments=arguments):
                    code, output, errors = self._main([asmFile] + arguments)
                    self.assertEqual(code, 0, errors)
                    self.assertEqual(output.splitlines()[0], expected)
            code, output, errors = self._main([asmFile])
            self.assertEqual(code, 1)
            self.assertIn("Name 'BASIC_START_ADDRESS' is not defined", errors)

    def testAssemble(self):
        """Assembling prints the .print output and the memory use, sends warnings to stderr, and saves the -o file."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, prgFile = os.path.join(directory, 'a.asm'), os.path.join(directory, 'a.prg')
            with open(asmFile, 'w') as f:
                f.write('.print "hi"\n.warning "careful"\nlda #1\n')
            code, output, errors = self._main([asmFile, '-o', prgFile])
            self.assertEqual(code, 0, errors)
            self.assertIn('hi', output.splitlines())
            self.assertIn('Memory used: $1000-$1001 (2 bytes)', output.splitlines())
            self.assertEqual(errors, f'{asmFile}:2: warning: careful\n')
            with open(prgFile, 'rb') as f:
                self.assertEqual(f.read(), bytes([0x00, 0x10, 0xa9, 0x01]))

    def testAssembleError(self):
        """With an error, assembling still prints the .print output, but not the memory use, and saves nothing. Exits with 1."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, prgFile = os.path.join(directory, 'a.asm'), os.path.join(directory, 'a.prg')
            with open(asmFile, 'w') as f:
                f.write('.print "hi"\n.error "stop"\n')
            code, output, errors = self._main([asmFile, '-o', prgFile])
            self.assertEqual(code, 1)
            self.assertIn('hi', output.splitlines())
            self.assertNotIn('Memory used', output)
            self.assertEqual(errors, f'{asmFile}:2: error: stop\n')
            self.assertFalse(os.path.exists(prgFile))

    def testSortedLabels(self):
        """The labels and zero page variables, sorted by address, with local labels as global_local,
        and generator labels as generator1_local. Other symbols are not included."""
        source = 'VALUE = 5\n.zpbyte "counter"\nstart: lda #VALUE\n_loop: dex\nbne _loop\nrts\n' \
                 '.python\ndef wait():\n    return "_x: dex\\nbne _x"\n.end\n@wait()\n'
        with tempfile.TemporaryDirectory() as directory:
            asmFile = os.path.join(directory, 'test.asm')
            with open(asmFile, 'w') as f:
                f.write(source)
            context = assemble.assembleFile(asmFile)
        self.assertEqual(sortedLabels(context), [(0x0002, 'counter'), (0x1000, 'start'), (0x1002, 'start_loop'), (0x1006, 'wait1_x')])

    def testViceCommands(self):
        """--vice writes a VICE monitor commands file: the labels, then the .break breakpoints.
        The memory use doesn't list the labels."""
        source = 'start: nop\n.break\nnop\n.break "RL > $40"\nrts\n'
        expected = 'al C:1000 .start\nbreak C:1001\nbreak C:1002 if RL > $40\n'
        with tempfile.TemporaryDirectory() as directory:
            asmFile, viceFile = os.path.join(directory, 'test.asm'), os.path.join(directory, 'test.vmc')
            with open(asmFile, 'w') as f:
                f.write(source)
            code, output, errors = self._main([asmFile, '--vice', viceFile])
            self.assertEqual(code, 0, errors)
            with open(viceFile) as f:
                self.assertEqual(f.read(), expected)
            self.assertNotIn('start', output)
            code, output, errors = self._main(['-d', asmFile, '--vice', viceFile]) # only when assembling
            self.assertEqual(code, 2)
            self.assertIn('--vice can only be used when assembling', errors)

    def testLabels(self):
        """-l writes the labels as Python assignments."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, labelsFile = os.path.join(directory, 'test.asm'), os.path.join(directory, 'test.py')
            with open(asmFile, 'w') as f:
                f.write('start: ldx #5\n_loop: dex\nbne _loop\nrts\n')
            for option in ['-l', '--labels']:
                with self.subTest(option=option):
                    code, output, errors = self._main([asmFile, option, labelsFile])
                    self.assertEqual(code, 0, errors)
                    with open(labelsFile) as f:
                        self.assertEqual(f.read(), 'start = 0x1000\nstart_loop = 0x1002\n')

    def testLabelsDisassemble(self):
        """With -d, -l reads the labels, and the disassembly uses their names."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, prgFile, labelsFile = (os.path.join(directory, name) for name in ['test.asm', 'test.prg', 'test.py'])
            with open(asmFile, 'w') as f:
                f.write('start: ldx #5\n_loop: dex\nbne _loop\nrts\n')
            code, output, errors = self._main([asmFile, '-o', prgFile, '-l', labelsFile])
            self.assertEqual(code, 0, errors)
            code, output, errors = self._main(['-d', prgFile, '-l', labelsFile])
            self.assertEqual(code, 0, errors)
            lines = [line.split(';')[0].strip() for line in output.splitlines()] # without the monitor comments
            for line in ['start:', 'start_loop:', 'bne start_loop']:
                self.assertIn(line, lines)

    def testOutputOrder(self):
        """With stderr in the same pipe as stdout (2>&1), .print output comes before the warnings, as on a terminal."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
        self.assertIn('$1000: #+..............', output.getvalue())

    def _prgFile(self, directory: str) -> str:
        """Write a .prg file with an rts at $1000, and return its name."""
        prgFile = os.path.join(directory, 'a.prg')
        with open(prgFile, 'wb') as f:
            f.write(bytes([0x00, 0x10, 0x60]))
        return prgFile

    def testDisassembleToFile(self):
        """-d disassembles to the -o file, also with the long option names."""
        with tempfile.TemporaryDirectory() as directory:
            prgFile, asmFile = self._prgFile(directory), os.path.join(directory, 'a.asm')
            for arguments in [['-d', prgFile, '-o', asmFile], ['--disassemble', prgFile, '--output', asmFile]]:
                with self.subTest(arguments=arguments[0]):
                    code, output, errors = self._main(arguments)
                    self.assertEqual(code, 0)
                    with open(asmFile) as f:
                        self.assertEqual(f.read(), disassemble.disassembleFile(prgFile))
                    os.remove(asmFile)

    def testDisassemblePrints(self):
        """Without -o, only the source is printed."""
        with tempfile.TemporaryDirectory() as directory:
            prgFile = self._prgFile(directory)
            code, output, errors = self._main(['-d', prgFile])
            self.assertEqual(code, 0)
            self.assertEqual(output, disassemble.disassembleFile(prgFile))
            self.assertEqual(errors, '')

    def testSourceNotUtf8(self):
        """A source file that is not UTF-8, also when imported, gives an error with its name and line."""
        with tempfile.TemporaryDirectory() as directory:
            badFile, importFile = os.path.join(directory, 'bad.asm'), os.path.join(directory, 'import.asm')
            with open(badFile, 'wb') as f:
                f.write(b'nop\n; caf\xe9\n')
            with open(importFile, 'w') as f:
                f.write('.import "bad.asm"\n')
            for asmFile in [badFile, importFile]:
                with self.subTest(asmFile=asmFile):
                    code, output, errors = self._main([asmFile])
                    self.assertEqual(code, 1)
                    self.assertEqual(errors, f'error: Not valid UTF-8 on line 2: "{badFile}"\n')

    def testDisassembleMissingFile(self):
        """A file that can't be read exits with 1, and an error on stderr."""
        with tempfile.TemporaryDirectory() as directory:
            missingFile = os.path.join(directory, 'missing.prg')
            code, output, errors = self._main(['-d', missingFile, '-o', os.path.join(directory, 'a.asm')])
            self.assertEqual(code, 1)
            self.assertIn(f'error: No such file or directory: "{missingFile}"', errors)

    def testDisassembleInvalidLabels(self):
        """A labels file that can't be used exits with 1, and an error with its name on stderr."""
        with tempfile.TemporaryDirectory() as directory:
            prgFile, labelsFile = self._prgFile(directory), os.path.join(directory, 'labels.py')
            for content, exception in [(b'x = (\n', 'SyntaxError'), (b'x = nope\n', 'NameError'), (b'\xff\n', 'UnicodeDecodeError')]:
                with self.subTest(content=content):
                    with open(labelsFile, 'wb') as f:
                        f.write(content)
                    code, output, errors = self._main(['-d', prgFile, '-l', labelsFile])
                    self.assertEqual(code, 1)
                    self.assertIn(f'error: Invalid labels file ({exception}: ', errors)
                    self.assertIn(f'"{labelsFile}"', errors)

    def testDisassembleMissingLabels(self):
        """A labels file that doesn't exist gives the usual error for a missing file."""
        with tempfile.TemporaryDirectory() as directory:
            labelsFile = os.path.join(directory, 'missing.py')
            code, output, errors = self._main(['-d', self._prgFile(directory), '-l', labelsFile])
            self.assertEqual(code, 1)
            self.assertIn(f'error: No such file or directory: "{labelsFile}"', errors)

    def testDisassembleMissingFolder(self):
        """A file that can't be written exits with 1, and an error on stderr."""
        with tempfile.TemporaryDirectory() as directory:
            missingFolder = os.path.join(directory, 'missing', 'a.asm')
            code, output, errors = self._main(['-d', self._prgFile(directory), '-o', missingFolder])
            self.assertEqual(code, 1)
            self.assertIn(f'error: No such file or directory: "{missingFolder}"', errors)

    def testPackageImports(self):
        """Importing the package keeps its modules inside it, e.g. code64.cpu, not a top level cpu."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        modules = subprocess.run([sys.executable, '-c', 'import sys, code64.main; print(*sorted(sys.modules))'],
                                 cwd=root, capture_output=True, text=True, check=True).stdout.split()
        self.assertIn('code64.cpu', modules)
        self.assertNotIn('cpu', modules)
        self.assertNotIn('assemble', modules)

    def testRunAsModule(self):
        """python -m code64 runs the command line, the same as python -m code64.main."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for module in ['code64', 'code64.main']:
            with self.subTest(module=module):
                output = subprocess.run([sys.executable, '-m', module, '--version'], cwd=root, capture_output=True, text=True)
                self.assertEqual((output.returncode, output.stderr), (0, ''))
                self.assertEqual(output.stdout, f'Code64 v{__version__} (c) Morten Perriard 2021-2026\n')

    def testPublicApi(self):
        """The package exports assembleFile, disassembleFile and Context, and its modules stay importable."""
        import code64
        self.assertEqual(sorted(code64.__all__), ['Context', 'assembleFile', 'disassembleFile'])
        self.assertIs(code64.assembleFile, assemble.assembleFile)
        self.assertIs(code64.disassembleFile, disassemble.disassembleFile)
        self.assertIs(code64.Context, Context)
        self.assertIs(code64.disassemble, disassemble) # the module, not the function of the same name


if __name__ == '__main__':
    unittest.main()
