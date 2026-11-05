#! /usr/bin/env python3
"""Tests of the directives."""

import unittest

from .. import lexer
from ..context import Context
from ..directives import assemble, byte, bytefill, _matches, org, printValues


class TestDirectives(unittest.TestCase):
    """Tests of the directive arguments."""

    def testMatches(self):
        """Arguments are checked against the parameters, and their type annotations."""
        self.assertTrue(_matches(org, [0x1000]))
        self.assertFalse(_matches(org, []))                  # missing argument
        self.assertFalse(_matches(org, [1, 2]))              # too many arguments
        self.assertFalse(_matches(org, ['a']))               # wrong type
        self.assertFalse(_matches(org, [True]))              # a bool is not an int
        self.assertTrue(_matches(bytefill, [3]))             # optional argument
        self.assertTrue(_matches(bytefill, [3, 'x: x']))
        self.assertTrue(_matches(byte, []))                  # any number of any type
        self.assertTrue(_matches(byte, [1, 'a', 2.5]))
        self.assertFalse(_matches(printValues, []))          # at least one


    def testBitsWithInt(self):
        """.bits needs a string with the bit pattern."""
        context = Context({})
        assemble(lexer.tokenize('.bits 3')[:-1], context)
        self.assertEqual(context.errors, ['error: Invalid directive: .bits 3'])


if __name__ == '__main__':
    unittest.main()
