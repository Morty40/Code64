
CPU_IO_DATA_DIRECTION = 0x00
CPU_IO_PORT           = 0x01

def ldax(value):
    a = lo(value)
    x = hi(value)
    if a == x:
        return f"""
        lda #{a}
        tax
        """
    else:
        return f"""
        lda #{a}
        ldx #{x}
        """

def lday(value):
    a = lo(value)
    y = hi(value)
    if a == y:
        return f"""
        lda #{a}
        tay
        """
    else:
        return f"""
        lda #{a}
        ldy #{y}
        """

def ldxy(value):
    x = lo(value)
    y = hi(value)
    return f"""
    ldx #{x}
    ldy #{y}
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
