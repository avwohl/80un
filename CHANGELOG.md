# Changelog

All notable changes to 80un, the unpacker for CP/M compression and packing
formats, are documented here.

## [0.2.4] - 2026-08-20

Version 0.2.3 was bumped in `pyproject.toml` but never uploaded to PyPI and
never tagged, so this release carries its changes as well. In the Python
package the only source change in the whole span is the four-line LBR directory
check described under Fixed; everything else is the CP/M side, the build and
the repository.

### Added

`80UNBAS.COM`, a standalone MBASIC detokenizer for CP/M, built from the new
`src/plm/basmain.plm` plus `startup.plm`, `common.plm`, `io.plm` and `bas.plm`.
It reads a file whose first byte is `0FFH` (tokenized) or `0FEH` (protected),
writes the ASCII text to the same name with the extension changed to `.TXT`,
and prints `Not a tokenized BASIC file` for anything else. The reason it exists
is memory: it allocates only an input and an output buffer of 4096 bytes each
off `heap$base`, so the 9216-byte program plus 8264 bytes of heap fits in about
18K of TPA, where `80UN.COM` has to reserve the whole ARC method 9 working set
(a 16384-byte LZW prefix table, an 8192-byte suffix table, a 4096-byte ring
buffer and a 4096-byte work buffer) and does not fit on a small system. The
README now puts `80UN.COM` at about 62KB of TPA, up from the 40KB it used to
claim.

`make` builds both programs, and `make test-bas` runs `80UNBAS.COM` under
cpmemu using the new `tests/80unbas.cfg`, which sets `default_mode = binary`
and `eol_convert = false` so the emulator does not rewrite CR LF pairs in a
tokenized input file on the way in. `tests/PALLOPS.BAS` is the test input.

`.github/workflows/publish.yml` builds an sdist and a wheel and uploads them to
PyPI through trusted publishing when a GitHub release is published, or on
manual dispatch. Repository infrastructure; it is not part of the installed
package.

### Changed

The README no longer marks CrLZH experimental. The format row drops
"(Experimental)" and the troubleshooting entry that told people to fall back to
`UCRLZH20.COM` under an emulator now says to check the file for corruption
instead. No code in `src/un80/crlzh.py` changed in this release, so this is a
reclassification of a decoder that was already there, not a fix to it. The
coverage table likewise marks LBR and MBASIC complete and adds check marks to
the Crunch and ARC rows, which still list missing samples; no test changed to
back any of it. A copy of the decompressed `CRLZH20.COM` was committed under
`tests/samples/crlzh/`, but no test refers to it; `test_crlzh.py` is unchanged
and still drives `CRLZH20.CYM`, `qto-zb12.aym` and `TEST.MYC`.

The README gained a Related Projects section listing the sister repositories.
The See Also section of external CP/M links was already there and is unchanged.
Documentation only.

### Fixed

`read_directory` in `src/un80/lbr.py` no longer rejects an LBR whose first
directory entry carries a name. The check was `if not dir_entry.is_directory`,
and that property demands a blank name, a blank extension and an index of 0.
Some LBR writers put a non-blank name in that entry, and every archive from one
of them failed with `ValueError: First entry is not a directory entry` before a
single member was read — extraction and plain `-l` listing alike, on an archive
that was not damaged in any way. The entry is now accepted when its status byte
is `0x00` (active), which is what the CP/M implementation in `src/plm/lbr.plm`
has always tested, and the directory length is validated separately as 1 to 32
sectors. The message raised when the first entry really is invalid changed
from `First entry is not a directory entry` to `First entry is not a valid
directory entry`, so anything matching on that string needs updating. Reported
as issue #1.

That length bound is new behavior in its own right and worth knowing about
before upgrading: an LBR whose directory is larger than 32 sectors — more than
128 entries, since a 128-byte sector holds four 32-byte entries — is now
refused with `ValueError: Invalid directory size`, where 0.2.2 read as many
directory sectors as the file contained. The ceiling matches the PL/M version,
which imposes it because it reads the directory into a 4K work buffer.

### Removed

`80UN.COM` no longer detokenizes MBASIC files; use `80UNBAS.COM` for that.
`bas.plm` is out of the `80un.com` link line in the `Makefile`, and `main.plm`
has lost the `mbasic$magic`/`mbasic$prot` constants, the `0FFH`/`0FEH` magic
test, the `.BAS` extension test and the whole detokenize branch. `80UN
PROGRAM.BAS` on CP/M no longer writes `PROGRAM.TXT`; with no format matched it
falls into the closing "try as LBR anyway" branch of `main`, which finds a
first byte that is not `0` and prints `Invalid LBR file`. The banner is now
`80UN - CP/M Archive Unpacker v2.3` and the format line printed for a bare
invocation is `Supports: LBR, ARC, .?Q?, .?Z?, .?Y?`. The binary shrank from
28885 to 21336 bytes.

The Python `80un` command is not affected by that removal. `src/un80/bas.py`
and the `bas` branch of `src/un80/cli.py` are untouched, so `80un file.bas`
still detokenizes both the standard and the protected variant.

The generated `80un.mac` (11,430 lines of assembler output) is no longer
committed, and `*.com` is now in `.gitignore`. The three `.com` files already
tracked stay tracked, so a new sample binary needs `git add -f`. The pre-split
`src/plm/80un.plm` moved to `src/plm/archive/80un.plm`; it is the single-file
program from before the sources were factored apart, kept for reference and not
built by anything. `WIP.md` (a resolved CrLZH investigation) and `todo.txt`
(early build notes) were deleted.

---

This file starts at 0.2.4. Earlier history is in the git log.
