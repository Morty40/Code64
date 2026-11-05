#! /usr/bin/env python3
"""The assembler: assembles source files into memory, in multiple passes."""

import os
import glob

from . import assignment
from . import cpu
from . import directives
from . import generators
from . import instructions
from . import lexer
from . import text
from .context import Context
from .cpu import lo, hi

# max passes until all symbols should have been resolved
MAX_PASSES = 42

DEFAULT_ORIGIN = 0x1000 # the address when there is no .org

TARGETS = ('c128', 'c16', 'c64', 'plus4', 'vic20') # the folders in imports/target


def assembleFile(inFile: str, outFile: str = None, target: str = None) -> Context:
    """Assemble inFile, and save it to outFile, if given and there are no errors. Returns the
    context of the last pass: memory, symbols, messages and errors. The target is one of TARGETS,
    whose imports are added to the generic ones.
    Raises OSError if inFile can't be read, or outFile can't be written, and ValueError for an unknown target.

    Passes are repeated until the output stops changing (max. MAX_PASSES), so
    labels can be used before they are defined.
    """
    if target is not None and target not in TARGETS:
        raise ValueError(f'Unknown target: {target}')

    path = os.path.dirname(inFile)

    symbols = {'lo': lo, 'hi': hi,
        'ENCODING_SCREEN_UPPER': text.ENCODING_SCREEN_UPPER,
        'ENCODING_SCREEN_MIXED': text.ENCODING_SCREEN_MIXED,
        'ENCODING_PETSCII_UPPER': text.ENCODING_PETSCII_UPPER,
        'ENCODING_PETSCII_MIXED': text.ENCODING_PETSCII_MIXED,
        'SOURCE_FOLDER': path} # for generators that read files

    root = os.path.abspath(os.path.dirname(__file__))
    imports = sorted(glob.glob(os.path.join(root, 'imports/*.py')))
    if target:
        imports += sorted(glob.glob(os.path.join(root, 'imports/target', target, '*.py')))

    for fileName in imports:
        with open(fileName) as f:
            exec(compile(f.read(), fileName, 'exec'), symbols) # the file name shows in tracebacks

    lastMemory = {}
    lastReferences = set()
    chunks = {} # the tokenized files and generated code, by name: tokenized once, for all passes

    for _ in range(MAX_PASSES):
        # a new context each pass, but symbols are kept from the last pass
        symbols['_'] = DEFAULT_ORIGIN
        context = Context(symbols)
        context.path = path
        context.lastReferences = lastReferences
        context.pushReadPointer( (inFile, 0) )

        # assemble line by line, from the file on top of the read pointer stack
        while True:
            readPointer = context.readPointer()
            if readPointer is None: break

            fileName, lineIndex = readPointer

            if not fileName in chunks:
                chunks[fileName] = list(lexer.splitByNewline(lexer.tokenizeFile(fileName)))

            allChunks = chunks[fileName]

            if lineIndex < len(allChunks):

                lineTokens = allChunks[lineIndex]
                advance = True

                # label
                if len(lineTokens) >= 2 and lineTokens[1].string == ':':
                    label = lineTokens[0].string
                    if label in context.labels:
                        context.reportError(f'Label was already defined: "{label}"')
                    context.setSymbol(label, context.symbols['_'])
                    context.labels.add(label)
                    lineTokens = lineTokens[2:]

                if len(lineTokens) >= 1 and cpu.isMnemonic(lineTokens[0].string):
                    instructions.assemble(lineTokens, context)

                elif len(lineTokens) >= 3 and lineTokens[1].string == '=':
                    assignment.assemble(lineTokens, context)

                elif len(lineTokens) >= 2 and lineTokens[0].string == '.':
                    advance = directives.assemble(lineTokens, context, chunks)

                elif len(lineTokens) >= 2 and lineTokens[0].string == '@':
                    advance = generators.assemble(lineTokens, context, chunks)

                elif len(lineTokens) > 0:
                    context.reportError(f'Invalid syntax')

                if advance:
                    context.advanceReadPointer()

            else:
                context.popReadPointer() # end of file, back to the importing file

        directives.reportOpenBlocks(context)

        # done when there are no errors, and the output and references are unchanged
        if len(context.errors) == 0 and context.memory == lastMemory and context.references == lastReferences:
            break

        # prepare for next pass
        lastMemory = dict(context.memory)
        lastReferences = context.references

    # save the .prg: the load address, the lowest address used or DEFAULT_ORIGIN, then memory from there to the end
    if outFile and not context.errors:
        memory = context.memory
        start = min(memory, default=DEFAULT_ORIGIN)
        data = [memory.get(address, 0) for address in range(start, max(memory) + 1)] if memory else []
        with open(outFile, 'wb') as f:
            f.write(bytes([lo(start), hi(start)] + data))
    return context
