; Testing Python f strings
; https://realpython.com/python-f-strings/

            .org $1000   
            a = "ABC"
	        b = 123
            .encoding ENCODING_SCREEN_UPPER
            .text "{a} {b}"
