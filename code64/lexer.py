#! /usr/bin/env python3

import re
import shlex
import unittest


class Token:
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
    elif word.startswith('%'):
        word = '0b' + word[1:]
    elif word.startswith('"') and word.endswith('"'):
        word = 'f' + word
    return word


def _translateLocalLabels(tokens):    
    newTokens = []
    lastLabel = ''
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
    tokens = []

    if type(text) is str:
        for line in text.splitlines():
            lex = shlex.shlex(line, punctuation_chars="|&<>.=")
            lex.commenters = ';'
            lex.wordchars += '$%'

            for token in lex:    
                tokens.append(Token(_fixPrefix(token), fileName, lex.lineno))
            tokens.append(Token('\n'))

    return tokens


def tokenizeFile(fileName):
    try:
        with open(fileName, 'r') as f:
            text = f.read()
            
    except FileNotFoundError:
        # TODO: also handle ValueError, when quotes are not matched..
        pass

    tokens = tokenize(text, fileName)
    tokens = _translateLocalLabels(tokens)    

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
