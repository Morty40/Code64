#! /usr/bin/env python3
"""The lexer: splits source code into tokens, one line at a time."""

import re
import shlex
import unittest
from typing import Iterator

import cpu


class Token:
    """A word or symbol from the source, e.g. a mnemonic or a number."""

    def __init__(self, string: str, fileName: str='', lineNumber: int=0):
        self.string = string
        self.fileName = fileName
        self.lineNumber = lineNumber

    def __repr__(self):
        s = self.string.replace('\n', '\\n')
        return f'{s} ({self.fileName}:{self.lineNumber})'


def _fixPrefix(word: str) -> str:
    """Convert hex and binary prefixes $ and % to 0x and 0b, and all strings to f-strings."""
    if word.startswith('$'):
        word = '0x' + word[1:]
    elif re.fullmatch(r'%[01]+', word):
        word = '0b' + word[1:]
    elif word.startswith('"') and word.endswith('"'):
        word = 'f' + word
    return word


def translateLocalLabels(tokens: list, lastLabel: str='') -> list:
    """Prefix local labels (starting with _) with the last global label."""
    newTokens = []
    for chunk in chunkSplit(tokens):
        
        if len(chunk) >= 2 and not chunk[0].string.startswith('_') and chunk[1].string == ':':
            lastLabel = chunk[0].string
            
        for token in chunk:
            if len(token.string) > 1 and token.string.startswith('_'):
                token.string = '_' + lastLabel + token.string
            newTokens.append(token)

        newTokens.append(Token('\n'))
        
    return newTokens


def join(tokens: list) -> str:
    """Join tokens into an expression, with a space between adjacent words, e.g. "1 if x else 2"."""
    s = ''
    for t in tokens:
        if re.fullmatch(r'\w\w', s[-1:] + t.string[:1]):
            s += ' '
        s += t.string
    return s


def tokenize(text: str, fileName: str='') -> list:
    """Split source code into tokens, with a newline token after each line.

    Comments are removed, $ and % become 0x and 0b, and strings become
    f-strings, so the tokens form valid Python expressions.
    """
    tokens = []

    if type(text) is str:
        for line in text.splitlines():
            lex = shlex.shlex(line, punctuation_chars="|&<>.=")
            lex.commenters = ';'
            lex.wordchars += '$%'

            # shlex raises ValueError when a line ends inside a quoted string. list() reads the
            # whole line first, so a broken line is replaced before any of its tokens are used.
            try:
                words = list(lex)
            except ValueError: # e.g. no closing quotation
                words = [line] # one token, reported as invalid syntax when assembled

            prev = ['', ''] # previous two tokens, to tell modulo from binary prefix
            for token in words:
                # % is modulo after a number, name or closing bracket (7 % 4), and
                # otherwise a binary prefix (%101), e.g. after a directive or mnemonic
                afterOperand = re.search(r'[\w)\]]$', prev[1]) and prev[0] != '.' and not cpu.isMnemonic(prev[1])
                if not (token.startswith('%') and afterOperand):
                    token = _fixPrefix(token)
                tokens.append(Token(token, fileName, lex.lineno))
                prev = [prev[1], token]
            tokens.append(Token('\n'))

    return tokens


def tokenizeFile(fileName: str) -> list:
    """Tokenize a source file, and translate its local labels."""
    try:
        with open(fileName, 'r') as f:
            text = f.read()
            
    except FileNotFoundError:
        pass

    tokens = tokenize(text, fileName)
    tokens = translateLocalLabels(tokens)

    return tokens


def chunkSplit(tokens: list) -> Iterator[list]:
    """A generator that splits a list of tokens by newlines."""
    indices = [i for i, token in enumerate(tokens) if token.string=='\n']
    for start, end in zip([-1, *indices], [*indices, len(tokens)]):
        yield tokens[start+1:end]


################################################################################

class TestLexer(unittest.TestCase):


    def testFixPrefix(self):
        self.assertEqual(_fixPrefix(''), '')
        self.assertEqual(_fixPrefix('abc'), 'abc')
        self.assertEqual(_fixPrefix('$1234'), '0x1234')
        self.assertEqual(_fixPrefix('%010101'), '0b010101')
        self.assertEqual(_fixPrefix('%'), '%') # modulo operator, not a binary prefix


    def testModulo(self):
        def strings(line):
            return [t.string for t in tokenize(line) if t.string != '\n']
        self.assertEqual(strings('7 % 4'),        ['7', '%', '4'])
        self.assertEqual(strings('7%4'),          ['7%4'])
        self.assertEqual(strings('10 %4'),        ['10', '%4'])
        self.assertEqual(strings('x % 2'),        ['x', '%', '2'])
        self.assertEqual(strings('6 % %11'),      ['6', '%', '0b11'])
        self.assertEqual(strings('%101 % 3'),     ['0b101', '%', '3'])
        self.assertEqual(strings('(%101) % 3'),   ['(', '0b101', ')', '%', '3'])
        self.assertEqual(strings('7 %11'),        ['7', '%11'])
        self.assertEqual(strings('x %10'),        ['x', '%10'])
        self.assertEqual(strings('(5) %10'),      ['(', '5', ')', '%10'])
        # binary prefix after directive, mnemonic and operators
        self.assertEqual(strings('.byte %11'),    ['.', 'byte', '0b11'])
        self.assertEqual(strings('.byte 1, %11'), ['.', 'byte', '1', ',', '0b11'])
        self.assertEqual(strings('lda %11'),      ['lda', '0b11'])
        self.assertEqual(strings('lda #%11'),     ['lda', '#', '0b11'])
        self.assertEqual(strings('x = %11'),      ['x', '=', '0b11'])


    def testTokenRepr(self):
        self.assertEqual(repr(Token('lda', 'a.asm', 3)), 'lda (a.asm:3)')
        self.assertEqual(repr(Token('\n')), '\\n (:0)') # newline is shown escaped


    def testUnclosedQuote(self):
        """A missing end quote doesn't crash, and the other lines are still tokenized."""
        strings = [t.string for t in tokenize('nop\n.text "abc\nrts')]
        self.assertEqual(strings[:2], ['nop', '\n'])
        self.assertEqual(strings[-2:], ['rts', '\n'])


    def testChunkSplit(self):
        tokens = [Token('a'), Token('\n'), Token('b'), Token('c'), Token('\n'), Token('\n'), Token('d')]
        for index, chunk in enumerate(chunkSplit(tokens)):
            if index==0:
                self.assertEqual(len(chunk), 1)
                self.assertEqual(chunk[0].string, 'a')
            if index==1:
                self.assertEqual(len(chunk), 2)
                self.assertEqual(chunk[0].string, 'b')
                self.assertEqual(chunk[1].string, 'c')
            if index==2:
                self.assertEqual(len(chunk), 0)
            if index==3:
                self.assertEqual(len(chunk), 1)
                self.assertEqual(chunk[0].string, 'd')

        
if __name__ == '__main__':
    unittest.main()
