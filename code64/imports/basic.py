"""BASIC: the tokens, and generators for a BASIC program that starts the machine code.

basicStart() uses BASIC_START_ADDRESS, which each target defines.
"""

# The tokens of BASIC 2, on all targets
BASIC_TOKEN_END        = 0x80
BASIC_TOKEN_FOR        = 0x81
BASIC_TOKEN_NEXT       = 0x82
BASIC_TOKEN_DATA       = 0x83
BASIC_TOKEN_INPUT_FILE = 0x84 # INPUT#
BASIC_TOKEN_INPUT      = 0x85
BASIC_TOKEN_DIM        = 0x86
BASIC_TOKEN_READ       = 0x87
BASIC_TOKEN_LET        = 0x88
BASIC_TOKEN_GOTO       = 0x89
BASIC_TOKEN_RUN        = 0x8a
BASIC_TOKEN_IF         = 0x8b
BASIC_TOKEN_RESTORE    = 0x8c
BASIC_TOKEN_GOSUB      = 0x8d
BASIC_TOKEN_RETURN     = 0x8e
BASIC_TOKEN_REM        = 0x8f
BASIC_TOKEN_STOP       = 0x90
BASIC_TOKEN_ON         = 0x91
BASIC_TOKEN_WAIT       = 0x92
BASIC_TOKEN_LOAD       = 0x93
BASIC_TOKEN_SAVE       = 0x94
BASIC_TOKEN_VERIFY     = 0x95
BASIC_TOKEN_DEF        = 0x96
BASIC_TOKEN_POKE       = 0x97
BASIC_TOKEN_PRINT_FILE = 0x98 # PRINT#
BASIC_TOKEN_PRINT      = 0x99
BASIC_TOKEN_CONT       = 0x9a
BASIC_TOKEN_LIST       = 0x9b
BASIC_TOKEN_CLR        = 0x9c
BASIC_TOKEN_CMD        = 0x9d
BASIC_TOKEN_SYS        = 0x9e
BASIC_TOKEN_OPEN       = 0x9f
BASIC_TOKEN_CLOSE      = 0xa0
BASIC_TOKEN_GET        = 0xa1
BASIC_TOKEN_NEW        = 0xa2
BASIC_TOKEN_TAB        = 0xa3 # TAB(
BASIC_TOKEN_TO         = 0xa4
BASIC_TOKEN_FN         = 0xa5
BASIC_TOKEN_SPC        = 0xa6 # SPC(
BASIC_TOKEN_THEN       = 0xa7
BASIC_TOKEN_NOT        = 0xa8
BASIC_TOKEN_STEP       = 0xa9
BASIC_TOKEN_PLUS       = 0xaa # +
BASIC_TOKEN_MINUS      = 0xab # -
BASIC_TOKEN_MULTIPLY   = 0xac # *
BASIC_TOKEN_DIVIDE     = 0xad # /
BASIC_TOKEN_POWER      = 0xae # ^
BASIC_TOKEN_AND        = 0xaf
BASIC_TOKEN_OR         = 0xb0
BASIC_TOKEN_GREATER    = 0xb1 # >
BASIC_TOKEN_EQUAL      = 0xb2 # =
BASIC_TOKEN_LESS       = 0xb3 # <
BASIC_TOKEN_SGN        = 0xb4
BASIC_TOKEN_INT        = 0xb5
BASIC_TOKEN_ABS        = 0xb6
BASIC_TOKEN_USR        = 0xb7
BASIC_TOKEN_FRE        = 0xb8
BASIC_TOKEN_POS        = 0xb9
BASIC_TOKEN_SQR        = 0xba
BASIC_TOKEN_RND        = 0xbb
BASIC_TOKEN_LOG        = 0xbc
BASIC_TOKEN_EXP        = 0xbd
BASIC_TOKEN_COS        = 0xbe
BASIC_TOKEN_SIN        = 0xbf
BASIC_TOKEN_TAN        = 0xc0
BASIC_TOKEN_ATN        = 0xc1
BASIC_TOKEN_PEEK       = 0xc2
BASIC_TOKEN_LEN        = 0xc3
BASIC_TOKEN_STR        = 0xc4 # STR$
BASIC_TOKEN_VAL        = 0xc5
BASIC_TOKEN_ASC        = 0xc6
BASIC_TOKEN_CHR        = 0xc7 # CHR$
BASIC_TOKEN_LEFT       = 0xc8 # LEFT$
BASIC_TOKEN_RIGHT      = 0xc9 # RIGHT$
BASIC_TOKEN_MID        = 0xca # MID$
BASIC_TOKEN_GO         = 0xcb

