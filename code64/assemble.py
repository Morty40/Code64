#! /usr/bin/env python3

import os
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


def _store(value: int, context: Context):
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
    mnemonic = chunk[0].string
    operand = ''.join(map(lambda t: t.string, chunk[1:]))
        
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
    symbol = chunk[0].string
    expression = ''.join(map(lambda t: t.string, chunk[2:]))
    value = eval.expression(expression, context)
    if value is not None:
        context.symbols[symbol] = value
    
    
def _asmDirective(chunk: list, context: Context):
    c = chunk[1]

    advance = True # advance read pointer after this chunk

    directive = chunk[1].string
    expression = ''.join(map(lambda t: t.string, chunk[2:]))

    # eval list of arguments
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
            value = eval.byteExpression(str(arg), context)
            _store(value, context)

    # data directive: declare a list of word values
    elif directive == 'word':
        for arg in arguments:
            value = eval.wordExpression(str(arg), context)
            _store(lo(value), context)
            _store(hi(value), context)
        
    # data directive: declare a text string
    elif directive == 'text' or directive == 'string':
        for arg in arguments:
            for char in arg:
                o = text.ord(char)
                if o is not None:
                    _store(o, context)
                else:
                    context.reportError(f'Unknown character "{char}" in text "{arg}"')
            if directive == 'string': # zero-terminated
                _store(0, context)

    elif directive == 'encoding' and argTypes == [int]:
        text.encoding = arguments[0]

    # data directive: declare bits
    elif directive == 'bits':
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

    # fill memory with n bytes, optional lambda argument
    elif directive == 'bytefill' and (argTypes == [int] or argTypes == [int, str]):
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
            value = eval.byteExpression(f'{value}', context)
            _store(value, context)

    elif directive == 'wordfill' and (argTypes == [int] or argTypes == [int, str]):
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
            value = eval.wordExpression(f'{value}', context)
            _store(lo(value), context)
            _store(hi(value), context)

    # align the current memory location to n
    elif directive == 'align' and argTypes == [int]:
        arg = arguments[0]
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
            
    # repeat
    elif directive == 'repeat' and argTypes == [str, int]:
        iterator = arguments[0]
        count = arguments[1]
        readPointer = context.readPointer()
        context.repeatStack.append( (iterator, count, readPointer) )
        context.symbols[iterator] = 0

    # end repeat
    elif directive == 'endr' and argTypes == []:
        if len(context.repeatStack) > 0:
            iterator, count, readPointer = context.repeatStack[-1] # last repeat
            context.symbols[iterator] += 1 # increment iterator
            if context.symbols[iterator] < count: # branch condition
                context.jumpReadPointer(readPointer)
                ## TODO: readpointer is advanced so it works by coincidence
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
                py = open(fileName).read() # TODO: use _asmDirective.pythonFiles
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
            context.symbols[prefix+'_LOAD'] = mu.loadAddress
            context.symbols[prefix+'_INIT'] = mu.initAddress
            context.symbols[prefix+'_PLAY'] = mu.playAddress
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
                    context.symbols[arg] = context.zpAddress
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
_asmDirective.pythonFiles = {}


def _asmGenerator(chunk: list, context: Context):
    generator = ''.join(map(lambda t: t.string, chunk[1:]))
    value = eval.expression(generator, context)

    context.advanceReadPointer()

    (fileName, lineIndex) = context.readPointer()
    generatorId = f"{fileName}:{lineIndex} @{generator}"
    multiPass.chunks[generatorId] = list(lexer.chunkSplit(lexer.tokenize(value)))

    context.pushReadPointer( (generatorId, 0) )

    return False # don't advance


def _saveMemoryToPrg(start: int, memory: dict, fileName: str):        
    f = open(fileName, 'wb')

    ints = [lo(start), hi(start)]

    if len(memory) > 0:
        first = min(memory.keys())
        last = max(memory.keys())
        for i in range(first, last+1):
            ints.append(memory[i] if i in memory else 0)

    f.write(bytes(ints))
    f.close()


def multiPass(inFile, outFile):

    path = os.path.dirname(inFile)

    symbols = {'lo': lo, 'hi': hi,
        'chr': text.chr, 'ord': text.ord,
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
            py = open(fileName).read()
            exec(py, symbols)
        except:
            print(f"failed to import: {fileName}")

    lastMemory = {}
    
    defaultOrigin = 0x1000

    n = 1
    while n<10:
        symbols['_'] = defaultOrigin
        context = Context(symbols)
        context.path = path
        context.pushReadPointer( (inFile, 0) )

        while True:
            readPointer = context.readPointer()
            #print(readPointer)
            if readPointer is None: break

            fileName, lineIndex = readPointer
            
            if not fileName in multiPass.chunks:
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
                    context.symbols[label] = context.symbols['_']
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
                context.popReadPointer()
                
        if len(context.errors) == 0 and context.memory == lastMemory:
            break

        # prepare for next pass
        lastMemory = dict(context.memory)
        n += 1

    # print memory use
    context.printMemoryUse()

    # print warning and errors
    context.printAsmReport()    

    if outFile is not None:
        if len(context.errors) == 0:
            # successfull assembly, all symbols resolved, no errors
            print(f'Saving program: {outFile}')
            start = defaultOrigin
            if len(context.memory) > 0:
                start = min(context.memory.keys())
            _saveMemoryToPrg(start, context.memory, outFile)
        else:
            # failed to resolve some symbols
            print(f'failed to save "{outFile}"')
multiPass.chunks = {} # function static variable
        

################################################################################

class TestAssemble(unittest.TestCase):

    def testTest(self):
        pass

if __name__ == '__main__':
    unittest.main()

# TODO: only load imports once!
