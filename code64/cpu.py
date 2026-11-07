#! /usr/bin/env python3
"""The 6502 instruction set: the opcode of each instruction in each address mode."""

# https://en.wikipedia.org/wiki/MOS_Technology_6502
# https://www.masswerk.at/6502/6502_instruction_set.html

from enum import Enum
import re

# the low and high byte of a 16-bit value, the 6502 stores words low byte first
def lo(x):
    """The low byte."""
    return x&0xff

def hi(x):
    """The high byte."""
    return (x>>8)&0xff


class AddressMode(Enum):
    """The 6502 address modes. The values are the operand syntax, see syntax()."""

    ABSOLUTE    = 'absolute'
    ABSOLUTE_X  = 'absolute,x'
    ABSOLUTE_Y  = 'absolute,y'
    ACCUMULATOR = 'accumulator'
    IMMEDIATE   = 'immediate'
    IMPLIED     = 'implied'
    INDIRECT    = '(indirect)'
    INDIRECT_X  = '(indirect,x)'
    INDIRECT_Y  = '(indirect),y'
    RELATIVE    = 'relative'
    ZERO_PAGE   = 'zeropage'
    ZERO_PAGE_X = 'zeropage,x'
    ZERO_PAGE_Y = 'zeropage,y'

    @property
    def size(self) -> int:
        """The size of an instruction in this mode: the opcode, and a byte or word operand."""
        if self in (AddressMode.IMPLIED, AddressMode.ACCUMULATOR):
            return 1
        if self in (AddressMode.ABSOLUTE, AddressMode.ABSOLUTE_X, AddressMode.ABSOLUTE_Y, AddressMode.INDIRECT):
            return 3
        return 2

    @property
    def zeroPageMode(self):
        """The zero page mode the assembler chooses instead of this mode for addresses below $100, or None."""
        return {AddressMode.ABSOLUTE: AddressMode.ZERO_PAGE,
                AddressMode.ABSOLUTE_X: AddressMode.ZERO_PAGE_X,
                AddressMode.ABSOLUTE_Y: AddressMode.ZERO_PAGE_Y}.get(self)

    def syntax(self, operand: str) -> str:
        """Write the operand in this mode, e.g. '($10),y' for INDIRECT_Y and '$10'."""
        if self in (AddressMode.IMPLIED, AddressMode.ACCUMULATOR):
            return ''
        if self is AddressMode.IMMEDIATE:
            return '#' + operand
        return re.sub(r'[a-z]+', lambda _: operand, self.value, count=1) # e.g. (indirect),y


class Instruction:
    """An instruction mnemonic, and its opcode for each address mode it supports."""

    def __init__(self, mnemonic, **opcodes):
        """Opcodes are given by address mode name, e.g. IMMEDIATE=0xa9."""
        self.mnemonic = mnemonic
        self.opcodes = {AddressMode[mode]: opcode for mode, opcode in opcodes.items()}


