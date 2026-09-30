# CP/M Version (80un.com)

A native CP/M program written in PL/M-80 that runs on real vintage hardware or emulators.

## Getting 80un.com

Download `80un.com` directly from this repository, or build from source (see below).

Transfer to your CP/M system via:
- XMODEM/YMODEM from a terminal program
- Write to a disk image and mount it
- Your emulator's file import feature

## Usage on CP/M

Extract an LBR archive:
```
A>80UN MYLIB.LBR

80UN - CP/M Archive Unpacker v2.3

Extracting:
  README.TXT OK
  PROGRAM.COM OK
  SOURCE.ASM OK

3 file(s) extracted
```

Extract an ARC archive:
```
A>80UN SOFTWARE.ARC

80UN - CP/M Archive Unpacker v2.3

Extracting:
  INSTALL.DOC OK
  PROG.COM OK
  CONFIG.DAT OK

3 file(s) extracted
```

Decompress a squeezed file:
```
A>80UN MANUAL.TQT

80UN - CP/M Archive Unpacker v2.3

Extracting:
Creating: MANUAL.TXT OK

1 file(s) extracted
```

Decompress a crunched file:
```
A>80UN SOURCE.AZM

80UN - CP/M Archive Unpacker v2.3

Extracting:
Creating: SOURCE.ASM OK

1 file(s) extracted
```

## Notes

- Files extract to current drive/user area
- Existing files are overwritten without warning
- Original filenames are restored from compressed file headers
- Nested compression is handled (e.g., crunched files inside LBR)

## Member names on CP/M

A member's stored name is whatever the archiver wrote: an ARC name made on
MS-DOS or Unix, lower case, too long, or a crunched file's name with a `/` in
it (`zex-sage.dzc` holds `ZEX/SAGE.DOC`). The BDOS will put any bytes into a
directory entry, but a file with such a name cannot be named at the CCP, and
cpmemu refuses to make it. `80un.com` makes a name CP/M takes, the same way for
every format (`src/plm/names.plm`):

- bit 7 of each byte, an attribute, is dropped, and so are blanks at either end;
- lower case letters become upper case, as the CCP makes every name;
- the type is what follows the last `.`, the name what comes before it;
- a character CP/M does not take in a name becomes `-`: a control character or
  blank, DEL, and `< > . , ; : = ? * [ ] _ | ( ) / \ ^ % "` - the CP/M
  manual's reserved characters, the CP/M 2.2 CCP's delimiters, and what the
  CP/M 3 parser and cpmemu refuse;
- the name is cut to 8 characters and the type to 3, and an empty name becomes
  `UNNAMED`;
- a name already made in this run gets `-1`, `-2`, ... on its end, cut to fit,
  so that two members never land on one file (for as many names as 80un
  keeps: 256, or as many as fit below the BDOS, about 100 in a 64K CP/M 2.2);
- the archive's own name counts as one made already, when the archive is on the
  drive the members are written to, so that no member is written over the
  archive while it is being read: `SELF.ARC` holding `SELF.ARC` writes it as
  `SELF-1.ARC`.

A crunched or CrLZH file's name ends at a `[`, where a note begins, as UNCR24
and `src/un80` end it. When the name made differs from the one stored, 80un
shows both:

```
Creating: ZEX/SAGE.DOC -> ZEX-SAGE.DOC [Crunch V1] OK
  CCP/M.COM -> CCP-M.COM OK
  ccp_m.com -> CCP-M-1.COM OK
```

This is `src/un80`'s rule for a host filesystem (`un80.cpm.safe_filename`:
replace, never split, and number the duplicates) made for CP/M, with one
difference that CP/M forces: the stand-in is `-`, not `_`. The CP/M 2.2 CCP
takes `_` as a delimiter, the same as `=`, so `TYPE ZEX_SAGE.DOC` would type a
file called `ZEX`, and `ERA ZEX_SAGE.DOC` erase one. So `src/un80` writes
`ZEX_SAGE.DOC` and `CCP_M.COM` where `80un.com` writes `ZEX-SAGE.DOC` and
`CCP-M.COM`, and an ARC member named `MY_FILE.TXT` keeps its name on a host but
becomes `MY-FILE.TXT` on CP/M.

## Building from Source

Requires the [uplm80](https://github.com/avwohl/uplm80) toolchain:

```bash
make            # Build 80un.com
make test       # Test with sample archives
make clean      # Remove build artifacts
```

## Developer Notes: EOL Handling

When testing the PL/M version with [cpmemu](https://github.com/avwohl/cpmemu), be aware that the emulator performs automatic line-ending conversion for text files. Files with extensions like `.MAC`, `.ASM`, `.TXT` are detected as text and have CR+LF converted to LF when written to the Unix filesystem.

To get raw binary output for testing, create a config file with `default_mode = binary` and `eol_convert = false`. See `CLAUDE.md` for details.

The Python and PL/M decompressors produce **identical output** when:
- Python: raw output (no `--text` flag)
- PL/M: via cpmemu with binary mode enabled

## Source Files

PL/M-80 source is in `src/plm/`:

| File | Purpose |
|------|---------|
| `startup.plm` | Entry point |
| `common.plm` | BDOS interface, memory ops |
| `io.plm` | Buffered I/O, bit readers |
| `names.plm` | CP/M names for archive members |
| `squeeze.plm` | Huffman decompressor |
| `crunch.plm` | LZW decompressor |
| `lzh.plm` | LZSS decompressor |
| `arc.plm` | ARC archive extractor |
| `lbr.plm` | LBR archive extractor |
| `bas.plm` | MBASIC detokenizer |
| `main.plm` | 80UN main program |
| `basmain.plm` | 80UNBAS main program |
| `heap.asm` | Heap allocation bridge |

## Requirements

- CP/M 2.2 or compatible (MP/M, ZCPR, etc.)
- About 58KB of TPA (Transient Program Area) for 80UN.COM: its buffers and
  room for one name must end 128 bytes below the BDOS entry at 0006H, so that
  must be at about E800H or above (the exact figure depends on the build).
  With more room it keeps up to 256 names (2.75KB), about 100 in a 64K CP/M
  2.2, whose BDOS entry is at EC06H. With less, 80UN says `Not enough memory`
  and stops.
- ~18KB TPA for 80UNBAS.COM
- Z80 processor

## Memory-Constrained Systems

80UN.COM requires approximately 58KB of TPA, most of it for ARC method 9 (squashed) with its 8192-entry LZW dictionary. For systems with limited memory, 80UNBAS.COM is provided as a separate utility for MBASIC detokenization, requiring only ~18KB TPA.

## 80UNBAS.COM - MBASIC Detokenizer

A companion utility that converts tokenized MBASIC files to ASCII text.

### Usage

```
A>80UNBAS PROGRAM.BAS

80UNBAS - MBASIC Detokenizer v2.3

Creating: PROGRAM.TXT OK
```

### Supported Formats

| Magic | Type | Description |
|-------|------|-------------|
| `0xFF` | Standard | Normal tokenized MBASIC file |
| `0xFE` | Protected | Protected (encrypted) MBASIC file |

Note: "Protected" files are only lightly scrambled; 80UNBAS fully decrypts and detokenizes them.

### Building

80UNBAS is built alongside 80UN:

```bash
make           # Builds both 80un.com and 80unbas.com
make test-bas  # Test BASIC detokenizer
```
