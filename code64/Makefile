
unittest:
	python3 -m unittest discover -s . -p '*.py'


asmfiles := $(wildcard testcases/*.asm)
prgfiles := $(asmfiles:.asm=.prg)
outfiles := $(asmfiles:.asm=.out)
hexfiles := $(asmfiles:.asm=.hex)
hx2files := $(asmfiles:.asm=.hx2)


%.prg: %.asm
	@./main.py -a $< -o $@ > $(basename $<).out


%.hx2: %.prg
	@hexdump -e \"%04_ax\"\ 16/1\ \"\ %02x\"\ \"\\n\" $< > $(basename $<).hx2


regtest: clean $(asmfiles) $(prgfiles) $(hexfiles) $(hx2files)
	@for f in $(asmfiles:.asm=); do \
        diff -w --unified=0 -s $$f.hex $$f.hx2; \
	done


test: regtest unittest


clean:
	@rm -f $(prgfiles) $(hx2files) $(outfiles)
