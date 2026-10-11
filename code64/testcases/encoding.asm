; encoding.asm - every pass must start with the default encoding
; (ENCODING_SCREEN_UPPER), no matter which .encoding the previous pass
; ended with. This file ends with a non-default encoding, so if the
; encoding leaks into the next pass, the first lines change.
; ord() and chr() in expressions must follow the current encoding too.
; Expected bytes are given in each comment.

            .org $1000

; default encoding, screen code upper
            .text "A"           ; screen code for A                  -> 01
            .byte ord("A")      ; screen code for A                  -> 01
            .byte int(chr(1) == "A")  ; screen code 1 is A           -> 01

            .encoding ENCODING_PETSCII_UPPER
            .text "A"           ; petscii upper for A                -> 41
            .byte ord("A")      ; petscii upper for A                -> 41
            .byte int(chr(65) == "A") ; petscii 65 is A              -> 01

; guard: switching back to screen code
            .encoding ENCODING_SCREEN_UPPER
            .text "A"           ; screen code upper                  -> 01

; end with a non-default encoding, this is what would leak into the next pass
            .encoding ENCODING_PETSCII_MIXED
            .text "A"           ; petscii mixed, uppercase A         -> 61
