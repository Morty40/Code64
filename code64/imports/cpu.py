
CPU_IO_DATA_DIRECTION = 0x00
CPU_IO_PORT           = 0x01

def ldax(value):
    return f"""
    lda #lo({value})
    ldx #hi({value})
    """

def lday(value):
    return f"""
    lda #lo({value})
    ldy #hi({value})
    """

def ldxy(value):
    return f"""
    ldx #lo({value})
    ldy #hi({value})
    """

def stax(address):
    return f"""
    sta {address}
    stx {address+1}
    """

def stay(address):
    return f"""
    sta {address}
    sty {address+1}
    """

def stxy(address):
    return f"""
    stx {address}
    sty {address+1}
    """
