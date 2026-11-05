#! /usr/bin/env python3
"""Tests of the generators."""

import os
import tempfile
import unittest

from .. import lexer
from ..assemble import assembleFile
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

    def _memory(self, source: str) -> list:
        """Assemble source without errors, and return the bytes in memory, by address."""
        with tempfile.TemporaryDirectory() as directory:
            fileName = os.path.join(directory, 'test.asm')
            with open(fileName, 'w') as f:
                f.write(source)
            context = assembleFile(fileName)
        self.assertEqual(context.errors, [])
        return [context.memory[address] for address in sorted(context.memory)]

    def testForwardReference(self):
        """A generator argument can be a symbol that is given after the call."""
        self.assertEqual(self._memory('.python\n    def fill(x, n):\n        return f".byte {x}\\n" * n\n.end\n'
                                      '@fill(1, length)\n@fill(2, length)\nlength = 3\n'), [1, 1, 1, 2, 2, 2])

    def testLocalLabelBytes(self):
        """Each call has its own local labels, after a label or in the same scope as the last call."""
        self.assertEqual(self._memory('.python\n    def delay(n):\n        return f"ldx #{n}\\n_loop: dex\\nbne _loop\\n"\n.end\n'
                                      'aa: @delay(3)\nbb: @delay(5)\n@delay(7)\nrts\n'),
                         [0xa2, 3, 0xca, 0xd0, 0xfd, 0xa2, 5, 0xca, 0xd0, 0xfd, 0xa2, 7, 0xca, 0xd0, 0xfd, 0x60])

    def testNamedArguments(self):
        """Named arguments work with or without spaces around the =."""
        self.assertEqual(self._memory('.python\n    def jump(address):\n        return f"jmp {address}\\n"\n.end\n'
                                      '@jump(address=_sub)\n@jump(address =_sub)\n@jump(address= _sub)\n@jump(address = _sub)\n'
                                      '_sub:\nrts\n'), [0x4c, 0x0c, 0x10] * 4 + [0x60])


if __name__ == '__main__':
    unittest.main()
