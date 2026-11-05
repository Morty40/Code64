#! /usr/bin/env python3
"""Tests of the text encodings."""

import unittest

from ..text import (
    _chr,
    chr,
    ENCODING_PETSCII_MIXED,
    ENCODING_PETSCII_UPPER,
    ENCODING_SCREEN_MIXED,
    ENCODING_SCREEN_UPPER,
    ord,
)


class TestText(unittest.TestCase):
    """The encoding tables, and chr() and ord() in each encoding."""

    def testOrdReversesChr(self):
        """In every encoding, ord gives back the value of every character."""
        for encoding, table in _chr.items():
            for value, char in table.items():
                with self.subTest(encoding=encoding, value=value):
                    self.assertEqual(ord(char, encoding), value)

    def testUnknown(self):
        """A value or character that is not in the encoding gives None."""
        self.assertEqual(chr(255, ENCODING_SCREEN_UPPER), None)
        self.assertEqual(ord('€', ENCODING_PETSCII_MIXED), None)

    def testApostrophe(self):
        """The apostrophe is code 39 in every encoding."""
        for encoding in _chr:
            self.assertEqual(ord("'", encoding), 39)

    def testGraphics(self):
        """Pi and the card suits are in the upper case encodings, where the mixed case ones have letters."""
        for char, screenCode, petscii in [('♠', 65, 97), ('♥', 83, 115), ('♣', 88, 120), ('♦', 90, 122), ('π', 94, 126)]:
            with self.subTest(char=char):
                self.assertEqual(ord(char, ENCODING_SCREEN_UPPER), screenCode)
                self.assertEqual(ord(char, ENCODING_PETSCII_UPPER), petscii)
                self.assertEqual(ord(char, ENCODING_SCREEN_MIXED), None)
                self.assertEqual(ord(char, ENCODING_PETSCII_MIXED), None)

    def testLetters(self):
        """The codes of A and a in each encoding. The upper case encodings have no lower case letters."""
        for encoding, upper, lower in [(ENCODING_SCREEN_UPPER,  1,  None),
                                       (ENCODING_SCREEN_MIXED,  65, 1),
                                       (ENCODING_PETSCII_UPPER, 65, None),
                                       (ENCODING_PETSCII_MIXED, 97, 65)]:
            with self.subTest(encoding=encoding):
                self.assertEqual(ord('A', encoding), upper)
                self.assertEqual(chr(upper, encoding), 'A')
                self.assertEqual(ord('a', encoding), lower)
                if lower is not None:
                    self.assertEqual(chr(lower, encoding), 'a')


if __name__ == '__main__':
    unittest.main()
