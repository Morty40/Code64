            .import "keywords.py"
            .org $1000
flag = 1

            ; directives
            .byte 1 if flag else 2
            .byte 3 if not flag else 4
            .byte flag and 5, flag or 6
            .byte 7 if 3 in [1, 2, 3] else 8
            .word $1234 if flag is not None else 0

            ; instructions
            lda #9 if flag else 10

            ; assignments
squares = [x * x for x in range(4)]
            .byte squares[3]

            ; generators
            @fill(11, 2) if flag else ""
