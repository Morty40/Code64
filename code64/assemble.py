#! /usr/bin/env python3
"""The assembler: assembles source files into memory, in multiple passes."""

import contextlib
import io
import os
import re
import tempfile
import unittest
import glob

#--
import pathlib, sys
sys.path.append(str(pathlib.Path(__file__).parent.absolute()))
#--

import cpu
import eval
import image
import lexer
import music
import text
from context import Context

def lo(x): return x&0xff
def hi(x): return (x>>8)&0xff


def _join(tokens: list) -> str:
    ''' joins tokens into an expression, with a space between adjacent words, e.g. "1 if x else 2" '''
    s = ''
    for t in tokens:
        if re.fullmatch(r'\w\w', s[-1:] + t.string[:1]):
            s += ' '
        s += t.string
    return s


def _store(value: int, context: Context):
    """Store a byte at the current address, and advance the address."""
    currentLocation = context.symbols['_']
    
    if currentLocation >= 0 and currentLocation <= 0xffff:
            
        if currentLocation in context.memory:
            oldValue = context.memory[currentLocation]
            context.reportWarning(f'${currentLocation:04x} is overwritten (${oldValue:02x} to ${value:02x})')
            
        # store value in memory, and advance to next memory location
        context.memory[currentLocation] = value
        context.symbols['_'] += 1
        
    else:
        context.reportError(f'Destination memory address out of range: ${currentLocation:x}')
    

def _asmInstruction(chunk: list, context: Context):
    """Assemble an instruction, with the address mode given by the operand.

    Zero page modes are chosen for addresses below $100.
    """
    mnemonic = chunk[0].string
    operand = _join(chunk[1:])
        
    instruction = cpu.instructionWithMnemonic(mnemonic)
    opcodes = instruction.opcodes
        
    bytes = []
    
    if cpu.AddressMode.accumulator in opcodes and not operand:
        bytes = [opcodes[cpu.AddressMode.accumulator]]
        
    elif cpu.AddressMode.implied in opcodes and not operand:
        bytes = [opcodes[cpu.AddressMode.implied]]
        
    elif cpu.AddressMode.immediate in opcodes and operand.startswith('#'):
        v = eval.byteExpression(operand[1:], context)
        bytes = [opcodes[cpu.AddressMode.immediate], v]
        
    elif cpu.AddressMode.indirectX in opcodes and operand.startswith('(') and operand.endswith(',x)'):
        v = eval.byteExpression(operand[1:-3], context)
        bytes = [opcodes[cpu.AddressMode.indirectX], v]

    elif cpu.AddressMode.indirectY in opcodes and operand.startswith('(') and operand.endswith('),y'):
        v = eval.byteExpression(operand[1:-3], context)
        bytes = [opcodes[cpu.AddressMode.indirectY], v]

    elif cpu.AddressMode.indirect in opcodes and operand.startswith('(') and operand.endswith(')'):
        v = eval.wordExpression(operand[1:-1], context)
        if lo(v) == 0xff:
            context.reportWarning(f'Indirect address located on page boundary: ${v:04x}')
        bytes = [opcodes[cpu.AddressMode.indirect], lo(v), hi(v)]

    elif cpu.AddressMode.relative in opcodes: # TODO: give warning about branching across page boundary
        v = eval.wordExpression(operand, context)
        # the offset counts from the address after the 2-byte branch instruction
        dist = v - context.symbols['_'] - 2
        if dist < -128 or dist > 127: # branch is out of range (signed byte)
            context.reportError(f'Branch destination out of range [-128..127]: {dist}')
            dist = 0
        bytes = [opcodes[cpu.AddressMode.relative], dist&0xff]

    elif (cpu.AddressMode.zeroPageX in opcodes or cpu.AddressMode.absoluteX in opcodes) and operand.endswith(',x'):
        v = eval.wordExpression(operand[:-2], context)
        if cpu.AddressMode.zeroPageX in opcodes and hi(v) == 0:
            bytes = [opcodes[cpu.AddressMode.zeroPageX], lo(v)]
        elif cpu.AddressMode.absoluteX in opcodes:
            bytes = [opcodes[cpu.AddressMode.absoluteX], lo(v), hi(v)]

    elif (cpu.AddressMode.zeroPageY in opcodes or cpu.AddressMode.absoluteY in opcodes) and operand.endswith(',y'):
        v = eval.wordExpression(operand[:-2], context)
        if cpu.AddressMode.zeroPageY in opcodes and hi(v) == 0:
            bytes = [opcodes[cpu.AddressMode.zeroPageY], lo(v)]
        elif cpu.AddressMode.absoluteY in opcodes:
            bytes = [opcodes[cpu.AddressMode.absoluteY], lo(v), hi(v)]

    elif (cpu.AddressMode.zeroPage in opcodes or cpu.AddressMode.absolute in opcodes) and operand:
        v = eval.wordExpression(operand, context)
        if cpu.AddressMode.zeroPage in opcodes and hi(v) == 0:
            bytes = [opcodes[cpu.AddressMode.zeroPage], lo(v)]
        elif cpu.AddressMode.absolute in opcodes:
            bytes = [opcodes[cpu.AddressMode.absolute], lo(v), hi(v)]

    if len(bytes) <= 0:
        context.reportError(f'Unknown instruction or address mode: {mnemonic} {operand}')
        
    # store the bytes
    for b in bytes:
        _store(b, context)

    
