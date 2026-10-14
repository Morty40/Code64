#! /usr/bin/env python3
"""The directives, such as .byte or .org, each a function in the DIRECTIVES table.

A directive's parameters declare the arguments it accepts, and their type
annotations the types, e.g. def org(context, address: int). Parameters
without an annotation accept any type.
"""

import inspect
import os
import unittest

import evaluate
import image
import lexer
import music
import text
from context import Context


DIRECTIVES = {} # directive name: function


def directive(name: str):
    """Register a function as the directive with the given name."""
    def register(function):
        DIRECTIVES[name] = function
        return function
    return register


def _matches(function, arguments: list) -> bool:
    """Check that the arguments fit the function's parameters, and their type annotations."""
    parameters = inspect.signature(function).parameters
    try:
        bound = inspect.signature(function).bind(None, *arguments) # None for the context
    except TypeError:
        return False
    for name, value in list(bound.arguments.items())[1:]:
        expected = parameters[name].annotation
        values = value if parameters[name].kind == inspect.Parameter.VAR_POSITIONAL else [value]
        if expected is not inspect.Parameter.empty and any(type(v) is not expected for v in values):
            return False
    return True


def assemble(chunk: list, context: Context) -> bool:
    """Assemble a directive line, e.g. .byte 1, 2.

    The arguments are evaluated as one expression, a tuple if several.
    Returns False if the directive moved the read pointer (.import).
    """
    name = chunk[1].string
    expression = lexer.join(chunk[2:])

    if len(expression.strip()) > 0:
        arguments = evaluate.expression(expression, context)
    else:
        arguments = None
    if arguments is None:
        arguments = []
    elif type(arguments) is tuple:
        arguments = list(arguments)
    else:
        arguments = [arguments]

    function = DIRECTIVES.get(name)
    if function is None or not _matches(function, arguments):
        context.reportError(f'Invalid directive: .{name} {expression}')
        return True
    return function(context, *arguments) is not False


################################################################################
# data

@directive('byte')
def byte(context, *values):
    """Store bytes."""
    for value in values:
        context.store(evaluate.byteExpression(repr(value), context))


@directive('word')
def word(context, *values):
    """Store 16-bit words, low byte first."""
    for value in values:
        context.storeWord(evaluate.wordExpression(repr(value), context))


@directive('text')
def storeText(context, *texts):
    """Store texts, in the current text encoding."""
    _storeTexts(context, texts, zeroTerminated=False)


@directive('string')
def storeString(context, *texts):
    """Store texts, each followed by a zero byte."""
    _storeTexts(context, texts, zeroTerminated=True)


def _storeTexts(context, texts, zeroTerminated: bool):
    for t in texts:
        for char in t:
            o = text.ord(char, context.encoding)
            if o is not None:
                context.store(o)
            else:
                context.reportError(f'Unknown character "{char}" in text "{t}"')
        if zeroTerminated:
            context.store(0)


@directive('encoding')
def encoding(context, encoding: int):
    """Set the text encoding."""
    context.encoding = encoding


@directive('bits')
def bits(context, pattern: str):
    """Store a bit pattern, 8 bits per byte. 0 and space are 0 bits, 1 and # are 1 bits."""
    # todo: check length
    pattern = pattern.replace(' ', '0').replace('#', '1')
    for binString in [pattern[i:i+8] for i in range(0, len(pattern), 8)]:
        context.store(evaluate.byteExpression('0b'+binString, context))


@directive('bytefill')
def bytefill(context, n: int, function: str = None):
    """Store n bytes: zero, or the values of a lambda, e.g. "x: x * 2"."""
    _fill(context, n, function, context.store, evaluate.byteExpression)


@directive('wordfill')
def wordfill(context, n: int, function: str = None):
    """Store n words: zero, or the values of a lambda, e.g. "x: x * 2"."""
    _fill(context, n, function, context.storeWord, evaluate.wordExpression)


def _fill(context, n: int, function: str, store, valueExpression):
    f = evaluate.lambdaExpression(function, context) if function is not None else lambda x: 0
    for x in range(0, n):
        try:
            value = f(x)
        except Exception as exception:
            context.reportError(f'{str(exception).capitalize()}')
            value = 0
        store(valueExpression(repr(value), context))


################################################################################
# location

@directive('org')
def org(context, address: int):
    """Set the current address."""
    context.symbols['_'] = address


@directive('align')
def align(context, n: int):
    """Advance the current address to the next multiple of n."""
    if n <= 0:
        context.reportError(f'Alignment must be positive: {n}')
        n = 1 # no alignment
    _ = context.symbols['_']
    mod = _ % n
    if mod > 0:
        context.symbols['_'] = _ - mod + n


@directive('zpbyte')
def zpbyte(context, name, *names):
    """Allocate a zero page byte for each name, and define it as a label."""
    _allocate(context, (name,) + names, 1)


@directive('zpword')
def zpword(context, name, *names):
    """Allocate two zero page bytes for each name, and define it as a label."""
    _allocate(context, (name,) + names, 2)


