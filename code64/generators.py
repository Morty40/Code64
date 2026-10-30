#! /usr/bin/env python3
"""The generators: Python code that returns assembly code, e.g. @nop(3)."""

import re
import unittest

from . import evaluate
from . import lexer
from .context import Context


def assemble(tokens: list, context: Context, chunks: dict) -> bool:
    """Assemble the code returned by a generator: @function(arguments).

    The generated code is added to chunks, the tokenized files, and assembled
    like an imported file. Local labels get their own scope for each call, named after the generator.
    Returns False, as the read pointer is moved to the generated code.
    """
    generator = lexer.join(tokens[1:])
    value = evaluate.expression(generator, context)
    if type(value) is not str:
        context.reportError(f'Generator must return a string, not {type(value).__name__}')

    context.advanceReadPointer()

    (fileName, lineIndex) = context.readPointer()
    generatorId = f"{fileName}:{lineIndex} @{generator}"
    # local labels are named after the generator and its call count, e.g. _loop in the 2nd @ldax() is _ldax2_loop
    match = re.match(r'[A-Za-z_][\w.]*', generator)
    name = match.group().split('.')[-1] if match else 'gen'
    context.generatorCounts[name] = context.generatorCounts.get(name, 0) + 1
    generatedTokens = lexer.translateLocalLabels(lexer.tokenize(value), f'{name}{context.generatorCounts[name]}')
    chunks[generatorId] = list(lexer.splitByNewline(generatedTokens))

    context.pushReadPointer( (generatorId, 0) )

    return False # don't advance


################################################################################

class TestGenerators(unittest.TestCase):

    def _assemble(self, line: str, symbols: dict):
        """Assemble a generator line, as line 1 of test.asm, and return the context and chunks."""
        context = Context(symbols)
        context.pushReadPointer( ('test.asm', 0) )
        chunks = {}
        advance = assemble(lexer.tokenize(line)[:-1], context, chunks)
        self.assertFalse(advance)
        return context, chunks

    def testGeneratedCode(self):
        """The generated code is assembled next, like an imported file."""
        context, chunks = self._assemble('@code(2)', {'code': lambda n: 'nop\n' * n})
        self.assertEqual(context.readPointer(), ('test.asm:1 @code(2)', 0))
        lines = [[t.string for t in lineTokens] for lineTokens in chunks['test.asm:1 @code(2)']]
        self.assertEqual(lines[:2], [['nop'], ['nop']])
        self.assertEqual(context.errors, [])

    def testLocalLabels(self):
        """Local labels in the generated code get their own scope for each call, named after the generator and counted for each name."""
        context, chunks = self._assemble('@loop()', {'loop': lambda: '_loop: bne _loop\n'})
        line = [t.string for t in chunks['test.asm:1 @loop()'][0]]
        self.assertEqual(line, ['_loop1_loop', ':', 'bne', '_loop1_loop'])
        for generator, expected in [('@loop()', '_loop2_x'), ('@wait(3)', '_wait1_x'), ('@loop()', '_loop3_x'), ('@sprites.draw()', '_draw1_x')]:
            with self.subTest(generator=generator):
                context.symbols.update({'loop': lambda: '_x: nop\n', 'wait': lambda n: '_x: nop\n',
                                        'sprites': type('Sprites', (), {'draw': staticmethod(lambda: '_x: nop\n')})})
                context.pushReadPointer( ('test.asm', 0) ) # each call on line 1 of test.asm
                assemble(lexer.tokenize(generator)[:-1], context, chunks)
                self.assertEqual(chunks[f'test.asm:1 {generator}'][0][0].string, expected)

    def testNotString(self):
        """A generator that doesn't return a string is an error."""
        context, chunks = self._assemble('@code', {'code': lambda: ''}) # forgot the parentheses
        self.assertEqual(context.errors, ['test.asm:1: error: Generator must return a string, not function'])


if __name__ == '__main__':
    unittest.main()
