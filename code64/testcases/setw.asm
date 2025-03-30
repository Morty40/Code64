            .org $1000
            @setw(dest1, 1)
            @setw(dest2, [value])
            rts
value:      .word 2
dest1:      .word 0
dest2:      .word 0
