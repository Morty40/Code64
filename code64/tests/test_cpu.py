#! /usr/bin/env python3
"""Tests of the 6502 instruction set."""

import unittest

from ..cpu import (
    AddressMode,
    Instruction,
    instructionForOpcode,
    _instructionSet,
    instructionWithMnemonic,
    isMnemonic,
    setIllegalInstructions,
    _stableIllegalInstructionSet,
    _unstableIllegalInstructionSet,
)


class TestCpu(unittest.TestCase):
    """Tests of the instruction set table and lookups.

    The opcodes themselves are tested by testOpcodes and testIllegalOpcodes in
    test_instructions.py, which assemble every instruction in every address mode.
    """

    def testInstructionSet(self):
        """The table has all instructions, and they can be looked up by mnemonic."""
        self.assertEqual(len(_instructionSet), 56) # the documented 6502 instructions

        i = instructionWithMnemonic('lda')
        self.assertEqual(i.mnemonic, 'lda')

        i = instructionWithMnemonic('xxx')
        self.assertEqual(i, None)


    def testInstructionForOpcode(self):
        """Each opcode gives its instruction and address mode, the reverse of the instruction set table."""
        instruction, mode = instructionForOpcode(0xa9)
        self.assertEqual((instruction.mnemonic, mode), ('lda', AddressMode.immediate))
        instruction, mode = instructionForOpcode(0x60)
        self.assertEqual((instruction.mnemonic, mode), ('rts', AddressMode.implied))
        self.assertEqual(instructionForOpcode(0x02), None) # jam, freezes the cpu


    def _setIllegalInstructions(self, illegal: str):
        """Choose the illegal instructions for this test only."""
        self.addCleanup(setIllegalInstructions, 'stable')
        setIllegalInstructions(illegal)


    def _opcodeCount(self) -> int:
        """The number of opcodes in use."""
        return sum(instructionForOpcode(opcode) is not None for opcode in range(256))


    def testIllegalInstructionSets(self):
        """The number of stable and unstable illegal instructions."""
        self.assertEqual(len(_stableIllegalInstructionSet), 13)
        self.assertEqual(len(_unstableIllegalInstructionSet), 6)


    def testIllegalDefault(self):
        """The stable illegal instructions are the default."""
        self.assertEqual(self._opcodeCount(), 208)


    def testIllegalNone(self):
        """'none' leaves only the documented 6502 opcodes."""
        self._setIllegalInstructions('none')
        self.assertEqual(self._opcodeCount(), 151)
        self.assertEqual((isMnemonic('lax'), instructionForOpcode(0xa7)), (False, None))


    def testIllegalStable(self):
        """'stable' adds the stable illegal instructions, but not the illegal nops, usbc, or the unstable ones."""
        self._setIllegalInstructions('stable')
        self.assertEqual(self._opcodeCount(), 208)
        self.assertEqual(instructionForOpcode(0xa7), (instructionWithMnemonic('lax'), AddressMode.zeroPage))
        self.assertEqual(instructionForOpcode(0x04), None) # an illegal nop
        self.assertEqual(instructionForOpcode(0xeb), None) # usbc, the same as sbc #
        self.assertEqual(isMnemonic('sha'), False)         # unstable


    def testIllegalAll(self):
        """'all' also adds the unstable illegal instructions, but still not the illegal nops."""
        self._setIllegalInstructions('all')
        self.assertEqual(self._opcodeCount(), 215)
        self.assertEqual(instructionWithMnemonic('nop').opcodes, {AddressMode.implied: 0xea})
        self.assertEqual(instructionForOpcode(0x9f), (instructionWithMnemonic('sha'), AddressMode.absoluteY))


    def testIllegalUnknown(self):
        """Any other choice is an error."""
        self.assertRaises(KeyError, setIllegalInstructions, 'some')


    def testIsMnemonic(self):
        """Only instruction mnemonics are recognized, in lowercase."""
        self.assertEqual(isMnemonic(''), False)
        self.assertEqual(isMnemonic('xxx'), False)
        self.assertEqual(isMnemonic('lda'), True)
        self.assertEqual(isMnemonic('sta'), True)
        self.assertEqual(isMnemonic('nop'), True)
        self.assertEqual(isMnemonic('LDA'), False)


    def testSize(self):
        """The size of an instruction, by address mode: the opcode, and a byte or word operand."""
        self.assertEqual(AddressMode.implied.size, 1)        # rts
        self.assertEqual(AddressMode.accumulator.size, 1)    # asl
        self.assertEqual(AddressMode.immediate.size, 2)      # lda #$01
        self.assertEqual(AddressMode.relative.size, 2)       # bne label
        self.assertEqual(AddressMode.indirectY.size, 2)      # lda ($10),y
        self.assertEqual(AddressMode.absoluteX.size, 3)      # lda $1234,x
        self.assertEqual(AddressMode.indirect.size, 3)       # jmp ($1234)


    def testSyntax(self):
        """The operand of each address mode, written in assembler syntax."""
        for mode, expected in [(AddressMode.implied, ''),        (AddressMode.accumulator, ''),
                               (AddressMode.immediate, '#$10'),  (AddressMode.relative, '$10'),
                               (AddressMode.zeroPage, '$10'),    (AddressMode.zeroPageX, '$10,x'),
                               (AddressMode.zeroPageY, '$10,y'), (AddressMode.indirectX, '($10,x)'),
                               (AddressMode.indirectY, '($10),y'), (AddressMode.absolute, '$10'),
                               (AddressMode.absoluteX, '$10,x'), (AddressMode.absoluteY, '$10,y'),
                               (AddressMode.indirect, '($10)')]:
            with self.subTest(mode=mode):
                self.assertEqual(mode.syntax('$10'), expected)


    def testZeroPageMode(self):
        """The zero page mode that is chosen instead of an absolute mode, for addresses below $100."""
        self.assertEqual(AddressMode.absolute.zeroPageMode, AddressMode.zeroPage)
        self.assertEqual(AddressMode.absoluteX.zeroPageMode, AddressMode.zeroPageX)
        self.assertEqual(AddressMode.absoluteY.zeroPageMode, AddressMode.zeroPageY)
        self.assertEqual(AddressMode.indirect.zeroPageMode, None) # always a word
        self.assertEqual(AddressMode.zeroPage.zeroPageMode, None)


    def testUnknownAddressMode(self):
        """A misspelled address mode in the table is an error when the module is loaded."""
        self.assertRaises(KeyError, Instruction, 'xxx', zeroPagee=0x00)


if __name__ == '__main__':
    unittest.main()
