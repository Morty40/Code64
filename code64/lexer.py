#! /usr/bin/env python3
"""The lexer: splits source code into tokens, one line at a time."""

import errno
import os
import re
import textwrap
import unittest
from dataclasses import dataclass
from typing import Iterator

from . import cpu


# the tokens of a line, in the order they are tried, with the longest operators first
_TOKEN = re.compile(r'''
    ;.*                                         # comment
  | [A-Za-z]*"(?:\\.|[^"\\])*"                  # strings, with any prefix
  | [A-Za-z]*'(?:\\.|[^'\\])*'
  | \$\w*                                       # hex number
  | %[01]+\b                                    # binary number, or modulo and a number, see tokenize()
  | \d[\w.]*(?:(?<=[eE])[-+]\d+)?               # number, with an optional signed exponent
  | \w+                                         # name
  | <<|>>|<=|>=|==|!=|\*\*|//|:=                 # operators of two characters
  | \S                                          # anything else, including an unmatched quote
''', re.VERBOSE)


_KEYWORDS = ('if', 'else', 'or', 'not', 'in', 'is') # Python keywords that an operand follows


@dataclass
class Token:
    """A word or symbol from the source, e.g. a mnemonic or a number."""
    string: str
    fileName: str = ''
    lineNumber: int = 0

    def __repr__(self):
        """The token with its file and line, for debugging."""
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
    for lineTokens in splitByNewline(tokens):

        if len(lineTokens) >= 2 and not lineTokens[0].string.startswith('_') and lineTokens[1].string == ':':
            lastLabel = lineTokens[0].string

        for token in lineTokens:
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


def splitByComma(tokens: list) -> list:
    """Split tokens at the commas that are not inside brackets, e.g. i<len([1, 2])."""
    parts, depth = [[]], 0
    for token in tokens:
        if token.string in ('(', '[', '{'):
            depth += 1
        elif token.string in (')', ']', '}'):
            depth -= 1
        if token.string == ',' and depth == 0:
            parts.append([])
        else:
            parts[-1].append(token)
    return parts


def tokenize(text: str, fileName: str='') -> list:
    """Split source code into tokens, with a newline token after each line.

    Comments are removed, $ and % become 0x and 0b, and strings become
    f-strings, so the tokens form valid Python expressions. A block of
    Python code, from .python to .end, becomes one .python line with the code as a
    string, followed by empty lines, so the line numbers stay the same.
    """
    tokens = []

    if type(text) is str:
        pythonBlock = None # the lines of a .python block, while they are collected
        for line in text.splitlines():
            if pythonBlock is not None:
                if re.fullmatch(r'\s*\.end\s*(;.*)?', line): # the end of the .python block
                    code = textwrap.dedent('\n'.join(pythonBlock))
                    tokens.append(Token(repr(code), fileName))
                    tokens += [Token('\n') for _ in range(len(pythonBlock) + 2)] # .python, the code, and .end
                    pythonBlock = None
                else:
                    pythonBlock.append(line)
                continue

            words = [word for word in _TOKEN.findall(line) if not word.startswith(';')]
            if '"' in words or "'" in words: # no closing quotation
                words = [line] # one token, reported as invalid syntax when assembled

            if words[:2] == ['.', 'python'] and len(words) > 2: # Python code is only allowed in a block
                words = [line] # one token, reported as invalid syntax when assembled
            if words == ['.', 'python']: # a block of Python code follows, up to .end
                tokens += [Token('.', fileName), Token('python', fileName)]
                pythonBlock = []
                continue

            prev = ['', ''] # previous two tokens, to tell modulo from binary prefix
            for token in words:
                # % is modulo after a number, name or closing bracket (7 % 4), and
                # otherwise a binary prefix (%101), e.g. after a directive or mnemonic
                afterOperand = (re.search(r'[\w)\]}"\']$', prev[1]) and prev[1] not in _KEYWORDS
                                and prev[0] != '.' and not cpu.isMnemonic(prev[1]))
                if not (token.startswith('%') and afterOperand):
                    token = _fixPrefix(token)
                tokens.append(Token(token, fileName))
                prev = [prev[1], token]
            tokens.append(Token('\n'))
        if pythonBlock is not None: # no .end, so the .python line is reported as an invalid directive
            tokens += [Token('\n') for _ in range(len(pythonBlock) + 1)]

    return tokens