_instructionSet = {
    Instruction('adc', ABSOLUTE=0x6d, ABSOLUTE_X=0x7d, ABSOLUTE_Y=0x79, IMMEDIATE=0x69, INDIRECT_X=0x61, INDIRECT_Y=0x71, ZERO_PAGE=0x65, ZERO_PAGE_X=0x75),
    Instruction('and', ABSOLUTE=0x2d, ABSOLUTE_X=0x3d, ABSOLUTE_Y=0x39, IMMEDIATE=0x29, INDIRECT_X=0x21, INDIRECT_Y=0x31, ZERO_PAGE=0x25, ZERO_PAGE_X=0x35),
    Instruction('asl', ABSOLUTE=0x0e, ABSOLUTE_X=0x1e, ACCUMULATOR=0x0a, ZERO_PAGE=0x06, ZERO_PAGE_X=0x16),
    Instruction('bcc', RELATIVE=0x90),
    Instruction('bcs', RELATIVE=0xb0),
    Instruction('beq', RELATIVE=0xf0),
    Instruction('bit', ABSOLUTE=0x2c, ZERO_PAGE=0x24),
    Instruction('bmi', RELATIVE=0x30),
    Instruction('bne', RELATIVE=0xd0),
    Instruction('bpl', RELATIVE=0x10),
    Instruction('brk', IMPLIED=0x00),
    Instruction('bvc', RELATIVE=0x50),
    Instruction('bvs', RELATIVE=0x70),
    Instruction('clc', IMPLIED=0x18),
    Instruction('cld', IMPLIED=0xd8),
    Instruction('cli', IMPLIED=0x58),
    Instruction('clv', IMPLIED=0xb8),
    Instruction('cmp', ABSOLUTE=0xcd, ABSOLUTE_X=0xdd, ABSOLUTE_Y=0xd9, IMMEDIATE=0xc9, INDIRECT_X=0xc1, INDIRECT_Y=0xd1, ZERO_PAGE=0xc5, ZERO_PAGE_X=0xd5),
    Instruction('cpx', ABSOLUTE=0xec, IMMEDIATE=0xe0, ZERO_PAGE=0xe4),
    Instruction('cpy', ABSOLUTE=0xcc, IMMEDIATE=0xc0, ZERO_PAGE=0xc4),
    Instruction('dec', ABSOLUTE=0xce, ABSOLUTE_X=0xde, ZERO_PAGE=0xc6, ZERO_PAGE_X=0xd6),
    Instruction('dex', IMPLIED=0xca),
    Instruction('dey', IMPLIED=0x88),
    Instruction('eor', ABSOLUTE=0x4d, ABSOLUTE_X=0x5d, ABSOLUTE_Y=0x59, IMMEDIATE=0x49, INDIRECT_X=0x41, INDIRECT_Y=0x51, ZERO_PAGE=0x45, ZERO_PAGE_X=0x55),
    Instruction('inc', ABSOLUTE=0xee, ABSOLUTE_X=0xfe, ZERO_PAGE=0xe6, ZERO_PAGE_X=0xf6),
    Instruction('inx', IMPLIED=0xe8),
    Instruction('iny', IMPLIED=0xc8),
    Instruction('jmp', ABSOLUTE=0x4c, INDIRECT=0x6c),
    Instruction('jsr', ABSOLUTE=0x20),
    Instruction('lda', ABSOLUTE=0xad, ABSOLUTE_X=0xbd, ABSOLUTE_Y=0xb9, IMMEDIATE=0xa9, INDIRECT_X=0xa1, INDIRECT_Y=0xb1, ZERO_PAGE=0xa5, ZERO_PAGE_X=0xb5),
    Instruction('ldx', ABSOLUTE=0xae, ABSOLUTE_Y=0xbe, IMMEDIATE=0xa2, ZERO_PAGE=0xa6, ZERO_PAGE_Y=0xb6),
    Instruction('ldy', ABSOLUTE=0xac, ABSOLUTE_X=0xbc, IMMEDIATE=0xa0, ZERO_PAGE=0xa4, ZERO_PAGE_X=0xb4),
    Instruction('lsr', ABSOLUTE=0x4e, ABSOLUTE_X=0x5e, ACCUMULATOR=0x4a, ZERO_PAGE=0x46, ZERO_PAGE_X=0x56),
    Instruction('nop', IMPLIED=0xea),
    Instruction('ora', ABSOLUTE=0x0d, ABSOLUTE_X=0x1d, ABSOLUTE_Y=0x19, IMMEDIATE=0x09, INDIRECT_X=0x01, INDIRECT_Y=0x11, ZERO_PAGE=0x05, ZERO_PAGE_X=0x15),
    Instruction('pha', IMPLIED=0x48),
    Instruction('php', IMPLIED=0x08),
    Instruction('pla', IMPLIED=0x68),
    Instruction('plp', IMPLIED=0x28),
    Instruction('rol', ABSOLUTE=0x2e, ABSOLUTE_X=0x3e, ACCUMULATOR=0x2a, ZERO_PAGE=0x26, ZERO_PAGE_X=0x36),
    Instruction('ror', ABSOLUTE=0x6e, ABSOLUTE_X=0x7e, ACCUMULATOR=0x6a, ZERO_PAGE=0x66, ZERO_PAGE_X=0x76),
    Instruction('rti', IMPLIED=0x40),
    Instruction('rts', IMPLIED=0x60),
    Instruction('sbc', ABSOLUTE=0xed, ABSOLUTE_X=0xfd, ABSOLUTE_Y=0xf9, IMMEDIATE=0xe9, INDIRECT_X=0xe1, INDIRECT_Y=0xf1, ZERO_PAGE=0xe5, ZERO_PAGE_X=0xf5),
    Instruction('sec', IMPLIED=0x38),
    Instruction('sed', IMPLIED=0xf8),
    Instruction('sei', IMPLIED=0x78),
    Instruction('sta', ABSOLUTE=0x8d, ABSOLUTE_X=0x9d, ABSOLUTE_Y=0x99, INDIRECT_X=0x81, INDIRECT_Y=0x91, ZERO_PAGE=0x85, ZERO_PAGE_X=0x95),
    Instruction('stx', ABSOLUTE=0x8e, ZERO_PAGE=0x86, ZERO_PAGE_Y=0x96),
    Instruction('sty', ABSOLUTE=0x8c, ZERO_PAGE=0x84, ZERO_PAGE_X=0x94),
    Instruction('tax', IMPLIED=0xaa),
    Instruction('tay', IMPLIED=0xa8),
    Instruction('tsx', IMPLIED=0xba),
    Instruction('txa', IMPLIED=0x8a),
    Instruction('txs', IMPLIED=0x9a),
    Instruction('tya', IMPLIED=0x98)}

