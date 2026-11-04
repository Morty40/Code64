#! /usr/bin/env python3
"""The assembler: assembles source files into memory, in multiple passes."""

import contextlib
import io
import os
import struct
import tempfile
import unittest
import glob

from . import assignment
from . import cpu
from . import directives
from . import generators
from . import instructions
from . import lexer
from . import text
from .context import Context
from .cpu import lo, hi

# max passes until all symbols should have been resolved
MAX_PASSES = 42

DEFAULT_ORIGIN = 0x1000 # the address when there is no .org

TARGETS = ('c128', 'c16', 'c64', 'plus4', 'vic20') # the folders in imports/target


def assembleFile(inFile: str, outFile: str = None, target: str = None) -> Context:
    """Assemble inFile, and save it to outFile, if given and there are no errors. Returns the
    context of the last pass: memory, symbols, messages and errors. The target is one of TARGETS,
    whose imports are added to the generic ones.
    Raises OSError if inFile can't be read, or outFile can't be written, and ValueError for an unknown target.

    Passes are repeated until the output stops changing (max. MAX_PASSES), so
    labels can be used before they are defined.
    """
    if target is not None and target not in TARGETS:
        raise ValueError(f'Unknown target: {target}')

    path = os.path.dirname(inFile)

    symbols = {'lo': lo, 'hi': hi,
        'ENCODING_SCREEN_UPPER': text.ENCODING_SCREEN_UPPER,
        'ENCODING_SCREEN_MIXED': text.ENCODING_SCREEN_MIXED,
        'ENCODING_PETSCII_UPPER': text.ENCODING_PETSCII_UPPER,
        'ENCODING_PETSCII_MIXED': text.ENCODING_PETSCII_MIXED,
        'SOURCE_FOLDER': path} # for generators that read files

    root = os.path.abspath(os.path.dirname(__file__))
    imports = sorted(glob.glob(os.path.join(root, 'imports/*.py')))
    if target:
        imports += sorted(glob.glob(os.path.join(root, 'imports/target', target, '*.py')))

    for fileName in imports:
        with open(fileName) as f:
            exec(compile(f.read(), fileName, 'exec'), symbols) # the file name shows in tracebacks

    lastMemory = {}
    lastReferences = set()
    chunks = {} # the tokenized files and generated code, by name: tokenized once, for all passes

    for _ in range(MAX_PASSES):
        # a new context each pass, but symbols are kept from the last pass
        symbols['_'] = DEFAULT_ORIGIN
        context = Context(symbols)
        context.path = path
        context.lastReferences = lastReferences
        context.pushReadPointer( (inFile, 0) )

        # assemble line by line, from the file on top of the read pointer stack
        while True:
            readPointer = context.readPointer()
            if readPointer is None: break

            fileName, lineIndex = readPointer

            if not fileName in chunks:
                chunks[fileName] = list(lexer.splitByNewline(lexer.tokenizeFile(fileName)))

            allChunks = chunks[fileName]

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
                    advance = directives.assemble(lineTokens, context, chunks)

                elif len(lineTokens) >= 2 and lineTokens[0].string == '@':
                    advance = generators.assemble(lineTokens, context, chunks)

                elif len(lineTokens) > 0:
                    context.reportError(f'Invalid syntax')

                if advance:
                    context.advanceReadPointer()

            else:
                context.popReadPointer() # end of file, back to the importing file

        directives.reportOpenBlocks(context)

        # done when there are no errors, and the output and references are unchanged
        if len(context.errors) == 0 and context.memory == lastMemory and context.references == lastReferences:
            break

        # prepare for next pass
        lastMemory = dict(context.memory)
        lastReferences = context.references

    # save the .prg: the load address, the lowest address used or DEFAULT_ORIGIN, then memory from there to the end
    if outFile and not context.errors:
        memory = context.memory
        start = min(memory, default=DEFAULT_ORIGIN)
        data = [memory.get(address, 0) for address in range(start, max(memory) + 1)] if memory else []
        with open(outFile, 'wb') as f:
            f.write(bytes([lo(start), hi(start)] + data))
    return context


################################################################################

