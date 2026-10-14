#! /usr/bin/env python3
"""The assembler state: symbols, memory, messages and the current line."""

import math
import unittest

import text


class Context:
    """The state of one assemble pass.

    The read pointer stack has a (fileName, lineIndex) for each file
    being assembled. The top is the current line, and an imported file
    or generator is pushed on top of the file that uses it.
    """

    def __init__(self, symbols: dict):
        """Create the state for a pass. The symbols are shared by all passes."""
        self.readPointerStack = []
        
        # math, and ord/chr in the current text encoding, for expressions
        symbols.update(math.__dict__)
        symbols['ord'] = lambda char: text.ord(char, self.encoding)
        symbols['chr'] = lambda value: text.chr(value, self.encoding)
        self.symbols = symbols
        self.labels = set() # labels defined in this pass, to find duplicates
        self.memory = {} # address: byte
        self.warnings = []
        self.errors = []
        self.repeatStack = [] # (iterator, count, readPointer) per open .repeat
        self.zpAddress = 2 # $0 and $1 are reserved
        self.generatorCount = 0 # gives each generator call its own local label scope
        self.path = '' # folder of the main source file, for .import and .binary
        self.encoding = text.ENCODING_SCREEN_UPPER


    def setSymbol(self, name: str, value) -> bool:
        """Set a symbol, which keeps its type, e.g. an int can't become a str.

        Returns False, and keeps the old value, if the type would change.
        """
        if name in self.symbols and type(self.symbols[name]) != type(value):
            oldType, newType = type(self.symbols[name]).__name__, type(value).__name__
            self.reportError(f'Symbol "{name}" cannot change type from {oldType} to {newType}')
            return False
        self.symbols[name] = value
        return True


    def store(self, value: int):
        """Store a byte at the current address, and advance the address."""
        currentLocation = self.symbols['_']

        if currentLocation >= 0 and currentLocation <= 0xffff:

            if currentLocation in self.memory:
                oldValue = self.memory[currentLocation]
                self.reportWarning(f'${currentLocation:04x} is overwritten (${oldValue:02x} to ${value:02x})')

            # store value in memory, and advance to next memory location
            self.memory[currentLocation] = value
            self.symbols['_'] += 1

        else:
            self.reportError(f'Destination memory address out of range: ${currentLocation:x}')


    def storeWord(self, value: int):
        """Store a 16-bit word, low byte first."""
        self.store(value & 0xff)
        self.store((value >> 8) & 0xff)


    def readPointer(self):
        """Return the current (fileName, lineIndex), or None when done."""
        return self.readPointerStack[-1] if self.readPointerStack else None


    def jumpReadPointer(self, readPointer: tuple):
        """Continue from another line. Used by .endr to repeat."""
        if self.readPointerStack:
            self.readPointerStack[-1] = readPointer


    def pushReadPointer(self, readPointer: tuple):
        """Start assembling another file, on top of the current one."""
        self.readPointerStack.append(readPointer)


    def popReadPointer(self):
        """Finish the current file, and return its read pointer."""
        return self.readPointerStack.pop() if self.readPointerStack else None


    def advanceReadPointer(self):
        """Move to the next line, and return the new read pointer."""
        if self.readPointerStack:
            fileName, lineIndex = self.readPointerStack[-1]
            self.readPointerStack[-1] = (fileName, lineIndex + 1)
            return self.readPointerStack[-1]


    def __formattedReadPointer(self):
        """Return the current position as 'file:line ', for messages."""
        rp = self.readPointer()
        return f'{rp[0]}:{rp[1]+1} ' if rp else ''


    def reportWarning(self, text: str):
        """Add a warning, at the current file and line."""
        rp = self.__formattedReadPointer()
        self.warnings.append(f'{rp}warning: {text}')


    def reportError(self, text: str):
        """Add an error, at the current file and line."""
        rp = self.__formattedReadPointer()
        self.errors.append(f'{rp}error: {text}')


    def printMemoryUse(self):
        """Print the memory range used, the global labels, and a page map."""

        if len(self.memory) > 0:
            first = min(self.memory.keys())
            last = max(self.memory.keys())
            total = last-first+1
            use = f"${first:04x}-${last:04x} ({total} bytes)"
        else:
            use = 'None'

        print(f'Memory used: {use}')
        
        # global labels, sorted by address
        lst = sorted(map(lambda label: (self.symbols[label], label), self.labels))
        for value, label in lst:
            if not label.startswith('_'):
                print(f'${value:04x}: {label}')

        # one symbol for each 256-byte page: unused, partly used, or full
        def _pageSymbol(used):
            if used <= 0: return '░'
            elif used > 0 and used < 256: return '▒'
            elif used >= 256: return '▓'

        pages = [0]*256
        for address in self.memory:
            pages[int(address>>8)] += 1
        pageString = "".join(map(_pageSymbol, pages))

        fullPagesUsed = len(list(filter(lambda x: x>=256, pages)))
        partialPagesUsed = len(list(filter(lambda x: x>0 and x<256, pages)))

        print(f'Pages used: {fullPagesUsed} full, {partialPagesUsed} partial')
        for i in range(16): # 16 pages per line
            print(f"${i*16*256:04x}: {pageString[i*16:(i+1)*16]}")


    def printAsmReport(self):
        """Print the warnings and errors from the pass."""
        
        for i in self.warnings + self.errors:
            print(i)


################################################################################

class TestContext(unittest.TestCase):

    def testReadPointerStack(self):
        """The read pointer stack, including the empty stack cases."""
        context = Context({})
        self.assertEqual(context.readPointer(), None)            # empty stack
        self.assertEqual(context.popReadPointer(), None)
        self.assertEqual(context.advanceReadPointer(), None)
        context.jumpReadPointer(('a.asm', 5))                    # no effect on an empty stack
        self.assertEqual(context.readPointer(), None)

        context.pushReadPointer(('a.asm', 0))
        self.assertEqual(context.advanceReadPointer(), ('a.asm', 1))
        context.pushReadPointer(('b.asm', 0))                    # e.g. an .import
        context.jumpReadPointer(('b.asm', 7))                    # e.g. .endr jumping back
        self.assertEqual(context.readPointer(), ('b.asm', 7))
        self.assertEqual(context.popReadPointer(), ('b.asm', 7)) # end of b.asm
        self.assertEqual(context.readPointer(), ('a.asm', 1))    # back in a.asm


    def testReport(self):
        """Warnings and errors are prefixed with the file and line, if any."""
        context = Context({})
        context.reportWarning('no position')
        context.pushReadPointer(('a.asm', 4))                    # line index 4 is line 5
        context.reportWarning('careful')
        context.reportError('failed')
        self.assertEqual(context.warnings, ['warning: no position', 'a.asm:5 warning: careful'])
        self.assertEqual(context.errors, ['a.asm:5 error: failed'])


if __name__ == '__main__':
    unittest.main()
