#! /usr/bin/env python3
"""The assembler: assembles source files into memory, in multiple passes."""

import contextlib
import io
import os
import tempfile
import unittest
import glob

#--
import pathlib, sys
sys.path.append(str(pathlib.Path(__file__).parent.absolute()))
#--

import assignment
import cpu
import directives
import evaluate
import generators
import instructions
import lexer
import text
from context import Context
from cpu import lo, hi


def _saveMemoryToPrg(start: int, memory: dict, fileName: str):
    """Save a .prg file: the load address, then memory from start to end."""
    f = open(fileName, 'wb')

    ints = [lo(start), hi(start)]

    if len(memory) > 0:
        first = min(memory.keys())
        last = max(memory.keys())
        for i in range(first, last+1):
            ints.append(memory[i] if i in memory else 0)

    f.write(bytes(ints))
    f.close()


def multiPass(inFile, outFile) -> bool:
    """Assemble inFile, and save it to outFile if there are no errors.

    Passes are repeated until the output stops changing (max. 9), so
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
    
    defaultOrigin = 0x1000

    n = 1
    while n<10:
        # a new context each pass, but symbols are kept from the last pass
        symbols['_'] = defaultOrigin
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
                multiPass.chunks[fileName] = list(lexer.chunkSplit(lexer.tokenizeFile(fileName)))

            allChunks = multiPass.chunks[fileName]

            if lineIndex < len(allChunks):
                
                chunk = allChunks[lineIndex]
                advance = True

                # label
                if len(chunk) >= 2 and chunk[1].string == ':':
                    label = chunk[0].string
                    if label in context.labels:
                        context.reportError(f'Label was already defined: "{label}"')
                    context.setSymbol(label, context.symbols['_'])
                    context.labels.add(label)
                    chunk = chunk[2:]

                if len(chunk) >= 1 and cpu.isMnemonic(chunk[0].string):
                    instructions.assemble(chunk, context)

                elif len(chunk) >= 3 and chunk[1].string == '=':
                    assignment.assemble(chunk, context)

                elif len(chunk) >= 2 and chunk[0].string == '.':
                    advance = directives.assemble(chunk, context)
            
                elif len(chunk) >= 2 and chunk[0].string == '@':
                    advance = generators.assemble(chunk, context, multiPass.chunks)

                elif len(chunk) > 0:
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
        n += 1

    # print warning and errors
    context.printAsmReport()    

    # only save if no errors
    anyErrors = len(context.errors) > 0
    if not anyErrors:

        # print memory use
        context.printMemoryUse()

        if outFile is not None:
            print(f'Saving program: {outFile}')
            start = defaultOrigin
            if len(context.memory) > 0:
                start = min(context.memory.keys())
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
            ('i = "a"\n.repeat "i", 2\n.endr\n', 'test.asm:2 error: Symbol "i" cannot change type from str to int'),
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
                             ('.py "def emit(): pass"\n@emit()\n', 2)]:     # forgot to return the code
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertIn(f'test.asm:{line} error:', output)

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
            ('.endr\n',                              'test.asm:1 error: End repeat without matching repeat'),
            ('.py "1/0"\n',                          'test.asm:1 error: Failed to execute python code: "1/0" (ZeroDivisionError: division by zero)'),
            ('.import "nothere.py"\n',               'test.asm:1 error: Failed to execute python code: "nothere.py" (FileNotFoundError: '),
            ('.binary "nothere.bin"\n',              'test.asm:1 error: File not found: "nothere.bin"'),
            ('.music "nothere.sid", "M"\n',          'test.asm:1 error: File not found: "nothere.sid"'),
            ('.bitmap "nothere.bmp", 1\n',           'test.asm:1 error: File not found: "nothere.bmp"'),
            ('.music "nothere.sid", "M"\n',          'test.asm:1 error: Music not loaded: "nothere.sid"'),
            ('.bitmap "nothere.bmp", 1\n',           'test.asm:1 error: Image not loaded: "nothere.bmp"'),
            ('.zpbyte "a"\n.zpbyte "a"\n',           'test.asm:2 error: Label was already defined: "a"'),
            ('.repeat "i", 127\n.zpword "v{i}"\n.endr\n.zpbyte "last"\n', # $02-$ff is full
                                                     'test.asm:4 error: No space for zero page variable: "last"'),
            ('hello world\n',                        'test.asm:1 error: Invalid syntax'),
        ]:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertIn(message, output)

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
