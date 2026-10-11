; modulo.asm - the % character is both the binary prefix (%101) and the
; Python modulo operator (7 % 4). These cases check that the lexer tells
; them apart. Expected bytes are given in each comment.

            .org $1000

; % as modulo
            .byte 7 % 4         ; spaces on both sides             -> 03
            .byte 7%4           ; no spaces, lexed as a single word -> 03
            .byte 10 %4         ; %4 is not binary (digit 4)        -> 02

; modulo mixed with binary numbers
            .byte 6 % %11       ; 6 % 3                             -> 00
            .byte %101 % 3      ; 5 % 3                             -> 02
            .byte (%101) % 3    ; 5 % 3, binary inside parentheses  -> 02

; modulo where the right operand looks like a binary number
x = 7
            .byte 7 %11         ; 7 % 11, after a number            -> 07
            .byte x %10         ; 7 % 10, after a name              -> 07
            .byte (5) %10       ; 5 % 10, after a parenthesis       -> 05

; guards: % right after a directive or mnemonic is a binary prefix
            .byte %11           ; binary 3                          -> 03
            lda %11             ; lda zeropage $03                  -> a5 03
