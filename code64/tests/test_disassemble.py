#! /usr/bin/env python3
"""Tests of the disassembler."""

import contextlib
import io
import os
import tempfile
import unittest

from .. import assemble
from .. import cpu
from ..cpu import AddressMode
from ..disassemble import disassemble, disassembleFile, readLabels


class TestDisassemble(unittest.TestCase):
    """Tests of finding the code, and of the source written for code and data."""

    def _assemble(self, asmFile: str, prgFile: str) -> bytes:
        """Assemble a file without errors, and return the .prg file's bytes."""
        with contextlib.redirect_stdout(io.StringIO()):
            context = assemble.assembleFile(asmFile, prgFile)
        self.assertEqual(context.errors, [])
        with open(prgFile, 'rb') as f:
            return f.read()

    def _disassemble(self, prgFile: str, asmFile: str) -> str:
        """Disassemble a file, and return the source, which is also saved."""
        source = disassembleFile(prgFile, asmFile)
        with open(asmFile) as f:
            self.assertEqual(f.read(), source)
        return source

    def _lines(self, data: bytes, start: int=0x1000) -> list:
        """Disassemble, and return the lines after the header, with single spaces, and without the monitor comments."""
        return [' '.join(line.split(';')[0].split()) for line in disassemble(bytes(data), start).splitlines()[4:]]

    def testRoundtrip(self):
        """asm -> prg -> asm -> prg -> asm gives the same .prg and the same source, for code and data."""
        with tempfile.TemporaryDirectory() as directory:
            name = os.path.join(directory, 'test')
            for source in [
                '',                                                   # nothing stored
                '.byte 1, 2, 3\n',                                    # only data
                '.word $1234, 0\n.text "ABC"\n.string "DEF"\n',       # data from other directives
                '.org $2000\n.byte 1\n.org $2010\n.byte 2\n',         # a gap in the memory
                '.align 16\n.byte 1\n.align 16\nrts\n',               # code after a gap
                'lda $02\nlda $1234\nlda #$12\nlda $02,x\nldx $02,y\nlda ($02,x)\nlda ($02),y\nrts\n', # operands
                'start: ldx #3\n_loop: dex\nbne _loop\njsr sub\njmp start\n.byte 1, 2\nsub: rts\n', # labels, code and data
                '.python\n    def delay(n):\n        return f"ldx #{n}\\n_loop: dex\\nbne _loop\\n"\n.end\n@delay(3)\n@delay(5)\nrts\n', # a generator
            ]:
                with self.subTest(source=source):
                    with open(name + '.asm', 'w') as f:
                        f.write(source)
                    prg1 = self._assemble(name + '.asm', name + '1.prg')
                    source1 = self._disassemble(name + '1.prg', name + '1.asm')
                    prg2 = self._assemble(name + '1.asm', name + '2.prg')
                    source2 = self._disassemble(name + '2.prg', name + '2.asm')
                    self.assertEqual(prg1, prg2)
                    self.assertEqual(source1, source2)
                    self.assertNotIn('@', source1) # no generators

    def testRoundtripInstructions(self):
        """Every instruction in every address mode is disassembled as code, and assembles to the same bytes."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, prgFile = os.path.join(directory, 'test.asm'), os.path.join(directory, 'test.prg')
            for opcode in range(0x100):
                if not (found := cpu.instructionForOpcode(opcode)):
                    continue
                instruction, mode = found
                operand = '_' if mode is AddressMode.RELATIVE else '$1234' if mode.size == 3 else '$12'
                source = f'{instruction.mnemonic} {mode.syntax(operand)}\nrts\n'
                with self.subTest(source=source):
                    with open(asmFile, 'w') as f:
                        f.write(source)
                    prg = self._assemble(asmFile, prgFile)
                    self._disassemble(prgFile, asmFile)
                    self.assertEqual(self._assemble(asmFile, prgFile), prg)
                    if instruction.mnemonic != 'brk': # brk is treated as data
                        self.assertIn(instruction.mnemonic, [line.partition(' ')[0] for line in self._lines(prg[2:])])

    def testLabels(self):
        """Branch, jmp and jsr destinations in the code get labels."""
        self.assertEqual(self._lines([0xa2, 0x05,         # $1000 ldx #5
                                      0xca,               # $1002 dex
                                      0xd0, 0xfd,         # $1003 bne $1002
                                      0x20, 0x0c, 0x10,   # $1005 jsr $100c
                                      0x4c, 0xd2, 0xff,   # $1008 jmp $ffd2, outside the program
                                      0x02,               # $100b data
                                      0x8d, 0x20, 0xd0,   # $100c sta $d020
                                      0x60]),             # $100f rts
            ['ldx #$05', 'l1002:', 'dex', 'bne l1002', 'jsr l100c', 'jmp $ffd2', '',
             '.byte $02', '',
             'l100c:', 'sta $d020', 'rts'])

    def testNames(self):
        """Names, e.g. from a labels file, are used for their addresses, with generated labels for the other destinations.
        Labels are alone on their line, and split the data. Names outside the program, or inside an instruction,
        are assigned at the top if the code uses them."""
        data = bytes([0xa5, 0x02,         # $1000 lda $02
                      0x20, 0x08, 0x10,   # $1002 jsr $1008
                      0x4c, 0x05, 0x10,   # $1005 jmp $1005
                      0xbd, 0x0c, 0x10,   # $1008 lda $100c,x
                      0x60,               # $100b rts
                      0x01, 0x02, 0x03])  # $100c data
        names = {0x0002: 'counter', 0x1008: 'draw', 0x100c: 'table', 0x100e: 'table_end',
                 0x1009: 'draw_operand', 0xffd2: 'CHROUT'} # not used, so not assigned
        self.assertEqual(disassemble(data, 0x1000, names),
            '; disassembled by Code64\n'
            '\n'
            'counter = $02\n'
            '\n'
            '            .org $1000\n'
            '\n'
            '            lda counter ; 1000  A5 02     LDA $02\n'
            '            jsr draw    ; 1002  20 08 10  JSR $1008\n'
            'l1005:\n'
            '            jmp l1005   ; 1005  4C 05 10  JMP $1005\n'
            'draw:\n'
            '            lda table,x ; 1008  BD 0C 10  LDA $100C,X\n'
            '            rts         ; 100B  60        RTS\n'
            '\n'
            'table:\n'
            '            .byte $01, $02\n'
            'table_end:\n'
            '            .byte $03\n')

    def testMonitorComments(self):
        """Each line of code ends with the instruction as a monitor shows it: its address, bytes, and the operand as a number.
        The comments are aligned, as a second column, and .byte lines have none, also when they are code."""
        self.assertEqual(disassemble(bytes([0xad, 0x10, 0x00,   # $1000 lda $0010, written as .byte
                                            0x0a,               # $1003 asl
                                            0xa9, 0x7f,         # $1004 lda #$7f
                                            0xd0, 0xfb,         # $1006 bne $1003
                                            0x60,               # $1008 rts
                                            0x02]), 0x1000).splitlines()[4:],   # $1009 data
            ['            .byte $ad, $10, $00',
             'l1003:',
             '            asl       ; 1003  0A        ASL',
             '            lda #$7f  ; 1004  A9 7F     LDA #$7F',
             '            bne l1003 ; 1006  D0 FB     BNE $1003',
             '            rts       ; 1008  60        RTS',
             '',
             '            .byte $02'])

    def testReadLabels(self):
        """A labels file is Python: its int values are names for addresses, the first name for each address."""
        with tempfile.TemporaryDirectory() as directory:
            labelsFile = os.path.join(directory, 'labels.py')
            with open(labelsFile, 'w') as f:
                f.write('start = 0x1000\nstart_loop = 0x1000\nirq = 0x1040\nNAME = "text"\n')
            self.assertEqual(readLabels(labelsFile), {0x1000: 'start', 0x1040: 'irq'})

    def testFindCode(self):
        """Code is found anywhere, e.g. after a BASIC line, or an interrupt handler only reached through a vector."""
        basic = [0x0b, 0x08, 0x0a, 0x00, 0x9e, *b'2061', 0x00, 0x00, 0x00] # 10 SYS2061
        self.assertEqual(self._lines(basic + [0xee, 0x20, 0xd0, 0x60], 0x0801),
            ['.byte $0b, $08, $0a, $00, $9e, $32, $30, $36, $31, $00, $00, $00', '', 'inc $d020', 'rts'])
        self.assertEqual(self._lines([0x60, 0x02, 0xee, 0x20, 0xd0, 0x40]),
            ['rts', '', '.byte $02', '', 'inc $d020', 'rti'])

    def testData(self):
        """Bytes that aren't code are data, in rows of up to 16 bytes, and 16 or more of the same byte are a .bytefill."""
        for data, expected in [
            ([0x60, *range(1, 19)],                 ['rts', '', '.byte ' + ', '.join(f'${b:02x}' for b in range(1, 17)), '.byte $11, $12']),
            ([0xea, 0x02, 0xea],                    ['.byte $ea, $02, $ea']),                 # runs into an unknown opcode, and the end
            ([0x4c, 0x04, 0x10, 0x60, 0x02],        ['.byte $4c, $04, $10', '', 'rts', '', '.byte $02']), # jumps to an unknown opcode
            ([0xea, 0x00, 0x60],                    ['.byte $ea, $00', '', 'rts']),           # runs into brk
            ([0x60, *[0]*16, *[0xff]*35],           ['rts', '', '.bytefill 16', '.bytefill 35, "x: 0xff"']),
            ([0x60, *[0]*15],                       ['rts', '', '.byte ' + ', '.join(['$00'] * 15)]),
            ([0xad, 0x10, 0x00, 0xb9, 0x10, 0x00, 0x60], ['.byte $ad, $10, $00', 'lda $0010,y', 'rts']), # absolute below $100 would assemble as zero page, but lda has no zero page,y
        ]:
            with self.subTest(data=data[:6]):
                self.assertEqual(self._lines(data), expected)

    def testBlankLines(self):
        """A blank line after rts and rti, as something new most likely starts there, and between code and data."""
        self.assertEqual(self._lines([0x20, 0x05, 0x10,   # jsr $1005
                                      0x40,               # rti
                                      0x02,               # data
                                      0x60]),             # rts, at the end
            ['jsr l1005', 'rti', '', '.byte $02', '', 'l1005:', 'rts'])

    def testFiles(self):
        """A .prg file starts with its address, other files are at the default address. The source is
        returned, and only saved if there is an output file."""
        with tempfile.TemporaryDirectory() as directory:
            for fileName, data, org in [('a.prg', [0x00, 0xc0, 0x60], '.org $c000'),
                                        ('a.bin', [0x60], '.org $1000')]:
                with open(os.path.join(directory, fileName), 'wb') as f:
                    f.write(bytes(data))
                source = self._disassemble(os.path.join(directory, fileName), os.path.join(directory, 'a.asm'))
                self.assertIn(org, source)
                self.assertIn('rts', source)
            self.assertEqual(disassembleFile(os.path.join(directory, 'a.prg')), self._disassemble(os.path.join(directory, 'a.prg'), os.path.join(directory, 'a.asm')))
            self.assertEqual(sorted(os.listdir(directory)), ['a.asm', 'a.bin', 'a.prg']) # nothing else saved
            with self.assertRaises(FileNotFoundError):
                disassembleFile(os.path.join(directory, 'missing.prg'), os.path.join(directory, 'a.asm'))


if __name__ == '__main__':
    unittest.main()
