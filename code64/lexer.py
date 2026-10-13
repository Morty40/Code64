#! /usr/bin/env python3

import re
import shlex
import unittest

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


def _fixPrefix(word):
    """ converts hex and binary prefixes $ and %, to 0x and 0b, and all strings to f-strings """
    if word.startswith('$'):
        word = '0x' + word[1:]
    elif re.fullmatch(r'%[01]+', word):
        word = '0b' + word[1:]
    elif word.startswith('"') and word.endswith('"'):
        word = 'f' + word
    return word


def translateLocalLabels(tokens, lastLabel=''):
    """ prefixes local labels (starting with _) with the last global label """
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


def tokenize(text: str, fileName=''):
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

            prev = ['', ''] # previous two tokens, to tell modulo from binary prefix
            for token in lex:
                afterOperand = re.search(r'[\w)\]]$', prev[1]) and prev[0] != '.' and not cpu.isMnemonic(prev[1])
                if not (token.startswith('%') and afterOperand):
                    token = _fixPrefix(token)
                tokens.append(Token(token, fileName, lex.lineno))
                prev = [prev[1], token]
            tokens.append(Token('\n'))

    return tokens


def tokenizeFile(fileName):
    """Tokenize a source file, and translate its local labels."""
    try:
        with open(fileName, 'r') as f:
            text = f.read()
            
    except FileNotFoundError:
        # TODO: also handle ValueError, when quotes are not matched..
        pass

    tokens = tokenize(text, fileName)
    tokens = translateLocalLabels(tokens)

    #for t in tokens:
    #    print(t.string, end=' ')
        
    return tokens


def chunkSplit(tokens):
    """ a generator that splits a list of tokens by newlines """
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
