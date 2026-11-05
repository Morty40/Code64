#! /usr/bin/env python3
"""Tests of the 6502 instructions."""

import unittest

from .. import lexer
from ..context import Context
from ..instructions import assemble


class TestInstructions(unittest.TestCase):
    """Tests of choosing the address mode, and the bytes stored."""

    def _assemble(self, line: str):
        """Assemble one instruction at $1000, and return the bytes and the context."""
        context = Context({'_': 0x1000})
        assemble(lexer.tokenize(line)[:-1], context)
        return [context.memory[address] for address in sorted(context.memory)], context

    def testAddressModes(self):
        """Each address mode, chosen from the operand syntax."""
        for line, expected in [
            ('rts',         [0x60]),             # implied
            ('asl',         [0x0a]),             # accumulator
            ('lda #1',      [0xa9, 0x01]),       # immediate
            ('lda ($10,x)', [0xa1, 0x10]),       # indexed indirect
            ('lda ($10),y', [0xb1, 0x10]),       # indirect indexed
            ('jmp ($1234)', [0x6c, 0x34, 0x12]), # indirect
            ('bne $1000',   [0xd0, 0xfe]),       # relative, to itself
            ('lda $10,x',   [0xb5, 0x10]),       # zero page,x
            ('lda $1234,x', [0xbd, 0x34, 0x12]), # absolute,x
            ('ldx $10,y',   [0xb6, 0x10]),       # zero page,y
            ('lda $10,y',   [0xb9, 0x10, 0x00]), # absolute,y, as lda has no zero page,y
            ('lda $10',     [0xa5, 0x10]),       # zero page
            ('lda $1234',   [0xad, 0x34, 0x12]), # absolute
            ('jmp $10',     [0x4c, 0x10, 0x00]), # absolute, as jmp has no zero page
        ]:
            with self.subTest(line=line):
                data, context = self._assemble(line)
                self.assertEqual(data, expected)
                self.assertEqual(context.errors + context.warnings, [])

    def testIndirectPageBoundary(self):
        """jmp ($xxff) is assembled, with a warning, as the 6502 does not cross the page."""
        data, context = self._assemble('jmp ($10ff)')
        self.assertEqual(data, [0x6c, 0xff, 0x10])
        self.assertEqual(context.warnings, ['warning: Indirect address located on page boundary: $10ff'])

    def testUnknownAddressMode(self):
        """An operand the instruction has no address mode for is an error, and nothing is stored."""
        for line, operand in [('stx $1234,y', '0x1234,y'), # no absolute,y
                              ('sty $1234,x', '0x1234,x'), # no absolute,x
                              ('lda', '')]:                # no implied
            with self.subTest(line=line):
                data, context = self._assemble(line)
                self.assertEqual(data, [])
                self.assertEqual(context.errors, [f'error: Unknown instruction or address mode: {line.split()[0]} {operand}'])

    def testBranchOutOfRange(self):
        """A branch reaches -128 to +127 bytes. One byte more is an error."""
        # one byte beyond +127 and -128, counted from $1002, the address after the branch
        for target, dist in [('$1082', 128), ('$0f81', -129)]:
            context = Context({'_': 0x1000})
            assemble(lexer.tokenize(f'bne {target}')[:-1], context)
            self.assertEqual(context.errors, [f'error: Branch destination out of range [-128..127]: {dist}'])


if __name__ == '__main__':
    unittest.main()
