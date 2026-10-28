#! /usr/bin/env python3
"""The assembler: assembles source files into memory, in multiple passes."""

import contextlib
import io
import os
import tempfile
import unittest
import glob

from . import assignment
from . import cpu
from . import directives
from . import evaluate
from . import generators
from . import instructions
from . import lexer
from . import text
from .context import Context
from .cpu import lo, hi

# max passes until all symbols should have been resolved
MAX_PASSES = 42

DEFAULT_ORIGIN = 0x1000 # the address when there is no .org


def _saveMemoryToPrg(start: int, memory: dict, fileName: str):
    """Save a .prg file: the load address, then memory from start to end."""
    data = [memory.get(address, 0) for address in range(min(memory), max(memory) + 1)] if memory else []
    with open(fileName, 'wb') as f:
        f.write(bytes([lo(start), hi(start)] + data))


def multiPass(inFile, outFile) -> bool:
    """Assemble inFile, and save it to outFile if there are no errors.

    Passes are repeated until the output stops changing (max. MAX_PASSES), so
    labels can be used before they are defined. Returns True on errors.
    """
    path = os.path.dirname(inFile)

    symbols = {'lo': lo, 'hi': hi,
        'ENCODING_SCREEN_UPPER': text.ENCODING_SCREEN_UPPER,
        'ENCODING_SCREEN_MIXED': text.ENCODING_SCREEN_MIXED,
        'ENCODING_PETSCII_UPPER': text.ENCODING_PETSCII_UPPER,
        'ENCODING_PETSCII_MIXED': text.ENCODING_PETSCII_MIXED}

    root = os.path.abspath(os.path.dirname(__file__))
    imports = sorted(glob.glob(os.path.join(root, 'imports/*.py')))

    importNames = ', '.join(map(lambda x: os.path.basename(x), imports))
    print(f'Importing: {importNames}')

    for fileName in imports:
        try:
            with open(fileName) as f:
                py = f.read()
            exec(py, symbols)
        except Exception as exception:
            print(f"failed to import: {fileName} ({type(exception).__name__}: {exception})")

    lastMemory = {}
    
    for _ in range(MAX_PASSES):
        # a new context each pass, but symbols are kept from the last pass
        symbols['_'] = DEFAULT_ORIGIN
        context = Context(symbols)
        context.path = path
        context.pushReadPointer( (inFile, 0) )

        # assemble line by line, from the file on top of the read pointer stack
        while True:
            readPointer = context.readPointer()
            if readPointer is None: break

            fileName, lineIndex = readPointer
            
            if not fileName in multiPass.chunks: # tokenized once, for all passes
                print(f'Loading: {fileName}')
                multiPass.chunks[fileName] = list(lexer.splitByNewline(lexer.tokenizeFile(fileName)))

            allChunks = multiPass.chunks[fileName]

            if lineIndex < len(allChunks):
                
                lineTokens = allChunks[lineIndex]
                advance = True

                # label
                if len(lineTokens) >= 2 and lineTokens[1].string == ':':
                    label = lineTokens[0].string
                    if label in context.labels:
                        context.reportError(f'Label was already defined: "{label}"')
                    context.setSymbol(label, context.symbols['_'])
                    context.labels.add(label)
                    lineTokens = lineTokens[2:]

                if len(lineTokens) >= 1 and cpu.isMnemonic(lineTokens[0].string):
                    instructions.assemble(lineTokens, context)

                elif len(lineTokens) >= 3 and lineTokens[1].string == '=':
                    assignment.assemble(lineTokens, context)

                elif len(lineTokens) >= 2 and lineTokens[0].string == '.':
                    advance = directives.assemble(lineTokens, context, multiPass.chunks)
            
                elif len(lineTokens) >= 2 and lineTokens[0].string == '@':
                    advance = generators.assemble(lineTokens, context, multiPass.chunks)

                elif len(lineTokens) > 0:
                    context.reportError(f'Invalid syntax')

                if advance:
                    context.advanceReadPointer()
                
            else:
                context.popReadPointer() # end of file, back to the importing file
                
        # done when there are no errors, and the output is unchanged
        if len(context.errors) == 0 and context.memory == lastMemory:
            break

        # prepare for next pass
        lastMemory = dict(context.memory)

    # print .print values, warnings and errors, from the last pass
    for message in context.printed + context.warnings + context.errors:
        print(message)

    # only save if no errors
    anyErrors = len(context.errors) > 0
    if not anyErrors:

        # print memory use
        context.printMemoryUse()

        if outFile is not None:
            print(f'Saving program: {outFile}')
            start = min(context.memory, default=DEFAULT_ORIGIN)
            _saveMemoryToPrg(start, context.memory, outFile)

    return anyErrors
multiPass.chunks = {} # function static variable
        

################################################################################