def _asmAssignment(chunk: list, context: Context):
    """Assign an expression to a symbol: name = expression.

    Upper case symbols are constants: once they have a value, they can't
    be assigned a different value.
    """
    symbol = chunk[0].string
    expression = _join(chunk[2:])
    value = eval.expression(expression, context)
    if value is not None:
        if symbol.isupper():
            if symbol in context.symbols and context.symbols[symbol] != value:
                context.reportError(f'Constant "{symbol}" cannot be changed from {context.symbols[symbol]} to {value}')
                return # the constant keeps its value
        context.setSymbol(symbol, value)
    
    
def _asmDirective(chunk: list, context: Context) -> bool:
    """Assemble a directive, such as .byte or .org.

    The arguments are evaluated as one expression, a tuple if several.
    Returns False if the directive moved the read pointer (.import).
    """
    advance = True # advance read pointer after this chunk

    directive = chunk[1].string
    expression = _join(chunk[2:])

    # the arguments are one Python expression: a tuple if there are several,
    # e.g. .byte 1, 2. Directives check argTypes, e.g. [str, int] for .repeat
    if len(expression.strip()) > 0:
        arguments = eval.expression(expression, context)
    else:
        arguments = None
    if arguments is None:
        arguments = []
    elif type(arguments) is tuple:
        arguments = list(arguments)
    else:
        arguments = [arguments]

    argTypes = list(map(lambda x: type(x), arguments))

    # data directive: declare a list of byte values
    if directive == 'byte':
        for arg in arguments:
            value = eval.byteExpression(repr(arg), context)
            _store(value, context)

    # data directive: declare a list of word values
    elif directive == 'word':
        for arg in arguments:
            value = eval.wordExpression(repr(arg), context)
            _store(lo(value), context)
            _store(hi(value), context)
        
    # data directive: declare a text string
    elif directive == 'text' or directive == 'string':
        for arg in arguments:
            for char in arg:
                o = text.ord(char, context.encoding)
                if o is not None:
                    _store(o, context)
                else:
                    context.reportError(f'Unknown character "{char}" in text "{arg}"')
            if directive == 'string': # zero-terminated
                _store(0, context)

    elif directive == 'encoding' and argTypes == [int]:
        context.encoding = arguments[0]

    # data directive: declare bits
    elif directive == 'bits' and argTypes == [str]:
        for arg in arguments:
            # todo: check length
            arg = arg.replace(' ', '0')
            arg = arg.replace('#', '1')
            for binString in [arg[i:i+8] for i in range(0, len(arg), 8)]:
                value = eval.byteExpression('0b'+binString, context)
                if value is not None:
                    _store(value, context)

    # origin, sets the current memory location
    elif directive == 'org' and argTypes == [int]:
        arg = arguments[0]
        context.symbols['_'] = arg

    # fill memory with n bytes or words, optional lambda argument
    elif directive in ['bytefill', 'wordfill'] and (argTypes == [int] or argTypes == [int, str]):
        n = arguments[0]
        if len(arguments) == 2:
            f = eval.lambdaExpression(arguments[1], context)
        else:
            f = lambda x: 0
        for x in range(0, n):
            try:
                value = f(x)
            except Exception as exception:
                context.reportError(f'{str(exception).capitalize()}')
                value = 0
            if directive == 'bytefill':
                _store(eval.byteExpression(repr(value), context), context)
            else:
                value = eval.wordExpression(repr(value), context)
                _store(lo(value), context)
                _store(hi(value), context)

    # align the current memory location to n
    elif directive == 'align' and argTypes == [int]:
        arg = arguments[0]
        if arg <= 0:
            context.reportError(f'Alignment must be positive: {arg}')
            arg = 1 # no alignment
        _ = context.symbols['_']
        mod = _ % arg 
        if mod > 0:
            context.symbols['_'] = _ - mod + arg
        
    # print to terminal
    elif directive == 'print' and len(arguments) >= 1:
        for arg in arguments:
            print(arg)
    
    # generate warning
    elif directive == 'warning' and argTypes == [str]:
        warning = arguments[0]
        context.reportWarning(warning)

    # generate error
    elif directive == 'error' and argTypes == [str]:
        error = arguments[0]
        context.reportError(error)
            
    # repeat: remember the .repeat line, and start the iterator at 0
    elif directive == 'repeat' and argTypes == [str, int]:
        iterator = arguments[0]
        count = arguments[1]
        readPointer = context.readPointer()
        if context.setSymbol(iterator, 0):
            context.repeatStack.append( (iterator, count, readPointer) )

    # end repeat: count the iterator up, and jump back while it is below the count.
    # The jump goes to the .repeat line, and as the read pointer then advances,
    # assembly continues on the first line of the block.
    elif directive == 'endr' and argTypes == []:
        if len(context.repeatStack) > 0:
            iterator, count, readPointer = context.repeatStack[-1] # last repeat
            context.symbols[iterator] += 1 # increment iterator
            if context.symbols[iterator] < count: # branch condition
                context.jumpReadPointer(readPointer)
            else:
                context.repeatStack.pop()
        else:
            context.reportError(f'End repeat without matching repeat')

    # execute python code
    elif directive == 'py' and argTypes == [str]:
        expression = arguments[0]
        try:
            exec(expression, context.symbols)
        except:
            context.reportError(f'Failed to execute python code: "{expression}"')

    # import source file
    elif directive == 'import' and argTypes == [str]:
        fileName = os.path.join(context.path, arguments[0])
        extension = os.path.splitext(fileName)[1]
        if extension == ".py":
            try:
                print(f'Loading: {fileName}')
                with open(fileName) as f:
                    py = f.read()
                exec(py, context.symbols)
            except:
                context.reportError(f'Failed to execute python code: "{expression}"')
        else:
            context.advanceReadPointer()
            context.pushReadPointer( (fileName, 0) )
            advance = False
    
    # import binary file
    elif directive == 'binary' and argTypes == [str]:
        fileName = arguments[0]
        
        if not fileName in _asmDirective.binaryFiles:
            try:
                print(f'Loading: {fileName}')
                with open(os.path.join(context.path, fileName), 'rb') as f:
                    bytesRead = f.read()
                    _asmDirective.binaryFiles[fileName] = bytesRead
            except FileNotFoundError:
                context.reportError(f'File not found: "{fileName}"')
                
        if fileName in _asmDirective.binaryFiles:
            bytesRead = _asmDirective.binaryFiles[fileName]
            for b in bytesRead:
                _store(b, context)

    # import music file
    elif directive == 'music' and argTypes == [str, str]:
        fileName = arguments[0]
        prefix = arguments[1]
        
        if not fileName in _asmDirective.musicFiles:
            mu = music.load(fileName, context)
            if type(mu) is music.Music:
                print(f'Loading: {fileName}')
                _asmDirective.musicFiles[fileName] = mu
            else:
                context.reportError(f'Music not loaded: "{fileName}"')

        if (mu := _asmDirective.musicFiles.get(fileName)) is not None:
            context.setSymbol(prefix+'_LOAD', mu.loadAddress)
            context.setSymbol(prefix+'_INIT', mu.initAddress)
            context.setSymbol(prefix+'_PLAY', mu.playAddress)
            for b in mu.data:
                _store(b, context)

    # import bitmap or sprite    
    elif directive in ['bitmap', 'sprite'] and argTypes == [str, int]:
        fileName = arguments[0]
        bitsPerPixel = arguments[1]

        if not fileName in _asmDirective.imageFiles:
            im = image.load(fileName, context)
            if type(im) is image.Image:
                print(f'Loading: {fileName}')
                _asmDirective.imageFiles[fileName] = im
            else:
                context.reportError(f'Image not loaded: "{fileName}"')

        if (im := _asmDirective.imageFiles.get(fileName)) is not None:
            for b in im.data:
                _store(b, context)

    elif directive in ['zpbyte', 'zpword'] and len(arguments) > 0:
        size = {'zpbyte': 1, 'zpword': 2}[directive]
        for arg in arguments:
            if context.zpAddress+size <= 0x100:
                if arg not in context.labels:
                    if context.setSymbol(arg, context.zpAddress):
                        context.labels.add(arg)
                        context.zpAddress += size
                else:
                    context.reportError(f'Label was already defined: "{arg}"')
            else:
                context.reportError(f'No space for zero page variable: "{arg}"')

    else:
        context.reportError(f'Invalid directive: .{directive} {expression}')
        
    return advance
