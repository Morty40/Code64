#! /usr/bin/env python3

# https://en.wikipedia.org/wiki/MOS_Technology_6502
# https://www.masswerk.at/6502/6502_instruction_set.html

from enum import Enum
import unittest

class AddressMode(Enum):
    absolute    = 'absolute'
    absoluteX   = 'absolute,x'
    absoluteY   = 'absolute,y'
    accumulator = 'accumulator'
    immediate   = 'immediate'
    implied     = 'implied'
    indirect    = '(indirect)'
    indirectX   = '(indirect,x)'
    indirectY   = '(indirect),y'
    relative    = 'relative'
    zeroPage    = 'zeropage'
    zeroPageX   = 'zeropage,x'
    zeroPageY   = 'zeropage,y'


class Instruction:

    def __init__(self, mnemonic,
                absolute    = None,
                absoluteX   = None,
                absoluteY   = None,
                accumulator = None,
                immediate   = None,
                implied     = None,
                indirect    = None,
                indirectX   = None,
                indirectY   = None,
                relative    = None,
                zeroPage    = None,
                zeroPageX   = None,
                zeroPageY   = None):
        self.mnemonic = mnemonic
        self.opcodes = {}
        if absolute    is not None: self.opcodes[AddressMode.absolute   ] = absolute
        if absoluteX   is not None: self.opcodes[AddressMode.absoluteX  ] = absoluteX
        if absoluteY   is not None: self.opcodes[AddressMode.absoluteY  ] = absoluteY
        if accumulator is not None: self.opcodes[AddressMode.accumulator] = accumulator
        if immediate   is not None: self.opcodes[AddressMode.immediate  ] = immediate
        if implied     is not None: self.opcodes[AddressMode.implied    ] = implied
        if indirect    is not None: self.opcodes[AddressMode.indirect   ] = indirect
        if indirectX   is not None: self.opcodes[AddressMode.indirectX  ] = indirectX
        if indirectY   is not None: self.opcodes[AddressMode.indirectY  ] = indirectY
        if relative    is not None: self.opcodes[AddressMode.relative   ] = relative
        if zeroPage    is not None: self.opcodes[AddressMode.zeroPage   ] = zeroPage
        if zeroPageX   is not None: self.opcodes[AddressMode.zeroPageX  ] = zeroPageX
        if zeroPageY   is not None: self.opcodes[AddressMode.zeroPageY  ] = zeroPageY


