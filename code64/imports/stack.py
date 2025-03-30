
STACK_ADDRESS = 0x0100

def pushAXY():
    return """
    pha
	txa
	pha
	tya
	pha
    """

def pullYXA():
    return """
	pla
	tay
	pla
	tax
	pla
    """