def tokenizeFile(fileName: str) -> list:
    """Tokenize a source file, and translate its local labels. Raises OSError if the file can't be read."""
    try:
        with open(fileName, 'r', encoding='utf-8') as f:
            text = f.read()
    except UnicodeDecodeError as exception:
        line = exception.object.count(b'\n', 0, exception.start) + 1
        raise OSError(errno.EILSEQ, f'Not valid UTF-8 on line {line}', fileName)

    tokens = tokenize(text, fileName)
    tokens = translateLocalLabels(tokens)

    return tokens


def splitByNewline(tokens: list) -> Iterator[list]:
    """A generator that splits a list of tokens by newlines."""
    indices = [i for i, token in enumerate(tokens) if token.string=='\n']
    for start, end in zip([-1, *indices], [*indices, len(tokens)]):
        yield tokens[start+1:end]


################################################################################

class TestLexer(unittest.TestCase):
    """Tests of tokenizing source code."""


    def testFixPrefix(self):
        """The number prefixes $ and % become Python's 0x and 0b."""
        self.assertEqual(_fixPrefix(''), '')
        self.assertEqual(_fixPrefix('abc'), 'abc')
        self.assertEqual(_fixPrefix('$1234'), '0x1234')
        self.assertEqual(_fixPrefix('%010101'), '0b010101')
        self.assertEqual(_fixPrefix('%'), '%') # modulo operator, not a binary prefix


    def testModulo(self):
        """% is modulo after a number, name or closing bracket, and otherwise a binary prefix."""
        def strings(line):
            """The tokens of a line as strings, without the newline."""
            return [t.string for t in tokenize(line) if t.string != '\n']
        self.assertEqual(strings('7 % 4'),        ['7', '%', '4'])
        self.assertEqual(strings('7%4'),          ['7', '%', '4'])
        self.assertEqual(strings('10 %4'),        ['10', '%', '4'])
        self.assertEqual(strings('x % 2'),        ['x', '%', '2'])
        self.assertEqual(strings('6 % %11'),      ['6', '%', '0b11'])
        self.assertEqual(strings('%101 % 3'),     ['0b101', '%', '3'])
        self.assertEqual(strings('(%101) % 3'),   ['(', '0b101', ')', '%', '3'])
        self.assertEqual(strings('7 %11'),        ['7', '%11'])
        self.assertEqual(strings('x %10'),        ['x', '%10'])
        self.assertEqual(strings('(5) %10'),      ['(', '5', ')', '%10'])
        self.assertEqual(strings('"%d" %10'),     ['f"%d"', '%10'])
        self.assertEqual(strings('True %10'),     ['True', '%10'])
        # binary prefix after directive, mnemonic and operators
        self.assertEqual(strings('.byte %11'),    ['.', 'byte', '0b11'])
        self.assertEqual(strings('1 if %1 else %10'), ['1', 'if', '0b1', 'else', '0b10'])
        self.assertEqual(strings('not %1'),       ['not', '0b1'])
        self.assertEqual(strings('.byte 1, %11'), ['.', 'byte', '1', ',', '0b11'])
        self.assertEqual(strings('lda %11'),      ['lda', '0b11'])
        self.assertEqual(strings('lda #%11'),     ['lda', '#', '0b11'])
        self.assertEqual(strings('x = %11'),      ['x', '=', '0b11'])


    def testTokenRepr(self):
        """A token is shown with its file and line."""
        self.assertEqual(repr(Token('lda', 'a.asm', 3)), 'lda (a.asm:3)')
        self.assertEqual(repr(Token('\n')), '\\n (:0)') # newline is shown escaped


    def testUnclosedQuote(self):
        """A missing end quote doesn't crash, and the other lines are still tokenized."""
        strings = [t.string for t in tokenize('nop\n.text "abc\nrts')]
        self.assertEqual(strings[:2], ['nop', '\n'])
        self.assertEqual(strings[-2:], ['rts', '\n'])


    def testSplitByComma(self):
        """Tokens are split at the commas that are not inside brackets."""
        parts = splitByComma(tokenize('a=0, a<len([1, 2]), {"x": (3, 4)}')[:-1])
        self.assertEqual([join(part) for part in parts], ['a=0', 'a<len([1,2])', '{f"x":(3,4)}'])


    def testScanner(self):
        """Each token is the longest match, whichever characters are next to it."""
        for line, expected in [
            ('t-$10',         ['t', '-', '0x10']),
            ('-$10',          ['-', '0x10']),
            ('2*%11',         ['2', '*', '0b11']),
            ('$20/$10',       ['0x20', '/', '0x10']),
            ('~$10',          ['~', '0x10']),
            ('2**$4',         ['2', '**', '0x4']),
            ('16//$4',        ['16', '//', '0x4']),
            ('7%$10',         ['7', '%', '0x10']),
            ('%101%2',        ['0b101', '%', '2']),
            ('a<<2',          ['a', '<<', '2']),
            ('a<=2',          ['a', '<=', '2']),
            ('a==-1',         ['a', '==', '-', '1']),
            ('a!=b',          ['a', '!=', 'b']),
            ('x=.5',          ['x', '=', '.', '5']),
            ('a<.5',          ['a', '<', '.', '5']),
            ('1.5',           ['1.5']),
            ('1e3',           ['1e3']),
            ('1.5e-3',        ['1.5e-3']),
            ('1e-_x',         ['1e', '-', '__x']),
            ('a-1',           ['a', '-', '1']),
            ('.byte 1 ; c',   ['.', 'byte', '1']),
            ('l:nop',         ['l', ':', 'nop']),
            ('"a;b" ; c',     ['f"a;b"']),
            ('"a\\"b"',       ['f"a\\"b"']),
            ("'a;b'",         ["'a;b'"]),
            ('r"a"',          ['r"a"']),
            ('f"a"',          ['f"a"']),
            ('x = "abc',      ['x = "abc']),   # no closing quote: one token, reported as invalid syntax
            ("x = 'abc",      ["x = 'abc"]),
        ]:
            with self.subTest(line=line):
                self.assertEqual([t.string for t in translateLocalLabels(tokenize(line))[:-1] if t.string != '\n'], expected)


    def testPythonBlock(self):
        """A .python block becomes one .python line with the code as a string, keeping the line count."""
        strings = [t.string for t in tokenize('nop\n.python\n    def f(x):\n        return x; # a;b\n.end\nrts')]
        self.assertEqual(strings[:5], ['nop', '\n', '.', 'python', repr('def f(x):\n    return x; # a;b')])
        self.assertEqual(strings[5:], ['\n'] * 4 + ['rts', '\n'])


    def testTokenizeMissingFile(self):
        """A missing file raises FileNotFoundError, for the caller to handle."""
        self.assertRaises(FileNotFoundError, tokenizeFile, os.path.join(os.path.dirname(__file__), 'missing.asm'))

    def testSplitByNewline(self):
        """The tokens of each line, without the newlines. An empty line has no tokens."""
        tokens = [Token('a'), Token('\n'), Token('b'), Token('c'), Token('\n'), Token('\n'), Token('d')]
        lines = [[token.string for token in lineTokens] for lineTokens in splitByNewline(tokens)]
        self.assertEqual(lines, [['a'], ['b', 'c'], [], ['d']])


if __name__ == '__main__':
    unittest.main()
