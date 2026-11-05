#! /usr/bin/env python3
"""The 6502 instructions: assembles an instruction line, e.g. lda #1."""

from . import cpu
from . import evaluate
from . import lexer
from .context import Context
from .cpu import lo, hi


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
