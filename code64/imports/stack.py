
STACK_ADDRESS = 0x0100

def pushRegisters():
    return """
    pha
	txa
	pha
	tya
	pha
    """

def pullRegisters():
    return """
	pla
	tay
	pla
	tax
	pla
    """

def storeRegisters(restore):
    return f"""
    sta {restore}+1
    stx {restore}+3
    sty {restore}+5
    """
    
def restoreRegisters():
    return """
    lda #0
    ldx #0
    ldy #0
    """
