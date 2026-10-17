; python.asm - blocks of Python code, from .python to .end. Expected bytes are given in each comment.

            .org $1000

            .python                         ; the code at the same indentation as .python
            f = lambda x: x+2
            .end
            .byte f(1)                      ; -> 03

            .python
                def double(x):                      # indented like the assembly around it
                    return x * 2
                values = [1, 2]; total = sum(values) # ; separates Python statements, it is not a comment
                text = "$%"                          # $ and % are not changed into 0x and 0b
            .end

            .byte double(21)                ; -> 2a
            .byte total, len(text)          ; -> 03 02
            .byte 7 % 4                     ; after the block, lines are assembled as before -> 03

            .python
                def nops(n):
                    return "nop\n" * n
            .end
            @nops(2)                        ; a generator defined in a block -> ea ea

            .if 0                           ; a block in skipped lines is skipped too
            .python
                this is not valid Python, but it is skipped
            .end
            .end
