            .import "generatorlocal.py"
            .org $1000
aa:         @delay(3)
bb:         @delay(5)
            @delay(7)       ; second call in the same scope
            rts
