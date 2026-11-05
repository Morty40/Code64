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
    assert instruction is not None # the caller checked that it is a mnemonic
    opcodes = instruction.opcodes

    data = []

    if cpu.AddressMode.ACCUMULATOR in opcodes and not operand:
        data = [opcodes[cpu.AddressMode.ACCUMULATOR]]

    elif cpu.AddressMode.IMPLIED in opcodes and not operand:
        data = [opcodes[cpu.AddressMode.IMPLIED]]

    elif cpu.AddressMode.IMMEDIATE in opcodes and operand.startswith('#'):
        v = evaluate.byteExpression(operand[1:], context)
        data = [opcodes[cpu.AddressMode.IMMEDIATE], v]

    elif cpu.AddressMode.INDIRECT_X in opcodes and operand.startswith('(') and operand.endswith(',x)'):
        v = evaluate.byteExpression(operand[1:-3], context)
        data = [opcodes[cpu.AddressMode.INDIRECT_X], v]

    elif cpu.AddressMode.INDIRECT_Y in opcodes and operand.startswith('(') and operand.endswith('),y'):
        v = evaluate.byteExpression(operand[1:-3], context)
        data = [opcodes[cpu.AddressMode.INDIRECT_Y], v]

    elif cpu.AddressMode.INDIRECT in opcodes and operand.startswith('(') and operand.endswith(')'):
        v = evaluate.wordExpression(operand[1:-1], context)
        if lo(v) == 0xff:
            context.reportWarning(f'Indirect address located on page boundary: ${v:04x}')
        data = [opcodes[cpu.AddressMode.INDIRECT], lo(v), hi(v)]

    elif cpu.AddressMode.RELATIVE in opcodes: # TODO: give warning about branching across page boundary
        v = evaluate.wordExpression(operand, context)
        # the offset counts from the address after the 2-byte branch instruction
        dist = v - context.symbols['_'] - 2
        if dist < -128 or dist > 127: # branch is out of range (signed byte)
            context.reportError(f'Branch destination out of range [-128..127]: {dist}')
            dist = 0
        data = [opcodes[cpu.AddressMode.RELATIVE], dist&0xff]

    elif (cpu.AddressMode.ZERO_PAGE_X in opcodes or cpu.AddressMode.ABSOLUTE_X in opcodes) and operand.endswith(',x'):
        v = evaluate.wordExpression(operand[:-2], context)
        if cpu.AddressMode.ZERO_PAGE_X in opcodes and hi(v) == 0:
            data = [opcodes[cpu.AddressMode.ZERO_PAGE_X], lo(v)]
        elif cpu.AddressMode.ABSOLUTE_X in opcodes:
            data = [opcodes[cpu.AddressMode.ABSOLUTE_X], lo(v), hi(v)]

    elif (cpu.AddressMode.ZERO_PAGE_Y in opcodes or cpu.AddressMode.ABSOLUTE_Y in opcodes) and operand.endswith(',y'):
        v = evaluate.wordExpression(operand[:-2], context)
        if cpu.AddressMode.ZERO_PAGE_Y in opcodes and hi(v) == 0:
            data = [opcodes[cpu.AddressMode.ZERO_PAGE_Y], lo(v)]
        elif cpu.AddressMode.ABSOLUTE_Y in opcodes:
            data = [opcodes[cpu.AddressMode.ABSOLUTE_Y], lo(v), hi(v)]

    elif (cpu.AddressMode.ZERO_PAGE in opcodes or cpu.AddressMode.ABSOLUTE in opcodes) and operand:
        v = evaluate.wordExpression(operand, context)
        if cpu.AddressMode.ZERO_PAGE in opcodes and hi(v) == 0:
            data = [opcodes[cpu.AddressMode.ZERO_PAGE], lo(v)]
        elif cpu.AddressMode.ABSOLUTE in opcodes:
            data = [opcodes[cpu.AddressMode.ABSOLUTE], lo(v), hi(v)]

    if len(data) <= 0:
        context.reportError(f'Unknown instruction or address mode: {mnemonic} {operand}')

    # store the bytes
    for b in data:
        context.store(b)
