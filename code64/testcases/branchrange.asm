; branchrange.asm - a branch reaches from -128 to +127 bytes, counted from the
; address after the branch instruction. Expected bytes are given in each comment.

            .org $1000

back:       .bytefill 126, "x: x"   ; filler, unique bytes keep the hex dump readable
            bne back                ; -128, furthest backward branch    -> d0 80
            bne forward             ; +127, furthest forward branch     -> d0 7f
            .bytefill 127, "x: x"
forward:    nop                     ;                                   -> ea
