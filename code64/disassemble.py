#! /usr/bin/env python3
"""The disassembler: turns a .prg or binary file into source that assembles to the same bytes."""

import contextlib
import glob
import io
import os
import tempfile
import unittest

from . import assemble
from . import cpu
from .cpu import AddressMode

def _decode(data: bytes, start: int, address: int):
    """Decode the instruction at address: (instruction, mode, operand, size), or None if it isn't one.

    The operand of a branch is its destination address.
    """
    index = address - start
    if not 0 <= index < len(data) or not (found := cpu.instructionForOpcode(data[index])):
        return None
    instruction, mode = found
    size = mode.size
    if index + size > len(data):
        return None
    operand = int.from_bytes(data[index+1:index+size], 'little')
    if mode is AddressMode.relative:
        operand = address + 2 + (operand ^ 0x80) - 0x80 # signed offset, from the next instruction
        if not 0 <= operand <= 0xffff:
            return None
    return instruction, mode, operand, size


def _jumpsTo(instruction, mode) -> bool:
    """Check if the operand is a code address: a branch, jmp or jsr destination."""
    return mode is AddressMode.relative or (instruction.mnemonic in ('jmp', 'jsr') and mode is AddressMode.absolute)


def _trace(data: bytes, start: int, entry: int, code: dict, used: set):
    """Find the new code that can be reached from entry, by following branches, jumps and subroutine calls.

    Returns {address: (instruction, mode, operand, size)}, or None if it isn't code: every path must end
    with jmp, rts or rti, or in known code, before it runs into an unknown opcode, brk, the middle of an
    instruction, or the end.
    """
    new, newUsed = {}, set()
    todo = [entry]
    while todo:
        address = todo.pop()
        while address not in code and address not in new:
            decoded = _decode(data, start, address)
            if decoded is None:
                return None
            instruction, mode, operand, size = decoded
            span = range(address, address + size)
            if instruction.mnemonic == 'brk' or not used.isdisjoint(span) or not newUsed.isdisjoint(span):
                return None
            new[address] = decoded
            newUsed.update(span)
            if _jumpsTo(instruction, mode) and start <= operand < start + len(data):
                todo.append(operand)
            if instruction.mnemonic in ('jmp', 'rts', 'rti'):
                break
            address += size
    return new


def _findCode(data: bytes, start: int) -> dict:
    """Find the code, by trying each byte that isn't code yet as the start of some.

    Returns {address: (instruction, mode, operand, size)} for each instruction.
    """
    code, used = {}, set()
    for address in range(start, start + len(data)):
        if address not in used and (new := _trace(data, start, address, code, used)):
            code.update(new)
            used.update(a for address, (*_, size) in new.items() for a in range(address, address + size))
    return code


def disassemble(data: bytes, start: int) -> str:
    """Disassemble data at the start address into Code64 source.

    Code is found anywhere, other bytes are data, and branch and jump destinations get labels.
    """
    end = start + len(data)
    code = _findCode(data, start)
    labels = {operand: f'l{operand:04x}' for instruction, mode, operand, _ in code.values()
              if _jumpsTo(instruction, mode) and operand in code}

    def line(address: int, text: str) -> str:
        label = labels[address] + ':' if address in labels else ''
        return f'{label:<12}{text}'

    def byteList(values) -> str:
        return '.byte ' + ', '.join(f'${b:02x}' for b in values)

    lines = ['; disassembled by Code64', '', f'{"":<12}.org ${start:04x}', '']
    address, wasCode = start, None
    while address < end:
        if lines[-1] and (address in code) != wasCode:
            lines.append('') # between code and data
        wasCode = address in code
        if wasCode:
            instruction, mode, operand, size = code[address]
            if mode.zeroPageMode in instruction.opcodes and operand < 0x100:
                text = byteList(data[address-start:address-start+size]) # would assemble as zero page
            else:
                if size == 3 or mode is AddressMode.relative:
                    operand = labels.get(operand, f'${operand:04x}')
                elif size == 2:
                    operand = f'${operand:02x}'
                text = f'{instruction.mnemonic} {mode.syntax(operand)}'.strip()
        else:
            # data up to the next code: 16 or more of the same byte, or else up to 16 bytes
            stop = next((a for a in range(address, end) if a in code), end)
            chunk = data[address-start:stop-start]
            size = len(chunk) - len(chunk.lstrip(chunk[:1])) # the bytes equal to the first
            if size >= 16:
                text = f'.bytefill {size}' + (f', "x: 0x{chunk[0]:02x}"' if chunk[0] else '')
            else:
                size = min(len(chunk), 16)
                text = byteList(chunk[:size])
        lines.append(line(address, text))
        if wasCode and instruction.mnemonic in ('rts', 'rti'):
            lines.append('') # something new most likely starts here
        address += size

    return '\n'.join(lines).rstrip() + '\n'


def disassembleFile(inFile: str, outFile: str = None) -> str:
    """Disassemble a .prg file, which starts with its load address, or another binary file
    loaded at the default address. Saves the source to outFile, if given, and returns it.
    Raises OSError if a file can't be read or written.
    """
    with open(inFile, 'rb') as f:
        data = f.read()

    if inFile.lower().endswith('.prg') and len(data) >= 2:
        start, data = data[0] + data[1]*256, data[2:]
    else:
        start = assemble.DEFAULT_ORIGIN

    source = disassemble(data, start)
    if outFile:
        with open(outFile, 'w') as f:
            f.write(source)
    return source


################################################################################

class TestDisassemble(unittest.TestCase):

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
        """Disassemble, and return the lines after the header, with single spaces."""
        return [' '.join(line.split()) for line in disassemble(bytes(data), start).splitlines()[4:]]

    def testRoundtrip(self):
        """asm -> prg -> asm -> prg -> asm gives the same .prg and the same source, for every test case."""
        root = os.path.dirname(os.path.abspath(__file__))
        with tempfile.TemporaryDirectory() as directory:
            for asmFile in sorted(glob.glob(os.path.join(root, 'testcases', '*.asm'))):
                name = os.path.join(directory, os.path.basename(asmFile)[:-4])
                with self.subTest(asmFile=os.path.basename(asmFile)):
                    prg1 = self._assemble(asmFile, name + '1.prg')
                    source1 = self._disassemble(name + '1.prg', name + '1.asm')
                    prg2 = self._assemble(name + '1.asm', name + '2.prg')
                    source2 = self._disassemble(name + '2.prg', name + '2.asm')
                    self.assertEqual(prg1, prg2)
                    self.assertEqual(source1, source2)
                    self.assertNotIn('@', source1) # no generators

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
            ['ldx #$05', 'l1002: dex', 'bne l1002', 'jsr l100c', 'jmp $ffd2', '',
             '.byte $02', '',
             'l100c: sta $d020', 'rts'])

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
            ['jsr l1005', 'rti', '', '.byte $02', '', 'l1005: rts'])

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
