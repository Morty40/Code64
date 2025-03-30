
def jump(address):
    asm = f"""
            jmp {address}
    """
    return asm