# Only on the C16, Plus/4 and C128, except RLUM on the C128. PET BASIC 4 and the CBM-II use these values
# for other keywords, and are not included.
BASIC_TOKEN_RGR        = 0xcc
BASIC_TOKEN_RCLR       = 0xcd
BASIC_TOKEN_RLUM       = 0xce
BASIC_TOKEN_JOY        = 0xcf
BASIC_TOKEN_RDOT       = 0xd0
BASIC_TOKEN_DEC        = 0xd1
BASIC_TOKEN_HEX        = 0xd2 # HEX$
BASIC_TOKEN_ERR        = 0xd3 # ERR$
BASIC_TOKEN_INSTR      = 0xd4
BASIC_TOKEN_ELSE       = 0xd5
BASIC_TOKEN_RESUME     = 0xd6
BASIC_TOKEN_TRAP       = 0xd7
BASIC_TOKEN_TRON       = 0xd8
BASIC_TOKEN_TROFF      = 0xd9
BASIC_TOKEN_SOUND      = 0xda
BASIC_TOKEN_VOL        = 0xdb
BASIC_TOKEN_AUTO       = 0xdc
BASIC_TOKEN_PUDEF      = 0xdd
BASIC_TOKEN_GRAPHIC    = 0xde
BASIC_TOKEN_PAINT      = 0xdf
BASIC_TOKEN_CHAR       = 0xe0
BASIC_TOKEN_BOX        = 0xe1
BASIC_TOKEN_CIRCLE     = 0xe2
BASIC_TOKEN_GSHAPE     = 0xe3
BASIC_TOKEN_SSHAPE     = 0xe4
BASIC_TOKEN_DRAW       = 0xe5
BASIC_TOKEN_LOCATE     = 0xe6
BASIC_TOKEN_COLOR      = 0xe7
BASIC_TOKEN_SCNCLR     = 0xe8
BASIC_TOKEN_SCALE      = 0xe9
BASIC_TOKEN_HELP       = 0xea
BASIC_TOKEN_DO         = 0xeb
BASIC_TOKEN_LOOP       = 0xec
BASIC_TOKEN_EXIT       = 0xed
BASIC_TOKEN_DIRECTORY  = 0xee
BASIC_TOKEN_DSAVE      = 0xef
BASIC_TOKEN_DLOAD      = 0xf0
BASIC_TOKEN_HEADER     = 0xf1
BASIC_TOKEN_SCRATCH    = 0xf2
BASIC_TOKEN_COLLECT    = 0xf3
BASIC_TOKEN_COPY       = 0xf4
BASIC_TOKEN_RENAME     = 0xf5
BASIC_TOKEN_BACKUP     = 0xf6
BASIC_TOKEN_DELETE     = 0xf7
BASIC_TOKEN_RENUMBER   = 0xf8
BASIC_TOKEN_KEY        = 0xf9
BASIC_TOKEN_MONITOR    = 0xfa
BASIC_TOKEN_USING      = 0xfb
BASIC_TOKEN_UNTIL      = 0xfc
BASIC_TOKEN_WHILE      = 0xfd

# The pi character, on all targets
BASIC_TOKEN_PI         = 0xff

_BASIC_KEYWORDS = ( # the keywords of the BASIC 2 tokens, from $80, tried in this order as BASIC does
    'END', 'FOR', 'NEXT', 'DATA', 'INPUT#', 'INPUT', 'DIM', 'READ', 'LET', 'GOTO', 'RUN', 'IF',
    'RESTORE', 'GOSUB', 'RETURN', 'REM', 'STOP', 'ON', 'WAIT', 'LOAD', 'SAVE', 'VERIFY', 'DEF',
    'POKE', 'PRINT#', 'PRINT', 'CONT', 'LIST', 'CLR', 'CMD', 'SYS', 'OPEN', 'CLOSE', 'GET', 'NEW',
    'TAB(', 'TO', 'FN', 'SPC(', 'THEN', 'NOT', 'STEP', '+', '-', '*', '/', '^', 'AND', 'OR', '>',
    '=', '<', 'SGN', 'INT', 'ABS', 'USR', 'FRE', 'POS', 'SQR', 'RND', 'LOG', 'EXP', 'COS', 'SIN',
    'TAN', 'ATN', 'PEEK', 'LEN', 'STR$', 'VAL', 'ASC', 'CHR$', 'LEFT$', 'RIGHT$', 'MID$', 'GO')

def basicStart():
    """Set the address to the start of the BASIC program."""
    return """
    .org BASIC_START_ADDRESS
    """

def _basicBytes(text):
    """The bytes of a BASIC line, as BASIC stores it: keywords become tokens, and the rest stays as text.

    Keywords are not converted in strings, after REM, or in DATA, up to the next ":".
    """
    text = text.upper() # BASIC keywords are in upper case, and so is its text in the default character set
    data = []
    index = 0
    inString = False # between two " characters
    literal = None   # REM or DATA, while in its text

    while index < len(text):
        # the keyword at this position, trying them in the order BASIC does, so INPUT# comes before INPUT
        keyword = None
        if not inString and not literal:
            keyword = next((k for k in _BASIC_KEYWORDS if text.startswith(k, index)), None)

        if keyword:
            # one token replaces the whole keyword, and the tokens start at $80, in the order of the list
            data.append(0x80 + _BASIC_KEYWORDS.index(keyword))
            index += len(keyword)
            literal = keyword if keyword in ('REM', 'DATA') else None
        else:
            # any other character is stored as it is. A " starts or ends a string
            inString ^= text[index] == '"'
            # a ":" ends a DATA statement, unless it is in a string. REM always lasts to the end of the line
            if literal == 'DATA' and text[index] == ':' and not inString:
                literal = None
            data.append(text[index].encode('ascii')[0]) # not ord(), which here is the current text encoding
            index += 1

    return data

def basicLine(lineNumber, text):
    """A BASIC line, with keywords as tokens, e.g. "POKE 53280,0:SYS 2061"."""
    data = _basicBytes(text) + [0]
    return f"""
    .word _ + 2 + 2 + {len(data)}
    .word {lineNumber}
    .byte {', '.join(map(str, data))}
    """

def basicSys(lineNumber, address):
    """A BASIC line with a SYS to the address, the same as basicLine(lineNumber, f"SYS{address}"). Kept for compatibility."""
    return basicLine(lineNumber, f"SYS{address}")

def basicEnd():
    """The end of the BASIC program."""
    return """
    .word 0
    """