instructionSet = {
    Instruction('adc', absolute=0x6d, absoluteX=0x7d, absoluteY=0x79, immediate=0x69, indirectX=0x61, indirectY=0x71, zeroPage=0x65, zeroPageX=0x75),
    Instruction('and', absolute=0x2d, absoluteX=0x3d, absoluteY=0x39, immediate=0x29, indirectX=0x21, indirectY=0x31, zeroPage=0x25, zeroPageX=0x35),
    Instruction('asl', absolute=0x0e, absoluteX=0x1e, accumulator=0x0a, zeroPage=0x06, zeroPageX=0x16),
    Instruction('bcc', relative=0x90),
    Instruction('bcs', relative=0xb0),
    Instruction('beq', relative=0xf0),
    Instruction('bit', absolute=0x2c, zeroPage=0x24),
    Instruction('bmi', relative=0x30),
    Instruction('bne', relative=0xd0),
    Instruction('bpl', relative=0x10),
    Instruction('brk', implied=0x00),
    Instruction('bvc', relative=0x50),
    Instruction('bvs', relative=0x70),
    Instruction('clc', implied=0x18),
    Instruction('cld', implied=0xd8),
    Instruction('cli', implied=0x58),
    Instruction('clv', implied=0xb8),
    Instruction('cmp', absolute=0xcd, absoluteX=0xdd, absoluteY=0xd9, immediate=0xc9, indirectX=0xc1, indirectY=0xd1, zeroPage=0xc5, zeroPageX=0xd5),
    Instruction('cpx', absolute=0xec, immediate=0xe0, zeroPage=0xe4),
    Instruction('cpy', absolute=0xcc, immediate=0xc0, zeroPage=0xc4),    
    Instruction('dec', absolute=0xce, absoluteX=0xde, zeroPage=0xc6, zeroPageX=0xd6),
    Instruction('dex', implied=0xca),
    Instruction('dey', implied=0x88),
    Instruction('eor', absolute=0x4d, absoluteX=0x5d, absoluteY=0x59, immediate=0x49, indirectX=0x41, indirectY=0x51, zeroPage=0x45, zeroPageX=0x55),
    Instruction('inc', absolute=0xee, absoluteX=0xfe, zeroPage=0xe6, zeroPageX=0xf6),
    Instruction('inx', implied=0xe8),
    Instruction('iny', implied=0xc8),
    Instruction('jmp', absolute=0x4c, indirect=0x6c),
    Instruction('jsr', absolute=0x20),
    Instruction('lda', absolute=0xad, absoluteX=0xbd, absoluteY=0xb9, immediate=0xa9, indirectX=0xa1, indirectY=0xb1, zeroPage=0xa5, zeroPageX=0xb5),
    Instruction('ldx', absolute=0xae, absoluteY=0xbe, immediate=0xa2, zeroPage=0xa6, zeroPageY=0xb6),
    Instruction('ldy', absolute=0xac, absoluteX=0xbc, immediate=0xa0, zeroPage=0xa4, zeroPageX=0xb4),
    Instruction('lsr', absolute=0x4e, absoluteX=0x5e, accumulator=0x4a, zeroPage=0x46, zeroPageX=0x56),
    Instruction('nop', implied=0xea),        
    Instruction('ora', absolute=0x0d, absoluteX=0x1d, absoluteY=0x19, immediate=0x09, indirectX=0x01, indirectY=0x11, zeroPage=0x05, zeroPageX=0x15),
    Instruction('pha', implied=0x48),
    Instruction('php', implied=0x08),
    Instruction('pla', implied=0x68),
    Instruction('plp', implied=0x28),
    Instruction('rol', absolute=0x2e, absoluteX=0x3e, accumulator=0x2a, zeroPage=0x26, zeroPageX=0x36),
    Instruction('ror', absolute=0x6e, absoluteX=0x7e, accumulator=0x6a, zeroPage=0x66, zeroPageX=0x76),
    Instruction('rti', implied=0x40),
    Instruction('rts', implied=0x60),    
    Instruction('sbc', absolute=0xed, absoluteX=0xfd, absoluteY=0xf9, immediate=0xe9, indirectX=0xe1, indirectY=0xf1, zeroPage=0xe5, zeroPageX=0xf5),
    Instruction('sec', implied=0x38),
    Instruction('sed', implied=0xf8),
    Instruction('sei', implied=0x78),
    Instruction('sta', absolute=0x8d, absoluteX=0x9d, absoluteY=0x99, indirectX=0x81, indirectY=0x91, zeroPage=0x85, zeroPageX=0x95),
    Instruction('stx', absolute=0x8e, zeroPage=0x86, zeroPageY=0x96),
    Instruction('sty', absolute=0x8c, zeroPage=0x84, zeroPageX=0x94),
    Instruction('tax', implied=0xaa),
    Instruction('tay', implied=0xa8),
    Instruction('tsx', implied=0xba),
    Instruction('txa', implied=0x8a),
    Instruction('txs', implied=0x9a),
    Instruction('tya', implied=0x98)}

_mnemonicMap = {instruction.mnemonic: instruction for instruction in instructionSet}


def instructionWithMnemonic(mnemonic: str) -> Instruction:
    return _mnemonicMap[mnemonic] if mnemonic in _mnemonicMap else None


def isMnemonic(mnemonic: str) -> bool:
    """ check if string is an instruction mnemonic """
    return instructionWithMnemonic(mnemonic) != None


################################################################################


class TestCpu(unittest.TestCase):

    def testInstructionSet(self):
        self.assertEqual(len(instructionSet), 56)
        
        i = instructionWithMnemonic('lda')
        self.assertEqual(i.mnemonic, 'lda')

        i = instructionWithMnemonic('xxx')
        self.assertEqual(i, None)


    def testIsMnemonic(self):
        self.assertEqual(isMnemonic(''), False)
        self.assertEqual(isMnemonic('a'), False)
        self.assertEqual(isMnemonic('yyy'), False)
        self.assertEqual(isMnemonic('lda'), True)
        self.assertEqual(isMnemonic('sta'), True)
        self.assertEqual(isMnemonic('nop'), True)
        

if __name__ == '__main__':
    unittest.main()


# IDEA: support for illegal instructions
# IDEA: cycle counting for instructions