def _allocate(context, names, size: int):
    for name in names:
        if context.zpAddress+size <= 0x100:
            if name not in context.labels:
                if context.setSymbol(name, context.zpAddress):
                    context.labels.add(name)
                    context.zpAddress += size
            else:
                context.reportError(f'Label was already defined: "{name}"')
        else:
            context.reportError(f'No space for zero page variable: "{name}"')


################################################################################
# messages

@directive('print')
def printValues(context, value, *values):
    """Print values to the terminal."""
    for v in (value,) + values:
        print(v)


@directive('warning')
def warning(context, message: str):
    """Report a warning."""
    context.reportWarning(message)


@directive('error')
def error(context, message: str):
    """Report an error."""
    context.reportError(message)


################################################################################
# repetition

@directive('repeat')
def repeat(context, iterator: str, count: int):
    """Start a repeat block: remember the .repeat line, and start the iterator at 0."""
    readPointer = context.readPointer()
    if context.setSymbol(iterator, 0):
        context.repeatStack.append( (iterator, count, readPointer) )


@directive('endr')
def endRepeat(context):
    """End a repeat block: count the iterator up, and jump back while it is below the count.

    The jump goes to the .repeat line, and as the read pointer then advances,
    assembly continues on the first line of the block.
    """
    if len(context.repeatStack) > 0:
        iterator, count, readPointer = context.repeatStack[-1] # last repeat
        context.symbols[iterator] += 1 # increment iterator
        if context.symbols[iterator] < count: # branch condition
            context.jumpReadPointer(readPointer)
        else:
            context.repeatStack.pop()
    else:
        context.reportError(f'End repeat without matching repeat')


################################################################################
# python and files

@directive('py')
def py(context, code: str):
    """Execute Python code."""
    try:
        exec(code, context.symbols)
    except:
        context.reportError(f'Failed to execute python code: "{code}"')


@directive('import')
def importFile(context, fileName: str):
    """Import a file: a .py file is executed, any other file is assembled as source code."""
    path = os.path.join(context.path, fileName)
    if os.path.splitext(path)[1] == ".py":
        try:
            print(f'Loading: {path}')
            with open(path) as f:
                py = f.read()
            exec(py, context.symbols)
        except:
            context.reportError(f'Failed to execute python code: "{fileName}"')
    else:
        context.advanceReadPointer()
        context.pushReadPointer( (path, 0) )
        return False # the read pointer was moved


_binaryFiles = {} # loaded files, by file name
_musicFiles = {}
_imageFiles = {}


@directive('binary')
def binary(context, fileName: str):
    """Store the contents of a binary file."""
    if not fileName in _binaryFiles:
        try:
            print(f'Loading: {fileName}')
            with open(os.path.join(context.path, fileName), 'rb') as f:
                _binaryFiles[fileName] = f.read()
        except FileNotFoundError:
            context.reportError(f'File not found: "{fileName}"')

    for b in _binaryFiles.get(fileName, b''):
        context.store(b)


@directive('music')
def loadMusic(context, fileName: str, prefix: str):
    """Store the music from a SID file, and define prefix_LOAD, prefix_INIT and prefix_PLAY."""
    if not fileName in _musicFiles:
        mu = music.load(fileName, context)
        if type(mu) is music.Music:
            print(f'Loading: {fileName}')
            _musicFiles[fileName] = mu
        else:
            context.reportError(f'Music not loaded: "{fileName}"')

    if (mu := _musicFiles.get(fileName)) is not None:
        context.setSymbol(prefix+'_LOAD', mu.loadAddress)
        context.setSymbol(prefix+'_INIT', mu.initAddress)
        context.setSymbol(prefix+'_PLAY', mu.playAddress)
        for b in mu.data:
            context.store(b)


@directive('bitmap')
@directive('sprite')
def loadImage(context, fileName: str, bitsPerPixel: int):
    """Store an image from a BMP file, converted to sprites."""
    if not fileName in _imageFiles:
        im = image.load(fileName, context)
        if type(im) is image.Image:
            print(f'Loading: {fileName}')
            _imageFiles[fileName] = im
        else:
            context.reportError(f'Image not loaded: "{fileName}"')

    if (im := _imageFiles.get(fileName)) is not None:
        for b in im.data:
            context.store(b)


################################################################################

class TestDirectives(unittest.TestCase):

    def testMatches(self):
        """Arguments are checked against the parameters, and their type annotations."""
        self.assertTrue(_matches(org, [0x1000]))
        self.assertFalse(_matches(org, []))                  # missing argument
        self.assertFalse(_matches(org, [1, 2]))              # too many arguments
        self.assertFalse(_matches(org, ['a']))               # wrong type
        self.assertFalse(_matches(org, [True]))              # a bool is not an int
        self.assertTrue(_matches(bytefill, [3]))             # optional argument
        self.assertTrue(_matches(bytefill, [3, 'x: x']))
        self.assertTrue(_matches(byte, []))                  # any number of any type
        self.assertTrue(_matches(byte, [1, 'a', 2.5]))
        self.assertFalse(_matches(printValues, []))          # at least one


    def testBitsWithInt(self):
        context = Context({})
        assemble(lexer.tokenize('.bits 3')[:-1], context)
        self.assertEqual(context.errors, ['error: Invalid directive: .bits 3'])


if __name__ == '__main__':
    unittest.main()
