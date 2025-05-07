
BASIC_ROM           = 0xa000

BASIC_ROM_STROUT    = 0xab1e

BASIC_START_ADDRESS = 0x0801

BASIC_TOKEN_REM     = 0x8f
BASIC_TOKEN_SYS     = 0x9e

def basicStart():
    return """
    .org BASIC_START_ADDRESS
    """

def basicRem(lineNumber, text):
    return f"""
    .word _ + 2 + 2 + 1 + {len(text) + 1}
    .word {lineNumber}
    .byte BASIC_TOKEN_REM
    .encoding ENCODING_PETSCII_UPPER
    .text " {text}"
    .byte 0
    """

def basicSys(lineNumber, address):
    sysArg = f"{address}"
    return f"""
    .word _ + 2 + 2 + 1 + {len(sysArg)}
    .word {lineNumber}
    .byte BASIC_TOKEN_SYS
    .encoding ENCODING_PETSCII_UPPER
    .text "{sysArg}"
    .byte 0
    """

def basicEnd():
    return """
    .word 0
    """