class TestAssemble(unittest.TestCase):

    def _assemble(self, source: str):
        """Assemble source, and return (anyErrors, printed output)."""
        with tempfile.TemporaryDirectory() as directory:
            fileName = os.path.join(directory, 'test.asm')
            with open(fileName, 'w') as f:
                f.write(source)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                anyErrors = multiPass(fileName, None)
        return anyErrors, output.getvalue()

    def testDuplicateLabel(self):
        anyErrors, output = self._assemble('a: nop\na: nop\n')
        self.assertTrue(anyErrors)
        self.assertIn('test.asm:2 error: Label was already defined: "a"', output)

    def testConstants(self):
        """Upper case symbols are constants, other symbols can be assigned again."""
        anyErrors, output = self._assemble('MY_VALUE = 123\nMY_VALUE = 123\n'   # same value again is ok
                                           'myValue = 1\nmyValue = 2\n'          # not constants
                                           'MyValue = 1\nMyValue = 2\n')
        self.assertFalse(anyErrors, output)

        # only the assignment that changes the value is an error
        anyErrors, output = self._assemble('MY_VALUE = 123\nMY_VALUE = 124\n')
        errors = [line.split('/')[-1] for line in output.splitlines() if ' error: ' in line]
        self.assertEqual(errors, ['test.asm:2 error: Constant "MY_VALUE" cannot be changed from 123 to 124'])

        # built-in constants, from the imports folder
        anyErrors, output = self._assemble('VIC_BORDER_COLOR = $d020\n')
        self.assertFalse(anyErrors, output)
        anyErrors, output = self._assemble('VIC_BORDER_COLOR = 1\n')
        self.assertIn('test.asm:1 error: Constant "VIC_BORDER_COLOR" cannot be changed from 53280 to 1', output)

    def testSymbolTypes(self):
        """A symbol keeps its type, e.g. an int can't become a str."""
        anyErrors, output = self._assemble('x = 1\nx = 2\nname = "a"\nname = "b"\nf = lambda v: v\nf = lambda v: v + 1\n')
        self.assertFalse(anyErrors, output)

        for source, message in [
            ('x = 1\nx = "a"\n',          'test.asm:2 error: Symbol "x" cannot change type from int to str'),
            ('f = lambda v: v\nf = 1\n',  'test.asm:2 error: Symbol "f" cannot change type from function to int'),
            ('x = "a"\nx: nop\n',         'test.asm:2 error: Symbol "x" cannot change type from str to int'),
            ('.zpbyte "x"\nx = "a"\n',    'test.asm:2 error: Symbol "x" cannot change type from int to str'),
            # the math module is protected
            ('pi = 3\n',                  'test.asm:1 error: Symbol "pi" cannot change type from float to int'),
            ('e: nop\n',                  'test.asm:1 error: Symbol "e" cannot change type from float to int'),
            ('sin: nop\n',                'test.asm:1 error: Symbol "sin" cannot change type from builtin_function_or_method to int'),
        ]:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertIn(message, output)

    def testByteWordString(self):
        """A string is not a .byte or .word value, even if a symbol has that name."""
        for source in ['.byte "B"', '.word "B"', '.bytefill 1, "x: \'B\'"', '.wordfill 1, "x: \'B\'"']:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(f'B = 5\n{source}\n')
                self.assertIn('test.asm:2 error:', output)

    def testGeneratorNotString(self):
        """A generator must return assembly code as a string, or it is an error."""
        for source, line in [('@nop\n', 1),                                # forgot the parentheses
                             ('.python\ndef emit(): pass\n.end\n@emit()\n', 4)]: # forgot to return the code
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertIn(f'test.asm:{line} error:', output)

    def testForLoopLimit(self):
        """A .for loop whose condition is never false is an error, not a hang."""
        from unittest import mock
        with mock.patch.object(directives, 'MAX_ITERATIONS', 100): # the real limit takes seconds
            anyErrors, output = self._assemble('.for a=0, a>=0, a+=1\n.end\n')
        self.assertIn('test.asm:2 error: For loop did not end after 100 iterations', output)

    def testSaveMemoryToPrg(self):
        """A .prg file is the load address, then the bytes from the lowest to the highest address, gaps as 0."""
        for memory, expected in [({0x1000: 1, 0x1002: 3}, [0x00, 0x10, 1, 0, 3]), ({}, [0x00, 0x10])]:
            with self.subTest(memory=memory), tempfile.TemporaryDirectory() as directory:
                fileName = os.path.join(directory, 'test.prg')
                _saveMemoryToPrg(0x1000, memory, fileName)
                with open(fileName, 'rb') as f:
                    self.assertEqual(list(f.read()), expected)

    def testPrgStart(self):
        """The load address is the lowest address used, or $1000 if nothing is stored."""
        for source, expected in [('.org $2000\n.byte 1\n.org $1fff\n.byte 2\n', [0xff, 0x1f, 2, 1]), ('', [0x00, 0x10])]:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                asmFile, prgFile = os.path.join(directory, 'test.asm'), os.path.join(directory, 'test.prg')
                with open(asmFile, 'w') as f:
                    f.write(source)
                with contextlib.redirect_stdout(io.StringIO()):
                    multiPass(asmFile, prgFile)
                with open(prgFile, 'rb') as f:
                    self.assertEqual(list(f.read()), expected)

    def testMessages(self):
        """Errors and warnings, each reported at the line that causes it."""
        for source, message in [
            ('.org $1000\n.byte 1\n.org $1000\n.byte 2\n', 'test.asm:4 warning: $1000 is overwritten ($01 to $02)'),
            ('.org $ffff\n.byte 1, 2\n',            'test.asm:2 error: Destination memory address out of range: $10000'),
            ('jmp ($10ff)\n',                        'test.asm:1 warning: Indirect address located on page boundary: $10ff'),
            ('stx $100,y\n',                         'test.asm:1 error: Unknown instruction or address mode: stx 0x100,y'),
            ('.text "a"\n',                          'test.asm:1 error: Unknown character "a" in text "a"'),
            ('.align 0\n',                           'test.asm:1 error: Alignment must be positive: 0'),
            ('.print 1 + 1\n',                       '\n2\n'),
            ('.warning "careful"\n',                 'test.asm:1 warning: careful'),
            ('.error "stop"\n',                      'test.asm:1 error: stop'),
            ('.end\n',                               'test.asm:1 error: End without matching repeat, for or if'),
            ('.else\n',                              'test.asm:1 error: Else without matching if'),
            ('.if 0\n.else\n.else\n.end\n',          'test.asm:3 error: Else already used for this if'),
            ('.if 0\n',                              'test.asm:1 error: If without matching end'),
            ('.if 1\n.else\n',                       'test.asm:2 error: Else without matching end'),
            ('.repeat "i", 2\n.end\n',               'test.asm:1 error: Expected .repeat count'), # the old syntax
            ('.repeat 0\n',                          'test.asm:1 error: Repeat without matching end'),
            ('.for a=0, a<1\n',                      'test.asm:1 error: Expected .for initial, condition, step'),
            ('.for a=0, a<0, a+=1\n',                'test.asm:1 error: For without matching end'),
            ('.for a=, a<1, a+=1\n.end\n',           'test.asm:1 error: Failed to execute python code: "a="'),
            ('.for a=0, a<1, b+=1\n.end\n',          'test.asm:2 error: Failed to execute python code: "b+=1"'),
            ('.python\n1/0\n.end\n',                    'test.asm:1 error: Failed to execute python code: "1/0" (ZeroDivisionError: division by zero)'),
            ('.python\nx = 1\n',                         'test.asm:1 error: Invalid directive: .python'), # no .end
            ('.python "1/0"\n',                      'test.asm:1 error: Invalid syntax'), # only python blocks
            ('.import "nothere.py"\n',               'test.asm:1 error: Failed to execute python code: "nothere.py" (FileNotFoundError: '),
            ('.org undefinedSymbol\n',               'test.asm:1 error: Invalid directive: .org undefinedSymbol'),
            ('.binary "nothere.bin"\n',              'test.asm:1 error: File not found: "nothere.bin"'),
            ('.music "nothere.sid", "M"\n',          'test.asm:1 error: File not found: "nothere.sid"'),
            ('.bitmap "nothere.bmp", 1\n',           'test.asm:1 error: File not found: "nothere.bmp"'),
            ('.music "nothere.sid", "M"\n',          'test.asm:1 error: Music not loaded: "nothere.sid"'),
            ('.bitmap "nothere.bmp", 1\n',           'test.asm:1 error: Image not loaded: "nothere.bmp"'),
            ('.zpbyte "a"\n.zpbyte "a"\n',           'test.asm:2 error: Label was already defined: "a"'),
            ('.for i=0, i<127, i+=1\n.zpword "v{i}"\n.end\n.zpbyte "last"\n', # $02-$ff is full
                                                     'test.asm:4 error: No space for zero page variable: "last"'),
            ('hello world\n',                        'test.asm:1 error: Invalid syntax'),
        ]:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertIn(message, output)

    def testPrint(self):
        """.print prints once, after the last pass, so values are final, even with errors."""
        anyErrors, output = self._assemble('.print "start", later\njmp later\nlater: rts\n') # later is $1003
        self.assertFalse(anyErrors, output)
        self.assertEqual(output.count('start\n'), 1, output)
        self.assertIn('start\n4099\n', output)
        anyErrors, output = self._assemble('.print "before"\n.error "stop"\n')
        self.assertTrue(anyErrors)
        self.assertIn('before\n', output)

    def testBrokenBuiltinImport(self):
        """A built-in import that fails is reported, and assembly continues."""
        from unittest import mock
        with tempfile.TemporaryDirectory() as directory:
            fileName = os.path.join(directory, 'broken.py')
            with open(fileName, 'w') as f:
                f.write('1/0\n')
            with mock.patch('glob.glob', return_value=[fileName]): # instead of the imports folder
                anyErrors, output = self._assemble('nop\n')
        self.assertFalse(anyErrors)
        self.assertIn(f'failed to import: {fileName} (ZeroDivisionError: division by zero)', output)

if __name__ == '__main__':
    unittest.main()
