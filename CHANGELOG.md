# Changelog

Whats new in Code64.

## [0.1.0] - unreleased

The first release.

### Added
- multi-pass 6502 assembler, with automatic zero page addressing and the illegal instructions (`-i none | stable | all`)
- Python expressions, f-strings and lambdas in operands and directives
- generators: Python functions that return assembly code
- local labels, zero page variable allocation, `.repeat`, `.for` and `.if` blocks
- PETSCII and screen code text encodings
- `.assert` to check conditions while assembling, e.g. the memory layout
- import of source files, Python files, binary files and SID music
- built-in symbols for the C64 hardware (VIC, SID, CIA, KERNAL, BASIC)
- `.prg` output, and a memory map after a successful assembly
- labels file, as Python assignments: `code64 game.asm -l game.py`
- VICE monitor commands file with labels and `.break` breakpoints: `code64 game.asm --vice game.vmc`
- disassembler: `code64 -d <binFile>`, to a file with `-o` or printed, with the names from a labels file with `-l`
- Python API: `code64.assembleFile`, `code64.disassembleFile` and `code64.Context`
- warnings and errors on stderr, and exit code 1 on errors
- `code64 --version` and `code64 -h`
- requires Python 3.9 or later

[0.1.0]: https://github.com/Morty40/Code64/releases/tag/v0.1.0
