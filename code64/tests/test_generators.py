#! /usr/bin/env python3
"""Tests of the generators."""

import unittest

from .. import lexer
from ..context import Context
from ..generators import assemble


class TestGenerators(unittest.TestCase):
    """Tests of generated code and its local labels."""

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
