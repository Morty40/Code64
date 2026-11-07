# Changelog

Whats new in Code64.

## [0.1.0] - unreleased

The first release.

### Added
- multi-pass 6502 assembler, with automatic zero page addressing and the stable illegal instructions
- Python expressions, f-strings and lambdas in operands and directives
- generators: Python functions that return assembly code
- local labels, zero page variable allocation, `.repeat`, `.for` and `.if` blocks
- `ref("label")`, to only assemble an `.if` block if its label is referenced
- `.optional` blocks, only assembled if one of their global labels is referenced
- PETSCII and screen code text encodings, and your own encoding tables
- `.assert` to check conditions while assembling, e.g. the memory layout
- import of source files, Python files, binary files and SID music
- generic 6502 generators and symbols, always imported
- target imports with `-t c128|c16|c64|plus4|vic20`, such as the C64 hardware (VIC, SID, CIA, KERNAL, BASIC)
- `.prg` output, and a memory map after a successful assembly
- labels file, as Python assignments: `code64 game.asm -l game.py`
- VICE monitor commands file with labels and `.break` breakpoints: `code64 game.asm --vice game.vmc`
- disassembler: `code64 -d <binFile>`, to a file with `-o` or printed, with the names from a labels file with `-l`, and each instruction commented as in a machine code monitor, with its address and bytes
- Python API: `code64.assembleFile`, `code64.disassembleFile` and `code64.Context`
- warnings and errors on stderr, and exit code 1 on errors
- `code64 --version` and `code64 -h`
- requires Python 3.11 or later

[0.1.0]: https://github.com/Morty40/Code64/releases/tag/v0.1.0