class TestAssemble(unittest.TestCase):
    """Tests of assembling source files: messages, files, and the .prg output."""

    def _assemble(self, source: str):
        """Assemble source, and return (anyErrors, printed output and messages)."""
        with tempfile.TemporaryDirectory() as directory:
            fileName = os.path.join(directory, 'test.asm')
            with open(fileName, 'w') as f:
                f.write(source)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                context = assembleFile(fileName)
        messages = ''.join(f'{message}\n' for message in context.printed + context.warnings + context.errors)
        return len(context.errors) > 0, output.getvalue() + messages

    def testDuplicateLabel(self):
        """A label can only be defined once."""
        anyErrors, output = self._assemble('a: nop\na: nop\n')
        self.assertTrue(anyErrors)
        self.assertIn('test.asm:2: error: Label was already defined: "a"', output)

    def testConstants(self):
        """Only all upper case symbols are constants, including the built-in ones."""
        anyErrors, output = self._assemble('myValue = 1\nmyValue = 2\nMyValue = 1\nMyValue = 2\n')
        self.assertFalse(anyErrors, output)

        # built-in constants, from the imports folder
        anyErrors, output = self._assemble('STACK_ADDRESS = $100\n')
        self.assertFalse(anyErrors, output)
        anyErrors, output = self._assemble('STACK_ADDRESS = 1\n')
        self.assertIn('test.asm:1: error: Constant "STACK_ADDRESS" cannot be changed from 256 to 1', output)

    def testSymbolTypes(self):
        """A symbol keeps its type, e.g. an int can't become a str."""
        anyErrors, output = self._assemble('x = 1\nx = 2\nname = "a"\nname = "b"\nf = lambda v: v\nf = lambda v: v + 1\n')
        self.assertFalse(anyErrors, output)

        for source, message in [
            ('x = 1\nx = "a"\n',          'test.asm:2: error: Symbol "x" cannot change type from int to str'),
            ('f = lambda v: v\nf = 1\n',  'test.asm:2: error: Symbol "f" cannot change type from function to int'),
            ('x = "a"\nx: nop\n',         'test.asm:2: error: Symbol "x" cannot change type from str to int'),
            ('.zpbyte "x"\nx = "a"\n',    'test.asm:2: error: Symbol "x" cannot change type from int to str'),
            # the math module is protected
            ('pi = 3\n',                  'test.asm:1: error: Symbol "pi" cannot change type from float to int'),
            ('e: nop\n',                  'test.asm:1: error: Symbol "e" cannot change type from float to int'),
            ('sin: nop\n',                'test.asm:1: error: Symbol "sin" cannot change type from builtin_function_or_method to int'),
        ]:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertIn(message, output)

    def testByteWordString(self):
        """A string is not a .byte or .word value, even if a symbol has that name."""
        for source in ['.byte "B"', '.word "B"', '.bytefill 1, "x: \'B\'"', '.wordfill 1, "x: \'B\'"']:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(f'B = 5\n{source}\n')
                self.assertIn('test.asm:2: error: Expected an int value instead of: "\'B\'"', output)

    def testGeneratorNotString(self):
        """A generator must return assembly code as a string, or it is an error."""
        anyErrors, output = self._assemble('.python\ndef emit(): pass\n.end\n@emit()\n') # forgot to return the code
        self.assertIn('test.asm:4: error: Generator must return a string, not NoneType', output)

    def testForLoopLimit(self):
        """A .for loop whose condition is never false is an error, not a hang."""
        from unittest import mock
        with mock.patch.object(directives, 'MAX_ITERATIONS', 100): # the real limit takes seconds
            anyErrors, output = self._assemble('.for a=0, a>=0, a+=1\n.end\n')
        self.assertIn('test.asm:2: error: For loop did not end after 100 iterations', output)

    def testPrgStart(self):
        """A .prg file is the load address, the lowest address used or $1000 if nothing is stored,
        then the bytes from there to the highest address, gaps as 0."""
        for source, expected in [('.org $2000\n.byte 1\n.org $1fff\n.byte 2\n', [0xff, 0x1f, 2, 1]),
                                 ('.org $1000\n.byte 1\n.org $1002\n.byte 3\n', [0x00, 0x10, 1, 0, 3]),
                                 ('', [0x00, 0x10])]:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                asmFile, prgFile = os.path.join(directory, 'test.asm'), os.path.join(directory, 'test.prg')
                with open(asmFile, 'w') as f:
                    f.write(source)
                with contextlib.redirect_stdout(io.StringIO()):
                    assembleFile(asmFile, prgFile)
                with open(prgFile, 'rb') as f:
                    self.assertEqual(list(f.read()), expected)

    def testFilePaths(self):
        """.binary and @importMusic read files relative to the folder of the main source file, not the current folder."""
        with tempfile.TemporaryDirectory() as directory:
            sid = struct.pack('>4sHHHHHHHL32s32s32sHBBBB', b'PSID', 2, 0x7c, 0x2000, 0x2000, 0x2003, 1, 1, 0, b'', b'', b'', 0, 0, 0, 0, 0)
            for name, data in [('paths.bin', b'\x01\x02'), ('paths.sid', sid + b'\x60')]:
                with open(os.path.join(directory, name), 'wb') as f:
                    f.write(data)
            asmFile, prgFile = os.path.join(directory, 'paths.asm'), os.path.join(directory, 'paths.prg')
            with open(asmFile, 'w') as f:
                f.write('.binary "paths.bin"\n.org M_LOAD\n@importMusic("paths.sid", "M")\n')
            context = assembleFile(asmFile, prgFile, target='c64')
            self.assertEqual(context.errors, [])
            self.assertEqual((context.memory[0x1000], context.memory[0x1001], context.memory[0x2000]), (0x01, 0x02, 0x60))

    def testBinaryOffsetLength(self):
        """.binary stores the whole file, or from an offset, or from an offset with a length."""
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, 'data.bin'), 'wb') as f:
                f.write(bytes([1, 2, 3, 4, 5]))
            asmFile = os.path.join(directory, 'data.asm')
            for source, expected in [('.binary "data.bin"\n',       [1, 2, 3, 4, 5]),
                                     ('.binary "data.bin", 2\n',    [3, 4, 5]),
                                     ('.binary "data.bin", 1, 2\n', [2, 3])]:
                with self.subTest(source=source):
                    with open(asmFile, 'w') as f:
                        f.write(source)
                    context = assembleFile(asmFile)
                    self.assertEqual(context.errors, [])
                    self.assertEqual(list(context.memory.values()), expected)

    def testNoPrgOnErrors(self):
        """The .prg file is only saved when there are no errors."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, prgFile = os.path.join(directory, 'error.asm'), os.path.join(directory, 'error.prg')
            with open(asmFile, 'w') as f:
                f.write('.byte 1\n.error "stop"\n')
            with contextlib.redirect_stdout(io.StringIO()):
                context = assembleFile(asmFile, prgFile)
            self.assertEqual(len(context.errors), 1)
            self.assertFalse(os.path.exists(prgFile))

    def _assertMessages(self, cases: list):
        """Assemble each source, and check the output has its message, at the line that causes it."""
        for source, message in cases:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertIn(message, output)

    def testMemoryMessages(self):
        """Storing outside memory, or over bytes already stored."""
        self._assertMessages([
            ('.org $1000\n.byte 1\n.org $1000\n.byte 2\n', 'test.asm:4: warning: $1000 is overwritten ($01 to $02)'),
            ('.org $ffff\n.byte 1, 2\n',                   'test.asm:2: error: Destination memory address out of range: $10000'),
        ])

    def testValueMessages(self):
        """Directive and instruction values that are unknown or not allowed."""
        self._assertMessages([
            ('.text "a"\n',                          'test.asm:1: error: Unknown character "a" in text "a"'),
            ('.align 0\n',                           'test.asm:1: error: Alignment must be positive: 0'),
            ('.org undefinedSymbol\n',               'test.asm:1: error: Invalid directive: .org undefinedSymbol'),
            ('hello world\n',                        'test.asm:1: error: Invalid syntax'),
            ('lda #MAX_Speed\n',                     'test.asm:1: error: Name \'MAX_Speed\' is not defined: "MAX_Speed"'), # only the first letter capitalized
            ('.bytefill 1, "x: MAX_Speed"\n',        'test.asm:1: error: Name \'MAX_Speed\' is not defined\n'),
        ])

    def testReportMessages(self):
        """.print, .warning and .error report their text."""
        self._assertMessages([
            ('.print 1 + 1\n',                       '2\n'),
            ('.warning "careful"\n',                 'test.asm:1: warning: careful'),
            ('.error "stop"\n',                      'test.asm:1: error: stop'),
        ])

    def testAssertMessages(self):
        """A failed .assert, and an .assert with the wrong arguments."""
        self._assertMessages([
            ('.assert 2 > 3\n',                       'test.asm:1: error: Assertion failed'),
            ('.assert 2 > 3, "Something is wrong"\n', 'test.asm:1: error: Something is wrong'),
            ('.assert\n',                             'test.asm:1: error: Invalid directive: .assert'),
            ('.assert 2 > 3, 42\n',                   'test.asm:1: error: Invalid directive: .assert'), # the message must be a string
        ])

    def testBlockMessages(self):
        """Blocks that are not opened or closed correctly."""
        self._assertMessages([
            ('.end\n',                               'test.asm:1: error: End without matching repeat, for or if'),
            ('.else\n',                              'test.asm:1: error: Else without matching if'),
            ('.if 0\n.else\n.else\n.end\n',          'test.asm:3: error: Else already used for this if'),
            ('.if 0\n',                              'test.asm:1: error: If without matching end'),
            ('.if 1\n.else\n',                       'test.asm:2: error: Else without matching end'),
            ('.repeat "i", 2\n.end\n',               'test.asm:1: error: Expected .repeat count'), # the count must be a number
            ('.repeat 0\n',                          'test.asm:1: error: Repeat without matching end'),
            ('.for a=0, a<1\n',                      'test.asm:1: error: Expected .for initial, condition, step'),
            ('.for a=0, a<0, a+=1\n',                'test.asm:1: error: For without matching end'),
            ('.python\nx = 1\n',                     'test.asm:1: error: Invalid directive: .python'), # no .end
        ])

    def testPythonMessages(self):
        """Python code that fails, in .for, .python and .import."""
        self._assertMessages([
            ('.for a=, a<1, a+=1\n.end\n',           'test.asm:1: error: Failed to execute python code: "a="'),
            ('.for a=0, a<1, b+=1\n.end\n',          'test.asm:2: error: Failed to execute python code: "b+=1"'),
            ('.python\n1/0\n.end\n',                 'test.asm:1: error: Failed to execute python code: "1/0" (ZeroDivisionError: division by zero)'),
            ('.python "1/0"\n',                      'test.asm:1: error: Invalid syntax'), # only python blocks
            ('.import "nothere.py"\n',               'test.asm:1: error: Failed to execute python code: "nothere.py" (FileNotFoundError: '),
        ])

    def testFileMessages(self):
        """Files that are not found."""
        self._assertMessages([
            ('.import "nothere.asm"\n',              'test.asm:1: error: File not found: "nothere.asm"'),
            ('.binary "nothere.bin"\n',              'test.asm:1: error: File not found: "nothere.bin"'),
        ])

    def testUnclosedBlockMessages(self):
        """A block without .end gives an error at the line that started it."""
        self._assertMessages([
            ('.repeat 2\nnop\n',               'test.asm:1: error: Repeat without matching end'),
            ('.for a=0, a<2, a+=1\nnop\n',      'test.asm:1: error: For without matching end'),
            ('.if 1\nnop\n',                   'test.asm:1: error: If without matching end'),
            ('.if 0\n.else\nnop\n',            'test.asm:2: error: If without matching end'), # at the .else
            ('nop\n.repeat 2\n.if 1\n.end\n',  'test.asm:2: error: Repeat without matching end'), # the outer block
        ])

    def _memory(self, source: str) -> list:
        """Assemble source without errors, and return the bytes in memory, by address."""
        with tempfile.TemporaryDirectory() as directory:
            fileName = os.path.join(directory, 'test.asm')
            with open(fileName, 'w') as f:
                f.write(source)
            context = assembleFile(fileName)
        self.assertEqual(context.errors, [])
        return [context.memory[address] for address in sorted(context.memory)]

    def testRef(self):
        """ref(label) is true if the label was referenced in the last pass, wherever and however."""
        block = '.if ref("t")\nt: .byte 8\n.end\n'
        chain = ''.join(f'.if ref("f{i}")\nf{i}: .word f{i + 1}\n.end\n' for i in range(20)) + '.if ref("f20")\nf20: .byte 9\n.end\n'
        for source, expected in [
            ('.byte 0\n' + block,                         [0]),                                # not referenced
            ('.word t\n' + block,                         [0x02, 0x10, 8]),
            (block + '.word t\n',                         [8, 0x00, 0x10]),                    # referenced after the block
            ('.word a\n.if ref("a")\na: .word b\n.end\n.if ref("b")\nb: .byte 9\n.end\n', [0x02, 0x10, 0x04, 0x10, 9]), # by a block
            ('.word f0\n' + chain,                        [0x02, 0x10] + [x for i in range(20) for x in (0x04 + 2 * i, 0x10)] + [9]),
            ('.byte 0\n' + chain,                         [0]),                                # nothing to start the chain
            ('.byte 0\n.if ref("s")\ns: .word s\n.end\n', [0]),                                # only by itself
            ('.byte 0\n.if ref("x")\nx: .word y\n.end\n.if ref("y")\ny: .word x\n.end\n', [0]), # only by each other
            ('.if 0\n.word t\n.end\n.byte 0\n' + block,   [0]),                                # not referenced if skipped
            ('.print "t"\n.byte 0\n' + block,             [0]),                                # text in a string
            ('.print \'t\'\n.byte 0\n' + block,           [0]),
            (".if ref('t')\nt: .byte 8\n.end\n.byte 0\n", [0]),                                # single quotes
            ('.print "{t}"\n' + block,                    [8]),                                # an expression in a string
            ('lda #lo(t)\n' + block,                      [0xa9, 0x02, 8]),                    # in an expression
            ('.bytefill 1, "x: lo(t)"\n' + block,         [0x01, 8]),                          # in a lambda
            ('@"jmp t"\n' + block,                        [0x4c, 0x03, 0x10, 8]),              # by generated code
            ('.python\ndef f():\n    return t\n.end\n.word f()\n' + block, [0x02, 0x10, 8]), # by Python code
            ('.if ref("t")\nt: .byte 8\n.else\n.byte 7\n.end\n',  [7]),                         # with .else
            ('.if ref("nothing")\n.byte 1\n.end\n',       []),
        ]:
            with self.subTest(source=source[:50]):
                self.assertEqual(self._memory(source), expected)

    def testRefOtherSymbols(self):
        """A symbol in a block that is not assembled is not defined."""
        self._assertMessages([
            ('.if ref("t")\nt: nop\nK = 2\n.end\nlda #K\n', "test.asm:5: error: Name 'K' is not defined"),
            ('.if ref("t")\nt: nop\n.zpbyte "v"\n.end\nlda v\n', "test.asm:5: error: Name 'v' is not defined"),
        ])

    def testOptional(self):
        """An optional block is only assembled if one of its global labels was referenced in the last pass."""
        table = '.optional\nmyTable: .byte 1, 2, 3\n.end\n'
        functions = '.optional\nfunc1: nop\nrts\nfunc2: nop\nrts\n.end\n'
        zeroPage = '.optional\n.zpbyte "xyz"\nfunc3: lda xyz\nrts\n.end\n'
        selfUse = '.optional\nfunc6: dex\nbne func6\nrts\n.end\n'
        for source, expected in [
            ('.byte 0\n' + table,                         [0]),                                # not referenced
            ('.word myTable\n' + table,                   [0x02, 0x10, 1, 2, 3]),
            (table + '.word myTable\n',                   [1, 2, 3, 0x00, 0x10]),              # referenced after the block
            ('.word func1\n' + functions,                 [0x02, 0x10, 0xea, 0x60, 0xea, 0x60]), # any of its labels
            ('.word func2\n' + functions,                 [0x04, 0x10, 0xea, 0x60, 0xea, 0x60]),
            ('.byte 0\n' + zeroPage,                      [0]),
            ('.word func3\n' + zeroPage,                  [0x02, 0x10, 0xa5, 0x02, 0x60]),
            ('.optional\n.byte 1, 2, 3\n.end\n',          []),                                 # no global labels
            ('.optional\n_x: .byte 1\n.end\n',            []),                                 # only a local label
            ('.byte 0\n' + selfUse,                       [0]),                                # only by itself
            ('jsr func6\n' + selfUse,                     [0x20, 0x03, 0x10, 0xca, 0xd0, 0xfd, 0x60]),
            ('.word a\n.optional\na: .word b\n.end\n.optional\nb: .byte 9\n.end\n', [0x02, 0x10, 0x04, 0x10, 9]), # by a block
            ('.print "myTable"\n.byte 0\n' + table,       [0]),                                # text in a string
            ('.word f\n.optional\n.if 1\nf: nop\n.end\n.end\n', [0x02, 0x10, 0xea]),          # in an .if in the block
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._memory(source), expected)

    def testOptionalNested(self):
        """A nested block is only assembled if the outer block is, and they each check their own labels."""
        nested = '.optional\nfunc4: .byte 4\n.optional\nfunc5: .byte 5\n.end\n.end\n'
        self.assertEqual(self._memory('.byte 0\n' + nested), [0])
        self.assertEqual(self._memory('.word func4\n' + nested), [0x02, 0x10, 4])
        self.assertEqual(self._memory('.word func4, func5\n' + nested), [0x04, 0x10, 0x05, 0x10, 4, 5])

    def testOptionalMessages(self):
        """An optional block needs an .end, and its symbols are not defined when it is left out."""
        self._assertMessages([
            ('.optional\nt: nop\n',                      'test.asm:1: error: Optional without matching end'),
            ('.optional\nf: nop\n.optional\ng: nop\n.end\n.end\njmp g\n', "test.asm:7: error: Name 'g' is not defined"),
            ('.optional\nf: nop\nK = 2\n.end\nlda #K\n',  "test.asm:5: error: Name 'K' is not defined"),
        ])

    def testOperatorsNextToOperands(self):
        """Number prefixes and local labels work next to any operator, without spaces."""
        for source, expected in [
            ('t = $20\nlda t-$10\n',         [0xa5, 0x10]),
            ('.byte -$10\n',                 [0xf0]),
            ('.byte 2*$10\n',                [0x20]),
            ('.byte 8-%10\n',                [6]),
            ('.byte %101%2\n',               [1]),
            ('.byte 7%$10\n',                [7]),
            ('x =.5\n.byte x*2\n',           [1]),
            ('g:\n_a: nop\n_b: nop\n.byte _b-_a\n', [0xea, 0xea, 1]),
            ('g:\n_a: nop\n.word 2*_a\n',    [0xea, 0x00, 0x20]),
            ('nop\n.word _-1\n',             [0xea, 0x00, 0x10]),
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._memory(source), expected)

    def testZeroPageMessages(self):
        """.zpbyte and .zpword names that are used twice, or that do not fit."""
        self._assertMessages([
            ('.zpbyte "a"\n.zpbyte "a"\n',           'test.asm:2: error: Label was already defined: "a"'),
            ('.zpbyte []\n',                         'test.asm:1: error: Invalid directive: .zpbyte []'),
            ('.zpbyte 1\n',                          'test.asm:1: error: Invalid directive: .zpbyte 1'),
            ('.zpword "a", 1\n',                     'test.asm:1: error: Invalid directive: .zpword f"a",1'),
            ('.for i=0, i<127, i+=1\n.zpword "v{i}"\n.end\n.zpbyte "last"\n', # $02-$ff is full
                                                     'test.asm:4: error: No space for zero page variable: "last"'),
        ])

    def testPrint(self):
        """.print prints once, after the last pass, so values are final, even with errors."""
        anyErrors, output = self._assemble('.print "start", later\njmp later\nlater: rts\n') # later is $1003
        self.assertFalse(anyErrors, output)
        self.assertEqual(output.count('start\n'), 1, output)
        self.assertIn('start\n4099\n', output)
        anyErrors, output = self._assemble('.print "before"\n.error "stop"\n')
        self.assertTrue(anyErrors)
        self.assertIn('before\n', output)

    def testAssert(self):
        """.assert reports nothing if the condition is true, also for labels defined later."""
        for source in ['.assert 2 < 3\n', '.assert 2 < 3, "Something is wrong"\n',
                       '.assert later == $1003\njmp later\nlater: rts\n']:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertFalse(anyErrors, output)

    def testBreak(self):
        """.break collects a breakpoint at the current address, with an optional VICE condition."""
        with tempfile.TemporaryDirectory() as directory:
            fileName = os.path.join(directory, 'test.asm')
            with open(fileName, 'w') as f:
                f.write('nop\n.break\nnop\n.break "RL > $40 && A == $00"\nlater: rts\n.break 5\n')
            context = assembleFile(fileName)
        self.assertEqual(context.breakpoints, [(0x1001, None), (0x1002, 'RL > $40 && A == $00')])
        self.assertEqual([e.split('/')[-1] for e in context.errors], ['test.asm:6: error: Invalid directive: .break 5'])

    def _assembleForTarget(self, source: str, target: str = None) -> Context:
        """Assemble source for the target, and return the context."""
        with tempfile.TemporaryDirectory() as directory:
            fileName = os.path.join(directory, 'test.asm')
            with open(fileName, 'w') as f:
                f.write(source)
            return assembleFile(fileName, target=target)

    def testNoTarget(self):
        """Without a target only the generic 6502 imports are available."""
        self.assertEqual(self._assembleForTarget('@ldax($1234)\n@pushRegisters()\nlda INTERRUPT_VECTOR_NMI\n').errors, [])
        for name in ['VIC_BORDER_COLOR', 'KERNAL_ROM', 'BASIC_START_ADDRESS', 'BASIC_ROM', 'CHAR_ROM', 'IO_PORT_DATA']:
            with self.subTest(name=name):
                self.assertIn(f"Name '{name}' is not defined", self._assembleForTarget(f'.word {name}\n').errors[0])

    def testBasicTokens(self):
        """The BASIC tokens are available without a target, including those of a single machine."""
        tokens = {'END': 0x80, 'INPUT_FILE': 0x84, 'INPUT': 0x85, 'REM': 0x8f, 'PRINT_FILE': 0x98, 'PRINT': 0x99, 'SYS': 0x9e,
                  'TAB': 0xa3, 'PLUS': 0xaa, 'LESS': 0xb3, 'CHR': 0xc7, 'GO': 0xcb, 'RGR': 0xcc, 'HEX': 0xd2, 'WHILE': 0xfd, 'PI': 0xff}
        symbols = self._assembleForTarget('nop\n').symbols
        for name, value in tokens.items():
            with self.subTest(name=name):
                self.assertEqual(symbols[f'BASIC_TOKEN_{name}'], value)

    def testBasicLine(self):
        """@basicLine writes the text, with keywords as tokens, except in strings, after REM, and in DATA."""
        def code(*values):
            """The bytes of the values: a token, or text."""
            return [b for value in values for b in ([value] if type(value) is int else value.encode('ascii'))]
        for text, expected in [
            ('SYS 2061',              code(0x9e, ' 2061')),
            ('POKE 53280,0:SYS 2061', code(0x97, ' 53280,0:', 0x9e, ' 2061')),
            ('poke 1,2',              code(0x97, ' 1,2')),
            ('GOTO 10',               code(0x89, ' 10')),              # not GO and TO
            ('INPUT#1,A',             code(0x84, '1,A')),              # not INPUT and #
            ('PRINT#1',               code(0x98, '1')),
            ('A=1+2',                 code('A', 0xb2, '1', 0xaa, '2')),
            ('FOR I=1 TO 3',          code(0x81, ' I', 0xb2, '1 ', 0xa4, ' 3')),
            ('PRINT CHR$(147)',       code(0x99, ' ', 0xc7, '(147)')),
            ('PRINT "POKE":SYS 1',    code(0x99, ' "POKE":', 0x9e, ' 1')),
            ('REM POKE:SYS "X',       code(0x8f, ' POKE:SYS "X')),
            ('DATA POKE,"A:B":SYS 1', code(0x83, ' POKE,"A:B":', 0x9e, ' 1')),
            ('',                      []),
        ]:
            with self.subTest(text=text):
                memory = self._memory(f""".org $1001\n@basicLine(10, '{text}')\n""")
                end = 0x1001 + len(expected) + 5
                self.assertEqual(memory, [end & 0xff, end >> 8, 10, 0] + expected + [0])

    def testBasicLineProgram(self):
        """Each line links to the next, labels can be used, and the text encoding is unchanged."""
        memory = self._memory('.org $1001\n@basicLine(10, "SYS {start}")\n@basicLine(20, "END")\n@basicEnd()\nstart: .text "A"\n')
        self.assertEqual(memory[:2], [0x0c, 0x10])                     # 2 + 2 + 7 bytes of text and the end, from $1001
        self.assertEqual(memory[4:11], [0x9e, *b' 4116', 0])           # start is $1014
        self.assertEqual(memory[11:13], [0x12, 0x10])                  # the next line, at $100c
        self.assertEqual(memory[-1], 1)                                # a screen code, the default

    def testBasicSys(self):
        """@basicSys is a @basicLine with a SYS, so it has the same link to the next line, and text encoding."""
        memory = self._memory('.org $1001\n@basicSys(10, start)\n@basicEnd()\nstart: .text "A"\n')
        self.assertEqual(memory, [0x0b, 0x10, 10, 0, 0x9e, *b'4109', 0, 0, 0, 1])

    def testBasicLineMessages(self):
        """Text that BASIC can't store is an error."""
        self._assertMessages([('@basicLine(10, "PRINT \\"é\\"")\n', "test.asm:1: error: 'ascii' codec can't encode")])

    def testBasicKeywords(self):
        """The keywords of @basicLine have the values of the BASIC_TOKEN_ symbols."""
        symbols = self._assembleForTarget('nop\n').symbols
        keywords = symbols['_BASIC_KEYWORDS']
        self.assertEqual(len(keywords), 76)
        for index, keyword in enumerate(keywords):
            if keyword.isalpha():
                with self.subTest(keyword=keyword):
                    self.assertEqual(symbols[f'BASIC_TOKEN_{keyword}'], 0x80 + index)

    def testBasicWithoutTarget(self):
        """The BASIC tokens and generators are generic, but the start address needs a target."""
        context = self._assembleForTarget('.org $1001\n@basicLine(5, "REM A")\n@basicLine(10, "SYS 4096")\n@basicEnd()\n.byte BASIC_TOKEN_REM, BASIC_TOKEN_SYS\n')
        self.assertEqual(context.errors, [])
        self.assertIn("Name 'BASIC_START_ADDRESS' is not defined", self._assembleForTarget('@basicStart()\n').errors[0])

    def testTargets(self):
        """A target adds the imports of its folder, to the generic ones."""
        source = '@basicStart()\n@basicLine(10, "SYS {start}")\n@basicEnd()\nstart: @ldax($1234)\n'
        for target, start in [('c64', 0x0801), ('vic20', 0x1001), ('c16', 0x1001), ('plus4', 0x1001), ('c128', 0x1c01)]:
            with self.subTest(target=target):
                context = self._assembleForTarget(source, target)
                self.assertEqual(context.errors, [])
                self.assertEqual(min(context.memory), start)
                self.assertEqual(context.symbols['BASIC_START_ADDRESS'], start)
        self.assertEqual(self._assembleForTarget('.word VIC_BORDER_COLOR, CHAR_ROM\n', 'c64').errors, [])

    def testVic20Vic(self):
        """The VIC-20 has its own VIC registers and colors, also where the name is the same as on the C64."""
        symbols = self._assembleForTarget('nop\n', 'vic20').symbols
        for name, value in [('VIC_ORIGIN_X', 0x9000), ('VIC_ORIGIN_Y', 0x9001), ('VIC_COLUMNS', 0x9002), ('VIC_ROWS', 0x9003),
                            ('VIC_RASTER_COUNTER', 0x9004), ('VIC_MEMORY_POINTERS', 0x9005),
                            ('VIC_LIGHT_PEN_X', 0x9006), ('VIC_LIGHT_PEN_Y', 0x9007), ('VIC_PADDLE_X', 0x9008), ('VIC_PADDLE_Y', 0x9009),
                            ('VIC_OSCILLATOR1', 0x900a), ('VIC_OSCILLATOR2', 0x900b), ('VIC_OSCILLATOR3', 0x900c), ('VIC_NOISE', 0x900d),
                            ('VIC_AUXILIARY_COLOR_VOLUME', 0x900e), ('VIC_BACKGROUND_BORDER_COLOR', 0x900f),
                            ('VIC_COLOR_BLACK', 0), ('VIC_COLOR_YELLOW', 7), ('VIC_COLOR_ORANGE', 8), ('VIC_COLOR_LIGHT_YELLOW', 15)]:
            with self.subTest(name=name):
                self.assertEqual(symbols[name], value)
        self.assertEqual(self._assembleForTarget('nop\n', 'c64').symbols['VIC_RASTER_COUNTER'], 0xd012)
        self.assertIn("Name 'VIC_BORDER_COLOR' is not defined", self._assembleForTarget('.word VIC_BORDER_COLOR\n', 'vic20').errors[0])
        self.assertIn("Name 'VIC_ORIGIN_X' is not defined", self._assembleForTarget('.word VIC_ORIGIN_X\n', 'c16').errors[0])

    def testVic20Via(self):
        """The VIC-20 has two VIA chips, with the same registers from $9110 and $9120."""
        symbols = self._assembleForTarget('nop\n', 'vic20').symbols
        registers = ['DATA_PORTB', 'DATA_PORTA', 'DATA_DIRECTION_PORTB', 'DATA_DIRECTION_PORTA',
                     'TIMER1_COUNTER_LO', 'TIMER1_COUNTER_HI', 'TIMER1_LATCH_LO', 'TIMER1_LATCH_HI', 'TIMER2_LO', 'TIMER2_HI',
                     'SERIAL_SHIFT', 'AUXILIARY_CONTROL', 'PERIPHERAL_CONTROL', 'INTERRUPT_FLAG', 'INTERRUPT_ENABLE', 'DATA_PORTA_NO_HANDSHAKE']
        for chip, base in [('VIA1', 0x9110), ('VIA2', 0x9120)]:
            for offset, register in enumerate(registers):
                with self.subTest(register=f'{chip}_{register}'):
                    self.assertEqual(symbols[f'{chip}_{register}'], base + offset)
        self.assertIn("Name 'VIA1_DATA_PORTA' is not defined", self._assembleForTarget('.word VIA1_DATA_PORTA\n', 'c64').errors[0])

    def testVic20Machine(self):
        """The screen and color RAM of the VIC-20, without and with 8K or more of memory expansion."""
        symbols = self._assembleForTarget('nop\n', 'vic20').symbols
        for name, value in [('SCREEN_RAM', 0x1e00), ('COLOR_RAM', 0x9600), ('SCREEN_RAM_EXPANDED', 0x1000), ('COLOR_RAM_EXPANDED', 0x9400)]:
            with self.subTest(name=name):
                self.assertEqual(symbols[name], value)
        self.assertIn("Name 'SCREEN_RAM' is not defined", self._assembleForTarget('.word SCREEN_RAM\n', 'c64').errors[0])

    def testC16Ted(self):
        """The C16 has the TED registers and colors, and only there."""
        symbols = self._assembleForTarget('nop\n', 'c16').symbols
        for name, value in [('TED_TIMER1_LO', 0xff00), ('TED_TIMER3_HI', 0xff05), ('TED_CONTROL_SCROLL_Y', 0xff06), ('TED_CONTROL_SCROLL_X', 0xff07),
                            ('TED_KEYBOARD', 0xff08), ('TED_INTERRUPT_REGISTER', 0xff09), ('TED_INTERRUPT_ENABLED', 0xff0a), ('TED_RASTER_COMPARE', 0xff0b),
                            ('TED_CURSOR_HI', 0xff0c), ('TED_CURSOR_LO', 0xff0d),
                            ('TED_VOICE1_FREQUENCY_LO', 0xff0e), ('TED_VOICE2_FREQUENCY_LO', 0xff0f), ('TED_VOICE2_FREQUENCY_HI', 0xff10),
                            ('TED_SOUND_CONTROL', 0xff11), ('TED_VOICE1_FREQUENCY_HI', 0xff12), ('TED_CHARSET', 0xff13), ('TED_SCREEN', 0xff14),
                            ('TED_BACKGROUND_COLOR0', 0xff15), ('TED_BACKGROUND_COLOR3', 0xff18), ('TED_BORDER_COLOR', 0xff19),
                            ('TED_CHARACTER_POSITION_HI', 0xff1a), ('TED_CHARACTER_POSITION_LO', 0xff1b), ('TED_RASTER_HI', 0xff1c), ('TED_RASTER_LO', 0xff1d),
                            ('TED_HORIZONTAL_POSITION', 0xff1e), ('TED_CHARACTER_LINE_FLASH', 0xff1f), ('TED_ROM_SELECT', 0xff3e), ('TED_RAM_SELECT', 0xff3f),
                            ('TED_COLOR_BLACK', 0), ('TED_COLOR_YELLOW', 7), ('TED_COLOR_LIGHT_GREEN', 15)]:
            with self.subTest(name=name):
                self.assertEqual(symbols[name], value)
        self.assertEqual(symbols['tedColor'](symbols['TED_COLOR_RED'], 5), 0x52)
        self.assertIn("Name 'TED_BORDER_COLOR' is not defined", self._assembleForTarget('.word TED_BORDER_COLOR\n', 'c64').errors[0])

    def testKernal(self):
        """The KERNAL routines of each target, from their jump tables, which mostly have the same addresses."""
        routines = ['RESTOR', 'VECTOR', 'SETMSG', 'LSTNSA', 'TALKSA', 'MEMBOT', 'MEMTOP', 'SCNKEY', 'SETTMO', 'IECIN', 'IECOUT', 'UNTALK',
                    'UNLSTN', 'LISTEN', 'TALK', 'READST', 'SETLFS', 'SETNAM', 'OPEN', 'CLOSE', 'CHKIN', 'CHKOUT', 'CLRCHN', 'CHRIN', 'CHROUT',
                    'LOAD', 'SAVE', 'SETTIM', 'RDTIM', 'STOP', 'GETIN', 'CLALL', 'UDTIM', 'SCREEN', 'PLOT', 'IOBASE']
        symbols = {target: self._assembleForTarget('nop\n', target).symbols for target in TARGETS}
        for routine in routines:
            with self.subTest(routine=routine):
                addresses = {target: symbols[target][f'KERNAL_ROM_{routine}'] for target in TARGETS}
                self.assertEqual(len(set(addresses.values())), 1, addresses)
        self.assertEqual(symbols['c16']['KERNAL_ROM_CHROUT'], 0xffd2)
        self.assertEqual({target: symbols[target]['KERNAL_ROM'] for target in TARGETS},
                         {'c64': 0xe000, 'vic20': 0xe000, 'c16': 0xc000, 'plus4': 0xc000, 'c128': 0xc000})
        self.assertEqual({symbols['c16']['KERNAL_ROM_SCINIT'], symbols['c16']['KERNAL_ROM_IOINIT'], symbols['c16']['KERNAL_ROM_RAMTAS']}, {0xff81, 0xff84, 0xff87})
        self.assertNotIn('KERNAL_ROM_SCINIT', symbols['vic20'])                # the VIC-20 table starts at $ff8a

    def testBasicRom(self):
        """The BASIC ROM and its string output routine, on each target."""
        for target, rom, strout in [('c64', 0xa000, 0xab1e), ('vic20', 0xc000, 0xcb1e), ('c16', 0x8000, 0x9088), ('plus4', 0x8000, 0x9088), ('c128', 0x4000, 0x55e2)]:
            with self.subTest(target=target):
                symbols = self._assembleForTarget('nop\n', target).symbols
                self.assertEqual((symbols['BASIC_ROM'], symbols['BASIC_ROM_STROUT']), (rom, strout))

    def testC16Machine(self):
        """The screen and color RAM of the C16."""
        symbols = self._assembleForTarget('nop\n', 'c16').symbols
        self.assertEqual((symbols['SCREEN_RAM'], symbols['COLOR_RAM']), (0x0c00, 0x0800))

    def testC128(self):
        """The C128 has the chips of the C64, its own memory addresses, the MMU and the VDC."""
        symbols = self._assembleForTarget('nop\n', 'c128').symbols
        for name, value in [('VIC_BORDER_COLOR', 0xd020), ('SID_VOICE1_FREQUENCY_LO', 0xd400), ('CIA1_DATA_PORTA', 0xdc00), ('SCREEN_RAM', 0x0400),
                            ('COLOR_RAM', 0xd800), ('MMU_CONFIGURATION', 0xd500), ('MMU_VERSION', 0xd50b), ('VDC_ADDRESS', 0xd600), ('VDC_DATA', 0xd601)]:
            with self.subTest(name=name):
                self.assertEqual(symbols[name], value)
        self.assertNotIn('BASIC_TOKEN_RLUM', symbols)                  # $ce is a prefix for two byte tokens on the C128

    def testPlus4(self):
        """The Plus/4 has the same symbols as the C16, and no SID."""
        symbols = {target: self._assembleForTarget('nop\n', target).symbols for target in ['c16', 'plus4']}
        for name, value in symbols['c16'].items():
            if name.isupper() and name != 'SOURCE_FOLDER':
                with self.subTest(name=name):
                    self.assertEqual(symbols['plus4'][name], value)
        self.assertEqual(symbols['plus4']['TED_BORDER_COLOR'], 0xff19)

    def testTargetOnlyHasItsOwnImports(self):
        """The imports of one target are not available in another."""
        for target in ['vic20', 'c16']:
            with self.subTest(target=target):
                self.assertIn("Name 'SID_", self._assembleForTarget('.word SID_VOICE1_FREQUENCY_LO\n', target).errors[0])

    def testUnknownTarget(self):
        """A target without a folder is an error."""
        with self.assertRaises(ValueError) as raised:
            self._assembleForTarget('nop\n', 'amiga')
        self.assertEqual(str(raised.exception), 'Unknown target: amiga')

    def testBrokenBuiltinImport(self):
        """A built-in import that fails raises its exception, with the import file in the traceback."""
        from unittest import mock
        import traceback
        with tempfile.TemporaryDirectory() as directory:
            fileName = os.path.join(directory, 'broken.py')
            with open(fileName, 'w') as f:
                f.write('1/0\n')
            with mock.patch('glob.glob', return_value=[fileName]): # instead of the imports folder
                try:
                    self._assemble('nop\n')
                    self.fail('ZeroDivisionError not raised')
                except ZeroDivisionError as exception: # not assertRaises, which drops the traceback
                    self.assertEqual(traceback.extract_tb(exception.__traceback__)[-1].filename, fileName)

