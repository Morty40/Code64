#! /usr/bin/env python3

import math
import os
import unittest

import text


class Context:
    """The state of one assemble pass.

    The read pointer stack has a (fileName, lineIndex) for each file
    being assembled. The top is the current line, and an imported file
    or generator is pushed on top of the file that uses it.
    """

    def __init__(self, symbols: dict):
        self.readPointerStack = []
        
        symbols.update(math.__dict__)
        symbols['ord'] = lambda char: text.ord(char, self.encoding)
        symbols['chr'] = lambda value: text.chr(value, self.encoding)
        self.symbols = symbols
        self.labels = set()
        self.memory = {}
        self.warnings = []
        self.errors = []
        self.repeatStack = []
        self.macroDict = {}
        self.zpAddress = 2 # $0 and $1 are reserved
        self.generatorCount = 0 # gives each generator call its own local label scope
        self.path = ''
        self.encoding = text.ENCODING_SCREEN_UPPER


    def readPointer(self):
        if len(self.readPointerStack) > 0:
            return self.readPointerStack[-1] # return last element
        else:
            return None

        
    def jumpReadPointer(self, readPointer: tuple):
        """Continue from another line. Used by .endr to repeat."""
        if len(self.readPointerStack) > 0:
            self.popReadPointer()
            self.pushReadPointer(readPointer)

        
    def pushReadPointer(self, readPointer: tuple):
        """Start assembling another file, on top of the current one."""
        self.readPointerStack.append(readPointer)
        
        
    def popReadPointer(self):
        if len(self.readPointerStack) > 0:
            return self.readPointerStack.pop() # remove and return last element
        else:
            return None
        
        
    def advanceReadPointer(self):
        """Move to the next line, and return the new read pointer."""
        if len(self.readPointerStack) > 0:
            fileName, lineIndex = self.popReadPointer()
            readPointer = (fileName, lineIndex + 1)        
            self.pushReadPointer(readPointer)
            return readPointer
        else:
            return None
        
    
    def __formattedReadPointer(self):
        rp = self.readPointer()
        if rp is None:
            s = ''
        else:
            fileName, lineIndex = rp
            s = f'{fileName}:{lineIndex+1} '
        return s


    def reportWarning(self, text: str):
        ''' report a warnings '''
        rp = self.__formattedReadPointer()
        self.warnings.append(f'{rp}warning: {text}')


    def reportError(self, text: str):
        ''' report an error '''
        rp = self.__formattedReadPointer()
        self.errors.append(f'{rp}error: {text}')


    def printMemoryUse(self):
        ''' print memory use '''

        if len(self.memory) > 0:
            first = min(self.memory.keys())
            last = max(self.memory.keys())
            total = last-first+1
            use = f"${first:04x}-${last:04x} ({total} bytes)"
        else:
            use = 'None'

        print(f'Memory used: {use}')
        
        lst = sorted(map(lambda label: (self.symbols[label], label), self.labels))
        for value, label in lst:
            if not label.startswith('_'):
                print(f'${value:04x}: {label}')

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
        for i in range(16):
            print(f"${i*16*256:04x}: {pageString[i*16:(i+1)*16]}")


    def printAsmReport(self):
        ''' print warnings and errors from assemble pass '''
        
        for i in self.warnings + self.errors:
            print(i)


################################################################################

class TestAssemble(unittest.TestCase):

    def testTest(self):
        pass


if __name__ == '__main__':
    unittest.main()
