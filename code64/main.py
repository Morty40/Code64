#! /usr/bin/env python3
"""Code64 command line: code64 <asmFile> -o <outFile>, or code64 -d <prgFile> -o <asmFile>"""

import argparse
import sys

from . import __version__
from . import assemble
from . import disassemble
from .context import Context


def printMemoryUse(context: Context):
    """Print the memory range used, and a page map."""

    if len(context.memory) > 0:
        first = min(context.memory.keys())
        last = max(context.memory.keys())
        total = last-first+1
        use = f"${first:04x}-${last:04x} ({total} bytes)"
    else:
        use = 'None'

    print(f'Memory used: {use}')

    # one symbol for each 256-byte page: unused, partly used, or full
    def _pageSymbol(used):
        """The symbol for a page with this number of bytes used."""
        if used <= 0: return '.'
        elif used > 0 and used < 256: return '+'
        elif used >= 256: return '#'

    pages = [0]*256
    for address in context.memory:
        pages[int(address>>8)] += 1
    pageString = "".join(map(_pageSymbol, pages))

    fullPagesUsed = len(list(filter(lambda x: x>=256, pages)))
    partialPagesUsed = len(list(filter(lambda x: x>0 and x<256, pages)))

    print(f'Pages used: {fullPagesUsed} full, {partialPagesUsed} partial')
    for i in range(16): # 16 pages per line
        print(f"${i*16*256:04x}: {pageString[i*16:(i+1)*16]}")


def sortedLabels(context: Context) -> list:
    """Return the (address, label) of each label, sorted by address. Local labels are named global_local."""
    return sorted((context.symbols[label], label[1:] if label.startswith('_') else label) for label in context.labels)


def pythonLabels(context: Context) -> str:
    """Return the labels as Python assignments, sorted by address."""
    return ''.join(f'{label} = 0x{address:04x}\n' for address, label in sortedLabels(context))


def viceMonitorCommands(context: Context) -> str:
    """Return the VICE monitor commands: the labels, sorted by address, then the breakpoints."""
    commands = [f'al C:{address:04x} .{label}' for address, label in sortedLabels(context)]
    commands += [f'break C:{address:04x}' + (f' if {condition}' if condition else '') for address, condition in context.breakpoints]
    return ''.join(f'{command}\n' for command in commands)


def main():
    """Assemble or disassemble the file given on the command line. Exits with 1 on errors, 2 on incorrect arguments, and 130 after Ctrl-C."""
    parser = argparse.ArgumentParser(prog='code64', description=f'Code64 v{__version__}: a 6502/Python hybrid cross assembler for Commodore computers.')
    parser.add_argument('file', help='the source file to assemble, or with -d the .prg or binary file to disassemble')
    parser.add_argument('-d', '--disassemble', dest='disassemble', action='store_true', help='disassemble the file instead of assembling it')
    parser.add_argument('-o', '--output', dest='outFile', help='the .prg file to write, or the source file when disassembling (default: print it)')
    parser.add_argument('-t', '--target', dest='target', choices=assemble.TARGETS,
                        help='the target machine, whose symbols and generators are imported (default: none)')
    parser.add_argument('-l', '--labels', dest='labelsFile', help='the labels file, as Python assignments: written when assembling, read when disassembling')
    parser.add_argument('--vice', dest='viceFile', help='the VICE monitor commands file to write: labels and breakpoints')
    parser.add_argument('--version', action='version', version=f'Code64 v{__version__} (c) Morten Perriard 2021-2026')
    arguments = parser.parse_args()
    if arguments.disassemble and arguments.viceFile:
        parser.error('--vice can only be used when assembling')
    if arguments.disassemble and arguments.target:
        parser.error('--target can only be used when assembling')
    try:
        if arguments.disassemble:
            source = disassemble.disassembleFile(arguments.file, arguments.outFile, arguments.labelsFile)
            if not arguments.outFile:
                print(source, end='')
            anyErrors = False
        else:
            context = assemble.assembleFile(arguments.file, arguments.outFile, arguments.target)
            for message in context.printed:
                print(message)
            sys.stdout.flush() # keep the order when stdout and stderr go to the same pipe or file
            for message in context.warnings + context.errors:
                print(message, file=sys.stderr)
            anyErrors = len(context.errors) > 0
            if not anyErrors:
                printMemoryUse(context)
                if arguments.labelsFile:
                    with open(arguments.labelsFile, 'w') as f:
                        f.write(pythonLabels(context))
                if arguments.viceFile:
                    with open(arguments.viceFile, 'w') as f:
                        f.write(viceMonitorCommands(context))
    except OSError as exception:
        print(f'error: {exception.strerror}: "{exception.filename}"', file=sys.stderr)
        anyErrors = True
    except KeyboardInterrupt:
        print('error: Interrupted', file=sys.stderr)
        sys.exit(130) # the usual exit code after Ctrl-C
    sys.exit(1 if anyErrors else 0)


if __name__ == '__main__':
   main()