class TestMusic(unittest.TestCase):
    """Tests of reading SID files."""

    def setUp(self):
        """Create a temporary folder for the SID files."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = directory.name
        self._Music = self._assemble('nop\n').symbols.get('_Music')

    def _sidFile(self, magicId=b'PSID', version=2, dataOffset=None, loadAddress=0x1000, initAddress=0x1000, playAddress=0x1003,
                 songs=1, startSong=1, speed=0, name=b'', author=b'', released=b'',
                 flags=0, startPage=0, pageLength=0, secondSid=0, thirdSid=0, data=b'\x4c\x00\x10\x60') -> str:
        """Write a SID file, with the header of the version, and return its name."""
        if dataOffset is None:
            dataOffset = 0x76 if version == 1 else 0x7c
        header = struct.pack('>4sHHHHHHHL32s32s32s', magicId, version, dataOffset, loadAddress, initAddress, playAddress,
                             songs, startSong, speed, name, author, released)
        if version >= 2:
            header += struct.pack('>HBBBB', flags, startPage, pageLength, secondSid, thirdSid)
        fileName = os.path.join(self.directory, f'{len(os.listdir(self.directory))}.sid')
        with open(fileName, 'wb') as f:
            f.write(header[:dataOffset] + data)
        return fileName

    def _load(self, fileName: str):
        """Load the file, and return the Music, or None, and the errors."""
        try:
            return self._Music.load(fileName), []
        except ValueError as exception:
            return None, [str(exception)]

    def _assemble(self, source: str, target: str = 'c64') -> Context:
        """Assemble source in the temporary folder, and return the context."""
        fileName = os.path.join(self.directory, 'test.asm')
        with open(fileName, 'w') as f:
            f.write(source)
        return assembleFile(fileName, target=target)

    def testImportMusic(self):
        """@importMusic stores the music where .org says, and defines the addresses with the prefix."""
        sid = os.path.basename(self._sidFile(loadAddress=0x2000, initAddress=0x2000, playAddress=0x2003, data=b'\x4c\x00\x20\x60'))
        context = self._assemble(f'.org MUSIC_LOAD\n@importMusic("{sid}", "MUSIC")\njsr MUSIC_INIT\n')
        self.assertEqual(context.errors, [])
        memory = [context.memory[address] for address in sorted(context.memory)]
        self.assertEqual(memory, [0x4c, 0x00, 0x20, 0x60, 0x20, 0x00, 0x20])
        self.assertEqual(min(context.memory), 0x2000)
        symbols = context.symbols
        self.assertEqual((symbols['MUSIC_LOAD'], symbols['MUSIC_INIT'], symbols['MUSIC_PLAY']), (0x2000, 0x2000, 0x2003))

    def testImportMusicWithLoadAddressInData(self):
        """The load address in the first two bytes of the data is not stored."""
        sid = os.path.basename(self._sidFile(loadAddress=0, initAddress=0x2000, data=b'\x00\x20\x60'))
        context = self._assemble(f'.org M_LOAD\n@importMusic("{sid}", "M")\n')
        self.assertEqual(context.errors, [])
        self.assertEqual(context.memory, {0x2000: 0x60})

    def testImportMusicMessages(self):
        """A file that is not found or not valid is an error, and the generator needs the c64 target."""
        sid = os.path.basename(self._sidFile(magicId=b'MSID'))
        for source, target, message in [
            ('@importMusic("nothere.sid", "M")\n', 'c64',   'test.asm:1: error: File not found: "nothere.sid"'),
            (f'@importMusic("{sid}", "M")\n',      'c64',   f'test.asm:1: error: Not a valid sid file: "{sid}": not PSID or RSID'),
            (f'@importMusic("{sid}", "M")\n',      None,    "test.asm:1: error: Name 'importMusic' is not defined"),
            (f'@importMusic("{sid}", "M")\n',      'vic20', "test.asm:1: error: Name 'importMusic' is not defined"),
            (f'.music "{sid}", "M"\n',             'c64',   'test.asm:1: error: Invalid directive: .music'),
        ]:
            with self.subTest(source=source, target=target):
                self.assertIn(message, '\n'.join(self._assemble(source, target).errors).replace(self.directory + os.sep, ''))

    def testImportsAreNotSymbols(self):
        """The class and the Python modules in music.py don't take names from the source."""
        symbols = self._assemble('nop\n').symbols
        for name in ['Music', 'os', 'struct', 'dataclass', 'field']:
            with self.subTest(name=name):
                self.assertNotIn(name, symbols)

    def testPsidVersion1(self):
        """Version 1 has the shorter header, and no flags."""
        music, errors = self._load(self._sidFile(version=1, songs=3, startSong=2, name=b'Song', author=b'Me', released=b'2021 Me'))
        self.assertEqual(errors, [])
        self.assertEqual((music.magicId, music.version), ('PSID', 1))
        self.assertEqual((music.loadAddress, music.initAddress, music.playAddress), (0x1000, 0x1000, 0x1003))
        self.assertEqual(music.data, b'\x4c\x00\x10\x60')
        self.assertEqual((music.songs, music.startSong), (3, 2))
        self.assertEqual((music.name, music.author, music.released), ('Song', 'Me', '2021 Me'))
        self.assertEqual((music.flags, music.clock, music.sidModels, music.sidAddresses), (0, 'unknown', ['unknown'], [0xd400]))

    def testLoadAddressInData(self):
        """A load address of 0 means the first two bytes of the data are the load address."""
        music, errors = self._load(self._sidFile(loadAddress=0, data=b'\x00\x20\x60'))
        self.assertEqual(errors, [])
        self.assertEqual((music.loadAddress, music.data), (0x2000, b'\x60'))

    def testInitAddressDefault(self):
        """An init address of 0 means the load address."""
        music, errors = self._load(self._sidFile(loadAddress=0x1800, initAddress=0))
        self.assertEqual(music.initAddress, 0x1800)

    def testPsidVersion2(self):
        """Version 2 adds the flags and the relocation range. Strings are Latin-1, and can fill all 32 bytes."""
        flags = 0b01 << 2 | 0b10 << 4 # PAL, MOS8580
        music, errors = self._load(self._sidFile(flags=flags, startPage=0x20, pageLength=0x10, name=b'J\xe4ger' + b'x'*27, author=b'A'*32))
        self.assertEqual(errors, [])
        self.assertEqual((music.clock, music.sidModels, music.isBasic, music.isPlaySidSpecific), ('PAL', ['MOS8580'], False, False))
        self.assertEqual((music.startPage, music.pageLength), (0x20, 0x10))
        self.assertEqual((music.name, music.author), ('Jäger' + 'x'*27, 'A'*32))
        music, errors = self._load(self._sidFile(flags=0b11 << 2 | 0b11 << 4 | 0b10)) # PAL and NTSC, both SID models, PlaySID specific
        self.assertEqual((music.clock, music.sidModels, music.isPlaySidSpecific), ('PAL and NTSC', ['MOS6581 and MOS8580'], True))

    def testExtraSids(self):
        """Version 3 adds a second SID, and version 4 a third, each with its own model and address."""
        flags = 0b01 << 4 | 0b10 << 6 | 0b01 << 8 # MOS6581, MOS8580, MOS6581
        music, errors = self._load(self._sidFile(version=3, flags=flags, secondSid=0x42))
        self.assertEqual(errors, [])
        self.assertEqual((music.sidAddresses, music.sidModels), ([0xd400, 0xd420], ['MOS6581', 'MOS8580']))
        music, errors = self._load(self._sidFile(version=4, flags=flags, secondSid=0x42, thirdSid=0xe0))
        self.assertEqual((music.sidAddresses, music.sidModels), ([0xd400, 0xd420, 0xde00], ['MOS6581', 'MOS8580', 'MOS6581']))
        music, errors = self._load(self._sidFile(version=2, secondSid=0x42, thirdSid=0xe0)) # reserved before version 3 and 4
        self.assertEqual(music.sidAddresses, [0xd400])
        for address in [0x43, 0x40, 0x80, 0xd4, 0xff]: # odd, or outside $42-$7f and $e0-$fe
            with self.subTest(address=address):
                music, errors = self._load(self._sidFile(version=4, secondSid=address, thirdSid=address))
                self.assertEqual(music.sidAddresses, [0xd400])

    def testRsid(self):
        """RSID has versions 2 to 4, with the load address in the data, and no play address."""
        for version in [2, 3, 4]:
            with self.subTest(version=version):
                music, errors = self._load(self._sidFile(magicId=b'RSID', version=version, loadAddress=0, initAddress=0x1000, playAddress=0,
                                                         data=b'\x00\x10\x60'))
                self.assertEqual(errors, [])
                self.assertEqual((music.magicId, music.version), ('RSID', version))
                self.assertEqual((music.loadAddress, music.initAddress, music.playAddress, music.data), (0x1000, 0x1000, 0, b'\x60'))
        music, errors = self._load(self._sidFile(magicId=b'RSID', loadAddress=0, initAddress=0, playAddress=0, flags=0b10,
                                                 data=b'\x01\x08\x00')) # a BASIC program, started with RUN
        self.assertEqual(errors, [])
        self.assertEqual((music.isBasic, music.isPlaySidSpecific, music.initAddress), (True, False, 0))

    def testSpeed(self):
        """Bit n of the speed is set if song n+1 uses a CIA timer, with bit 31 for song 32 and later."""
        music, errors = self._load(self._sidFile(songs=40, speed=0b101 | 1 << 31))
        self.assertEqual([song for song in range(1, 41) if music.usesCiaTimer(song)], [1, 3] + list(range(32, 41)))

    def testInvalid(self):
        """Invalid files report an error, and return None."""
        for name, fileName, error in [
            ('not found',          os.path.join(self.directory, 'missing.sid'),                             'File not found'),
            ('magic id',           self._sidFile(magicId=b'MSID'),                                          'Not a valid sid file'),
            ('short header',       self._sidFile(dataOffset=0x20, data=b''),                                'Not a valid sid file'),
            ('PSID version',       self._sidFile(version=5),                                                'unsupported PSID version 5'),
            ('RSID version 1',     self._sidFile(magicId=b'RSID', version=1, loadAddress=0, playAddress=0), 'unsupported RSID version 1'),
            ('data offset',        self._sidFile(version=2, dataOffset=0x76),                               'data offset'),
            ('no data',            self._sidFile(data=b''),                                                 'no music data'),
            ('no data after load', self._sidFile(loadAddress=0, data=b'\x00\x10'),                          'no music data'),
            ('past $ffff',         self._sidFile(loadAddress=0xfffe, data=b'\x60\x60\x60'),                 'past $ffff'),
            ('MUS data',           self._sidFile(flags=0b01),                                               'Sidplayer MUS'),
            ('RSID load',          self._sidFile(magicId=b'RSID', loadAddress=0x1000, playAddress=0),       'RSID load address'),
            ('RSID play',          self._sidFile(magicId=b'RSID', loadAddress=0, data=b'\x00\x10\x60'),     'RSID play address'),
            ('RSID speed',         self._sidFile(magicId=b'RSID', loadAddress=0, playAddress=0, speed=1,
                                                 data=b'\x00\x10\x60'),                                     'RSID speed')]:
            with self.subTest(name=name):
                music, errors = self._load(fileName)
                self.assertIsNone(music)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(error, errors[0])


if __name__ == '__main__':
    unittest.main()
