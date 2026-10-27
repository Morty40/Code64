#! /usr/bin/env python3
"""Assigns the value of a Python expression to a symbol, e.g. x = 1."""

import unittest

from . import evaluate
from . import lexer
from .context import Context


def assemble(tokens: list, context: Context):
    """Assign an expression to a symbol: name = expression.

    Upper case symbols are constants: once they have a value, they can't
    be assigned a different value.
    """
    symbol = tokens[0].string
    expression = lexer.join(tokens[2:])
    value = evaluate.expression(expression, context)
    if value is not None:
        if symbol.isupper():
            if symbol in context.symbols and context.symbols[symbol] != value:
                context.reportError(f'Constant "{symbol}" cannot be changed from {context.symbols[symbol]} to {value}')
                return # the constant keeps its value
        context.setSymbol(symbol, value)


################################################################################

class TestAssignment(unittest.TestCase):

    def _assemble(self, line: str, context: Context):
        assemble(lexer.tokenize(line)[:-1], context)

    def testAssignment(self):
        """The value of a Python expression is assigned to the symbol."""
        context = Context({})
        self._assemble('x = 1 + 2', context)
        self.assertEqual(context.symbols['x'], 3)
        self.assertEqual(context.errors, [])

    def testFailedExpression(self):
        """A symbol is not assigned, if the expression fails."""
        context = Context({})
        self._assemble('x = undefined', context)
        self.assertNotIn('x', context.symbols)
        self.assertEqual(len(context.errors), 1) # the expression's error

    def testConstant(self):
        """An upper case symbol is a constant, which can't be assigned a different value."""
        context = Context({})
        self._assemble('MAX = 1', context)
        self._assemble('MAX = 1', context) # the same value is ok
        self._assemble('MAX = 2', context)
        self.assertEqual(context.symbols['MAX'], 1) # keeps its value
        self.assertEqual(context.errors, ['error: Constant "MAX" cannot be changed from 1 to 2'])


if __name__ == '__main__':
    unittest.main()
