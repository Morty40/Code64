#! /usr/bin/env python3
"""The 6502 instructions: assembles an instruction line, e.g. lda #1."""

import unittest

import cpu
import evaluate
import lexer
from context import Context
from cpu import lo, hi


def assemble(tokens: list, context: Context):
    """Assemble an instruction, with the address mode given by the operand.

    Zero page modes are chosen for addresses below $100.
    """
    mnemonic = tokens[0].string
    operand = lexer.join(tokens[1:])
        
    instruction = cpu.instructionWithMnemonic(mnemonic)
    opcodes = instruction.opcodes
        
    data = []
    
    if cpu.AddressMode.accumulator in opcodes and not operand:
        data = [opcodes[cpu.AddressMode.accumulator]]
        
    elif cpu.AddressMode.implied in opcodes and not operand:
        data = [opcodes[cpu.AddressMode.implied]]
        
    elif cpu.AddressMode.immediate in opcodes and operand.startswith('#'):
        v = evaluate.byteExpression(operand[1:], context)
        data = [opcodes[cpu.AddressMode.immediate], v]
        
    elif cpu.AddressMode.indirectX in opcodes and operand.startswith('(') and operand.endswith(',x)'):
        v = evaluate.byteExpression(operand[1:-3], context)
        data = [opcodes[cpu.AddressMode.indirectX], v]

    elif cpu.AddressMode.indirectY in opcodes and operand.startswith('(') and operand.endswith('),y'):
        v = evaluate.byteExpression(operand[1:-3], context)
        data = [opcodes[cpu.AddressMode.indirectY], v]

    elif cpu.AddressMode.indirect in opcodes and operand.startswith('(') and operand.endswith(')'):
        v = evaluate.wordExpression(operand[1:-1], context)
        if lo(v) == 0xff:
            context.reportWarning(f'Indirect address located on page boundary: ${v:04x}')
        data = [opcodes[cpu.AddressMode.indirect], lo(v), hi(v)]

    elif cpu.AddressMode.relative in opcodes: # TODO: give warning about branching across page boundary
        v = evaluate.wordExpression(operand, context)
        # the offset counts from the address after the 2-byte branch instruction
        dist = v - context.symbols['_'] - 2
        if dist < -128 or dist > 127: # branch is out of range (signed byte)
            context.reportError(f'Branch destination out of range [-128..127]: {dist}')
            dist = 0
        data = [opcodes[cpu.AddressMode.relative], dist&0xff]

    elif (cpu.AddressMode.zeroPageX in opcodes or cpu.AddressMode.absoluteX in opcodes) and operand.endswith(',x'):
        v = evaluate.wordExpression(operand[:-2], context)
        if cpu.AddressMode.zeroPageX in opcodes and hi(v) == 0:
            data = [opcodes[cpu.AddressMode.zeroPageX], lo(v)]
        elif cpu.AddressMode.absoluteX in opcodes:
            data = [opcodes[cpu.AddressMode.absoluteX], lo(v), hi(v)]

    elif (cpu.AddressMode.zeroPageY in opcodes or cpu.AddressMode.absoluteY in opcodes) and operand.endswith(',y'):
        v = evaluate.wordExpression(operand[:-2], context)
        if cpu.AddressMode.zeroPageY in opcodes and hi(v) == 0:
            data = [opcodes[cpu.AddressMode.zeroPageY], lo(v)]
        elif cpu.AddressMode.absoluteY in opcodes:
            data = [opcodes[cpu.AddressMode.absoluteY], lo(v), hi(v)]

    elif (cpu.AddressMode.zeroPage in opcodes or cpu.AddressMode.absolute in opcodes) and operand:
        v = evaluate.wordExpression(operand, context)
        if cpu.AddressMode.zeroPage in opcodes and hi(v) == 0:
            data = [opcodes[cpu.AddressMode.zeroPage], lo(v)]
        elif cpu.AddressMode.absolute in opcodes:
            data = [opcodes[cpu.AddressMode.absolute], lo(v), hi(v)]

    if len(data) <= 0:
        context.reportError(f'Unknown instruction or address mode: {mnemonic} {operand}')
        
    # store the bytes
    for b in data:
        context.store(b)


################################################################################

class TestInstructions(unittest.TestCase):

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
        # one byte beyond +127 and -128, counted from $1002, the address after the branch
        for target, dist in [('$1082', 128), ('$0f81', -129)]:
            context = Context({'_': 0x1000})
            assemble(lexer.tokenize(f'bne {target}')[:-1], context)
            self.assertEqual(context.errors, [f'error: Branch destination out of range [-128..127]: {dist}'])


if __name__ == '__main__':
    unittest.main()
