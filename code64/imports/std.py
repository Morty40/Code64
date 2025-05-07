
CHAR_ROM = 0xd000

def setb(address, value):
	asm = ""
	if type(value) is int:
		asm += f"""
				lda #{value}
				sta {address}
				"""
	elif type(value) is list and len(value)==1 and type(value[0]) is int:
		asm += f"""
				lda {value[0]}
				sta {address}
				"""
	return asm


def setw(address, value):
	asm = ""
	if type(value) is int:
		asm += f"""
				lda #lo({value})
				sta {address+0}
				lda #hi({value})
				sta {address+1}
				"""
	elif type(value) is list and len(value)==1 and type(value[0]) is int:
		asm += f"""
				lda {value[0]+0}
				sta {address+0}
				lda {value[0]+1}
				sta {address+1}
				"""
	return asm
