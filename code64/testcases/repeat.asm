; repeat.asm - .repeat count blocks. Expected bytes are given in each comment.

            .org $1000

            .repeat 3                       ; three times           -> ee ee ee
            .byte $ee
            .end

            .repeat 0                       ; zero times, so the block is skipped
            .byte $ff
            .end

            .repeat 0                       ; skipped, with a label and a nested block inside
skipped:    .repeat 2
            .byte $ff
            .end
            .end

            .repeat 2                       ; nested blocks         -> 01 02 02 01 02 02
            .byte 1
            .repeat 2
            .byte 2
            .end
            .end

            .repeat 4 // 2                  ; the count is an expression -> 03 03
            .byte 3
            .end

            .repeat 2                       ; a for loop inside a repeat block -> 00 01 00 01
            .for a=0, a<2, a+=1
            .byte a
            .end
            .end

            .repeat 0                       ; skipped, with a for loop inside
            .for a=0, a<2, a+=1
            .byte $ff
            .end
            .end
