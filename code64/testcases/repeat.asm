            .org $1000

            .repeat 'a', 2
            .repeat 'b', 4
            .byte (a*16)+b
            .endr
            .endr
