# Command Line Usage

```
usage: 80un [-h] [--version] [-o DIR] [-l] [-t] [-f FORMAT] [-n] file

Unpacker for CP/M compression and packing formats

positional arguments:
  file                  File to extract or decompress

options:
  -h, --help            Show this help message and exit
  --version             Show program's version number and exit
  -o, --output DIR      Output directory for extracted files
  -l, --list            List contents without extracting
  -t, --text            Convert text files (strip ^Z, CR/LF to LF)
  -f, --format FORMAT   Force file format: lbr, arc, squeeze, crunch, crlzh
  -n, --no-clobber      Do not overwrite existing files
```

## Examples

**List contents of an LBR archive:**
```bash
$ 80un myarchive.lbr -l
Filename             Size  Sectors
------------------------------------
README.TZT            512        4
PROGRAM.CZM          8192       64
DATA.DZT             1024        8

3 file(s)
```

**List contents of an ARC archive:**
```bash
$ 80un myarchive.arc -l
Filename           Original  Compressed  Method
------------------------------------------------------
README.TXT             1024         512  crunched LZW
PROGRAM.COM           16384        8192  crunched LZW
DATA.DAT               2048        1024  squeezed

3 file(s)
```

**Extract an archive:**
```bash
$ 80un myarchive.lbr
  README.TXT
  PROGRAM.COM
  DATA.DAT

Extracted 3 file(s)
```

**Extract to a specific directory:**
```bash
$ 80un myarchive.lbr -o output/
  README.TXT
  PROGRAM.COM
  DATA.DAT

Extracted 3 file(s)
```

**Extract and convert text files to Unix format:**
```bash
$ 80un myarchive.lbr -t -o output/
```

This strips the ^Z (Ctrl-Z) end-of-file padding and converts CR/LF line endings to Unix LF.

**Decompress a single crunched file:**
```bash
$ 80un document.tzt
  document.txt (2048 bytes)
```

The original filename is recovered from the compressed file header.

**Force a specific format:**
```bash
$ 80un unknown.dat -f crunch
```

**Extract without overwriting existing files:**
```bash
$ 80un myarchive.lbr -o output/ -n
  README.TXT
  PROGRAM.COM (skipped, already exists)
  DATA.DAT

3 file(s): 2 extracted, 1 skipped
```

The `-n` / `--no-clobber` option is useful when extracting multiple archives to the same directory, or when you want to preserve files you've already modified.
