#! /usr/bin/env python3

import builtins
import unittest
import types

#--
import pathlib, sys
sys.path.append(str(pathlib.Path(__file__).parent.absolute()))
#--

from context import Context


def expression(e: str, context: Context):
    value = None
    try:
        value = builtins.eval(e, context.symbols)
    except Exception as exception:
        context.reportError(f'{str(exception).capitalize()}: "{e}"')
    return value


def intExpression(e: str, context: Context) -> int:
    value = expression(e, context)
    if type(value) is float:
        intValue = int(value)
        if value != float(intValue):
            context.reportWarning(f'Truncating float value: {value}')
        value = intValue
    if type(value) is not int:
        context.reportError(f'Expected an int value instead of: "{e}"')
        value = 0
    return value
    
    
def byteExpression(e: str, context: Context) -> int:    
    value = intExpression(e, context)
    if value < -128 or value > 255:
        context.reportError(f'Byte value out of range: {value}')
    return value & 0xff


def wordExpression(e: str, context: Context) -> int:
    value = intExpression(e, context)
    if value < -32768 or value > 65535:
        context.reportError(f'Word value out of range: {value}')
    return value & 0xffff


def lambdaExpression(e: str, context: Context):
    value = expression(f'lambda {e}', context)
    if not isinstance(value, types.FunctionType):
        context.reportError(f'Expected a function instead of: "{e}"')
        value = lambda x: x
    return value


################################################################################

class TestEval(unittest.TestCase):

    def testEvalExpression(self):
        context = Context({})
        value = expression('123', context)
        self.assertEqual(value, 123)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({'abc': 234})
        value = expression('abc', context)
        self.assertEqual(value, 234)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = expression('abc', context)
        self.assertEqual(value, None)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 1)


    def testEvalIntExpression(self):
        context = Context({})
        value = intExpression('12', context)
        self.assertEqual(value, 12)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = intExpression('1.2', context)
        self.assertEqual(value, 1)
        self.assertEqual(len(context.warnings), 1)
        self.assertEqual(len(context.errors), 0)


    def testEvalByteExpression(self):
        context = Context({})
        value = byteExpression('-10', context)
        self.assertEqual(value, 0xf6)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = byteExpression('0x10', context)
        self.assertEqual(value, 0x10)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = byteExpression('0xfff', context)
        self.assertEqual(value, 0xff)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 1)
        

    def testEvalWordExpression(self):
        context = Context({})
        value = wordExpression('-10', context)
        self.assertEqual(value, 0xfff6)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = wordExpression('0x1000', context)
        self.assertEqual(value, 0x1000)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = wordExpression('0xfffff', context)
        self.assertEqual(value, 0xffff)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 1)


    def testEvalLambdaExpression(self):
        context = Context({'k': 1})
        value = lambdaExpression('x: x + k + round(cos(0))', context)
        self.assertEqual(isinstance(value, types.FunctionType), True)
        self.assertEqual(value(1), 3)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)


    def testDivZeroExpression(self):
        context = Context({})
        value = expression('0/0', context)
        self.assertEqual(value, None)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 1)
        

if __name__ == '__main__':
    unittest.main()
