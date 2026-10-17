; if.asm - .if condition blocks, with .else and .end. Expected bytes are given in each comment.

            .org $1000
a = 7

            .if a>5                         ; true                  -> 01
            .byte 1
            .end

            .if a<5                         ; false, so the lines are skipped
            .byte $ee
            .end

            .if a>5                         ; true, with else       -> 02
            .byte 2
            .else
            .byte $ee
            .end

            .if a<5                         ; false, with else      -> 03
            .byte $ee
            .else
            .byte 3
            .end

            .if a>5                         ; nested                -> 04
            .if a<5
            .byte $ee
            .else
            .byte 4
            .end
            .end

            .if a<5                         ; skipped, with a label, a nested if and a loop inside -> 05
inner:      .if a>5
            .byte $ee
            .else
            .byte $ee
            .end
            .repeat 2
            .byte $ee
            .end
            .else
            .byte 5
            .end

            .if a>5                         ; the same label in both branches -> 06
both:       .byte 6
            .else
both:       .byte $ee
            .end

            .if a>5 and not a>10            ; Python keywords in the condition -> 07
            .byte 7
            .end

            .for i=0, i<4, i+=1             ; inside a loop         -> 00 02
            .if i % 2 == 0
            .byte i
            .end
            .end
