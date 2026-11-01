"""The stack address, and generators to save and restore the registers."""

STACK_ADDRESS = 0x0100

def pushRegisters():
    """Push A, X and Y on the stack."""
    return """
    pha
	txa
	pha
	tya
	pha
    """

def pullRegisters():
    """Pull Y, X and A from the stack, the reverse of pushRegisters."""
    return """
	pla
	tay
	pla
	tax
	pla
    """

def storeRegisters(restore):
    """Store A, X and Y in the operands of restoreRegisters, which starts at the label restore."""
    return f"""
    sta {restore}+1
    stx {restore}+3
    sty {restore}+5
    """
    
def restoreRegisters():
    """Load A, X and Y with the values written by storeRegisters."""
    return """
    lda #0
    ldx #0
    ldy #0
    """
