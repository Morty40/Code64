# BASIC

BASIC_START_ADDRESS = 0x0801
BASIC_TOKEN_SYS     = 0x9e

def basicSys(address):
    sysArg = f" {address}"
    return f"""
    .org BASIC_START_ADDRESS
    .word _ + 5 + {len(sysArg)} + 1
    .word 1
    .byte BASIC_TOKEN_SYS
    .encoding ENCODING_PETSCII_UPPER
    .text "{sysArg}"
    .byte 0
    .word 0
    """