_asmDirective.binaryFiles = {} # function static variable
_asmDirective.musicFiles = {}
_asmDirective.imageFiles = {}


def _asmGenerator(chunk: list, context: Context) -> bool:
    """Assemble the code returned by a generator: @function(arguments).

    Local labels get their own scope for each call. Returns False, as
    the read pointer is moved to the generated code.
    """
    generator = _join(chunk[1:])
    value = eval.expression(generator, context)
    if type(value) is not str:
        context.reportError(f'Generator must return a string, not {type(value).__name__}')

    context.advanceReadPointer()

    (fileName, lineIndex) = context.readPointer()
    generatorId = f"{fileName}:{lineIndex} @{generator}"
    context.generatorCount += 1
    tokens = lexer.translateLocalLabels(lexer.tokenize(value), f'_gen{context.generatorCount}')
    multiPass.chunks[generatorId] = list(lexer.chunkSplit(tokens))

    context.pushReadPointer( (generatorId, 0) )

    return False # don't advance


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
        except:
            print(f"failed to import: {fileName}")

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
                    _asmInstruction(chunk, context)

                elif len(chunk) >= 3 and chunk[1].string == '=':
                    _asmAssignment(chunk, context)

                elif len(chunk) >= 2 and chunk[0].string == '.':
                    advance = _asmDirective(chunk, context)
            
                elif len(chunk) >= 2 and chunk[0].string == '@':
                    advance = _asmGenerator(chunk, context)

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
        ''' assembles source, and returns (anyErrors, printed output) '''
        with tempfile.TemporaryDirectory() as directory:
            fileName = os.path.join(directory, 'test.asm')
            with open(fileName, 'w') as f:
                f.write(source)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                anyErrors = multiPass(fileName, None)
        return anyErrors, output.getvalue()

    def testTest(self):
        pass

    def testBitsWithInt(self):
        context = Context({})
        _asmDirective(lexer.tokenize('.bits 3')[:-1], context)
        self.assertEqual(context.errors, ['error: Invalid directive: .bits 3'])

    def testBranchOutOfRange(self):
        # one byte beyond +127 and -128, counted from $1002, the address after the branch
        for target, dist in [('$1082', 128), ('$0f81', -129)]:
            context = Context({'_': 0x1000})
            _asmInstruction(lexer.tokenize(f'bne {target}')[:-1], context)
            self.assertEqual(context.errors, [f'error: Branch destination out of range [-128..127]: {dist}'])

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
            ('.py "1/0"\n',                          'test.asm:1 error: Failed to execute python code: "1/0"'),
            ('.import "nothere.py"\n',               'test.asm:1 error: Failed to execute python code'),
            ('.binary "nothere.bin"\n',              'test.asm:1 error: File not found: "nothere.bin"'),
            ('.music "nothere.sid", "M"\n',          'test.asm:1 error: Music not loaded: "nothere.sid"'),
            ('.sprite "nothere.bmp", 1\n',           'test.asm:1 error: Image not loaded: "nothere.bmp"'),
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
        self.assertIn(f'failed to import: {fileName}', output)

if __name__ == '__main__':
    unittest.main()

# TODO: only load imports once!
