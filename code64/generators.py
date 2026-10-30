#! /usr/bin/env python3
"""The generators: Python code that returns assembly code, e.g. @nop(3)."""

import unittest

from . import evaluate
from . import lexer
from .context import Context


def assemble(tokens: list, context: Context, chunks: dict) -> bool:
    """Assemble the code returned by a generator: @function(arguments).

    The generated code is added to chunks, the tokenized files, and assembled
    like an imported file. Local labels get their own scope for each call.
    Returns False, as the read pointer is moved to the generated code.
    """
    generator = lexer.join(tokens[1:])
    value = evaluate.expression(generator, context)
    if type(value) is not str:
        context.reportError(f'Generator must return a string, not {type(value).__name__}')

    context.advanceReadPointer()

    (fileName, lineIndex) = context.readPointer()
    generatorId = f"{fileName}:{lineIndex} @{generator}"
    context.generatorCount += 1
    generatedTokens = lexer.translateLocalLabels(lexer.tokenize(value), f'_gen{context.generatorCount}')
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
        """Local labels in the generated code get their own scope for each call."""
        context, chunks = self._assemble('@loop()', {'loop': lambda: '_loop: bne _loop\n'})
        line = [t.string for t in chunks['test.asm:1 @loop()'][0]]
        self.assertEqual(line, ['__gen1_loop', ':', 'bne', '__gen1_loop'])

    def testNotString(self):
        """A generator that doesn't return a string is an error."""
        context, chunks = self._assemble('@code', {'code': lambda: ''}) # forgot the parentheses
        self.assertEqual(context.errors, ['test.asm:1: error: Generator must return a string, not function'])


if __name__ == '__main__':
    unittest.main()
