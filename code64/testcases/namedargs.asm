            .import "namedargs.py"
            .org $1000
            @jump(address=_sub)
            @jump(address =_sub)
            @jump(address= _sub)
            @jump(address = _sub)
_sub:
            rts
