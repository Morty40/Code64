#! /usr/bin/env python3
"""Assigns the value of a Python expression to a symbol, e.g. x = 1."""

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
