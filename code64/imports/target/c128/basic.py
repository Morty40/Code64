"""BASIC: the start address of a program, on the C128, and ROM addresses."""

BASIC_START_ADDRESS = 0x1c01

BASIC_ROM           = 0x4000

BASIC_ROM_STROUT    = 0x55e2

del BASIC_TOKEN_RLUM # $ce is a prefix for two byte tokens on the C128
