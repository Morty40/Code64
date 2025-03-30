            .org $1000
            @setb(dest1, 1)
            @setb(dest2, [value])
            rts
value:      .byte 2
dest1:      .byte 0
dest2:      .byte 0
