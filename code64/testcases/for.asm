; for.asm - .for initial, condition, step loops. Expected bytes are given in each comment.

            .org $1000

            .for a=0, a<4, a+=1             ; four times            -> 00 01 02 03
            .byte a
            .end

            .for a=10, a<10, a+=1           ; false at the start, so the loop is skipped
            .byte $ee
            .end

            .for a=0, a<0, a+=1             ; skipped, with a label and a nested loop inside
skipped:    .for b=0, b<2, b+=1
            .byte $ee
            .end
            .end

            .for a=3, a>0, a-=1             ; counting down         -> 03 02 01
            .byte a
            .end

            .for row=0, row<2, row+=1       ; nested loops          -> 00 01 02 10 11 12
            .for column=0, column<3, column+=1
            .byte row*16 + column
            .end
            .end

            .for a=1, a<100, a*=2           ; any Python statement as the step -> 01 02 04 08 10 20 40
            .byte a
            .end

            .for i=0, i<len([5, 6]), i+=1   ; commas inside brackets -> 00 01
            .byte i
            .end