# the "illegal" instructions that work the same on all 6510, 8500 and 8502 cpus. Left out are anc 0x2b
# and usbc 0xeb, which do the same as anc 0x0b and sbc 0xe9, the nops, which would conflict with nop, and
# the unstable ane, lxa, sha, shx, shy and tas, which depend on the cpu, its temperature, or dma
_illegalInstructionSet = {
    Instruction('alr', IMMEDIATE=0x4b),
    Instruction('anc', IMMEDIATE=0x0b),
    Instruction('arr', IMMEDIATE=0x6b),
    Instruction('dcp', ABSOLUTE=0xcf, ABSOLUTE_X=0xdf, ABSOLUTE_Y=0xdb, INDIRECT_X=0xc3, INDIRECT_Y=0xd3, ZERO_PAGE=0xc7, ZERO_PAGE_X=0xd7),
    Instruction('isc', ABSOLUTE=0xef, ABSOLUTE_X=0xff, ABSOLUTE_Y=0xfb, INDIRECT_X=0xe3, INDIRECT_Y=0xf3, ZERO_PAGE=0xe7, ZERO_PAGE_X=0xf7),
    Instruction('las', ABSOLUTE_Y=0xbb),
    Instruction('lax', ABSOLUTE=0xaf, ABSOLUTE_Y=0xbf, INDIRECT_X=0xa3, INDIRECT_Y=0xb3, ZERO_PAGE=0xa7, ZERO_PAGE_Y=0xb7),
    Instruction('rla', ABSOLUTE=0x2f, ABSOLUTE_X=0x3f, ABSOLUTE_Y=0x3b, INDIRECT_X=0x23, INDIRECT_Y=0x33, ZERO_PAGE=0x27, ZERO_PAGE_X=0x37),
    Instruction('rra', ABSOLUTE=0x6f, ABSOLUTE_X=0x7f, ABSOLUTE_Y=0x7b, INDIRECT_X=0x63, INDIRECT_Y=0x73, ZERO_PAGE=0x67, ZERO_PAGE_X=0x77),
    Instruction('sax', ABSOLUTE=0x8f, INDIRECT_X=0x83, ZERO_PAGE=0x87, ZERO_PAGE_Y=0x97),
    Instruction('sbx', IMMEDIATE=0xcb),
    Instruction('slo', ABSOLUTE=0x0f, ABSOLUTE_X=0x1f, ABSOLUTE_Y=0x1b, INDIRECT_X=0x03, INDIRECT_Y=0x13, ZERO_PAGE=0x07, ZERO_PAGE_X=0x17),
    Instruction('sre', ABSOLUTE=0x4f, ABSOLUTE_X=0x5f, ABSOLUTE_Y=0x5b, INDIRECT_X=0x43, INDIRECT_Y=0x53, ZERO_PAGE=0x47, ZERO_PAGE_X=0x57)}


_mnemonicMap: dict[str, Instruction] = {}
_opcodeMap: dict[int, tuple[Instruction, AddressMode]] = {}


def setIllegalInstructions(illegal: str):
    """Choose the illegal instructions to use with the regular ones: 'none' or 'stable'."""
    global _mnemonicMap, _opcodeMap
    instructions = {'none': _instructionSet,
                    'stable': _instructionSet | _illegalInstructionSet}[illegal]
    _mnemonicMap = {instruction.mnemonic: instruction for instruction in instructions}
    _opcodeMap = {opcode: (instruction, mode) for instruction in instructions for mode, opcode in instruction.opcodes.items()}


setIllegalInstructions('stable') # the default


def instructionWithMnemonic(mnemonic: str) -> Instruction | None:
    """Return the instruction for a lower case mnemonic, e.g. 'lda', or None."""
    return _mnemonicMap.get(mnemonic)


def instructionForOpcode(opcode: int) -> tuple[Instruction, AddressMode] | None:
    """Return the (instruction, address mode) of an opcode, e.g. 0xa9 is lda immediate, or None."""
    return _opcodeMap.get(opcode)


def isMnemonic(mnemonic: str) -> bool:
    """Check if a string is an instruction mnemonic."""
    return mnemonic in _mnemonicMap


# IDEA: cycle counting for instructions
