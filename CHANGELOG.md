# Changelog

All notable changes to 80un, the unpacker for CP/M compression and packing
formats, are documented here.

## [0.3.2] - 2026-09-23

### Changed

`80un.com` and `80unbas.com` rebuilt against uplm80 0.3.5. That release fixes
a long list of code-generation defects, so the emitted code differs from the
binaries built with 0.3.4 even though the behaviour does not: both builds
produce byte-identical output on all 21 members of the sample corpus and on
the BASIC detokeniser. Reproducing the committed binaries now needs uplm80
`>=0.3.5`.

None of the defects 0.3.5 fixes was reachable from this source — the survey
in that release found no site in `src/plm` exposed to any of them — which is
why the output is unchanged. The rebuild is to keep `make` reproducing what
is committed.

`src/plm/bas.plm` writes MBASIC's integer-divide token as `'\'` again rather
than `5CH`. The numeric form was a workaround from when uplm80's lexer took a
backslash inside a character literal for an escape introducer and refused the
file; PL/M-80 has no escape character, uplox 3.3.1 corrected the grammar, and
uplm80 0.3.5 requires it. `80unbas.com` is byte-identical across the change,
which is what proves `'\'` lexes to 5CH.

## [0.3.1] - 2026-09-19

### Changed

`80un.com` and `80unbas.com` are built by plain `make` again, with the released
toolchain. uplm80 0.3.4 fixes the last of the three code-generation defects
recorded under 0.3.0 below, so the pin to uplm80 `01cfcc6` is gone. Reproducing
the committed binaries needs uplm80 `>=0.3.4`; with that, `make` reproduces
`80un.com` byte for byte.

The committed `80un.com` is byte-exact against the original CP/M UNCR24.COM on
all 15 single-file crunch and squeeze samples, and reproduces the Python decoders
on 107 of the 108 sample-corpus members - the exception being the Crunch V1 file,
which the decoder refuses by design. `80unbas.com` produces output identical to
the binary committed before.

The last defect was worth recording, because the shape is a trap for any code
generator: uplm80 parked an array's base address in `DE` and then generated the
index expression, and an index carrying a 16-bit constant emits `ld de,nn`, so
the base was destroyed and the closing `add hl,de` added the constant twice.
`prnt(i + lzh$t) = i` stored to `(i + 629) * 2 + 629` instead of
`prnt + (i + 629) * 2`. An index of `i` or `i + 1` was unaffected, because
neither needs `DE`, which is why only `init$tree` and `update$tree` in
`src/plm/lzh.plm` broke and only CrLZH decoding was wrong.

`make clean` no longer deletes `80unbas.com`. Both `.COM` files are committed
deliverables, and removing one but not the other left a stale binary looking
current.

### Known issues

Crunch V1 (siglevel below 0x20) is still not implemented, and input is refused
with a clear error. UNCR24 handles V1 in a separate routine with a different
algorithm.

## [0.3.0] - 2026-09-19

### Fixed

RLE90 emitted one byte too many for every run. `90 N` means the previous byte
occurs N times in TOTAL, so only N-1 further copies belong in the output - the
previous byte was already written when the previous byte was read as a literal.
The decoders emitted N, which added one spurious byte per run, in practice from
around output byte 72 of every affected file. `90 00`, which is a literal `90`,
also wrongly set the previous-byte register; `90 00` must leave the previous-byte
register alone. Both rules come straight from GEL Uncruncher v2.4 (`DEC A` at
04AF, and the 04BF path that does not touch the previous-byte register).

A `90` with no count byte after it is now dropped rather than written out as a
literal. UNCR24 only arms its escape flag and then runs out of input, so UNCR24
writes nothing; running UNCR24 on `A 90` under cpmemu produces just `A`.

One difference from UNCR24 is deliberate. UNCR24 decrements the count into the
Z80 `B` register and then runs a do-while loop, so `90 01` underflows to 256
copies: running UNCR24 on `A 90 01` produces 257 bytes. No encoder emits `90 01`
- a run of one is simply a literal - and reproducing the underflow would turn
three bytes into 257, so `90 01` emits nothing here, which is what the count
actually means.

The same off-by-one was present in every RLE90 decoder that the build uses, and
all of the decoders are fixed: `src/un80/crunch.py`, `src/un80/arc.py`,
`src/un80/squeeze.py`, and on the CP/M side `rle$decode$byte` in `src/plm/io.plm`
(shared by crunch, squeeze and ARC) and `arc$decomp$rle` in `src/plm/arc.plm`.
The two copies in `src/plm/archive/80un.plm` are left alone; that file predates
the split into modules and nothing builds that file. Two independent oracles
confirm the correction rather than just the samples: the CRC-16 that each ARC
member header carries over its uncompressed contents goes from 8 of 48 members
valid to 46 of 48, and both squeeze samples now reproduce the 16-bit checksum
stored in their headers exactly.

ARC methods 8 and 9 lost the stream at the first code after a CLEAR. ARC packs
LZW codes eight at a time, so one block is `code_size` bytes, and the encoder
pads the block out before starting again at 9 bits; a decoder that reads straight
on takes the padding for data. Both implementations are fixed,
`decompress_lzw_arc8` and the method 9 decoder in `src/un80/arc.py` and
`arc$decomp$lzw8` and `arc$decomp$squashed` in `src/plm/arc.plm`. Discarding the
padding takes the ARC corpus from 46 of 48 members CRC-valid to all 48, which
retires the two method 8 failures that this file previously recorded as a known
issue. `CPKERM.DOC`, the larger of the two, now reproduces its stored CRC of
0xA4B4 under cpmemu as well as in Python. Only CLEAR needs the
alignment. A code-size increase is already aligned, because the increase happens
after exactly `2**code_size - 256` codes, and that count is a multiple of 8 for
every code size from 9 up - measured across the corpus, a growth-point alignment
would discard nothing at all 98 growth points.

Crunch froze its LZW dictionary once the dictionary held 4096 entries. CRUNCH
does not freeze - once the table is full CRUNCH switches to a second mode that
*replaces* entries which have never been referenced, choosing the victim by
walking the same open-addressed hash table the compressor used. A decoder that
freezes instead desynchronises from the compressor at the moment the table fills,
so everything after that point is corrupt. `src/un80/crunch.py` now implements
the replacement mode: the 5003-slot hash table, the `(prefix, suffix)` hash and
its probe stride, the "referenced" flag bit, and the one extra append that
happens between the table filling and replacement starting. `src/plm/crunch.plm`
implements the same mode for CP/M, with the tables declared in
`src/plm/common.plm` and given storage in `src/plm/main.plm`. Every routine
carries the UNCR24 address the routine was taken from.

The crunch decoder's "entry does not exist" guard never fired. The caller marks a
code as referenced before decoding the code, and the referenced bit and the
"slot empty" marker are different bits of the same flag byte, so a code naming an
entry that was never created read as a single-byte entry: the decoder emitted a
NUL and carried on instead of stopping on a corrupt or truncated stream. 61 of
the 62 bytes that `tests/samples/crunch/zex-sage.dzc` used to produce were that
artefact.

Crunch V1 input is refused rather than decoded wrongly. V1 carries a siglevel
below 0x20 and uses a different algorithm, which UNCR24 handles in a separate
routine. Running the V2 decoder over V1 input produced a short run of rubbish and
reported success, so `un80 zex-sage.dzc` wrote a 62-byte file and said nothing
was wrong. `uncrunch` now raises `CrunchError`.

The embedded filename in a crunch header may carry a free-form note, as in
`MOUSE.MAC[04/01/87]` or `COMMON.LIB[ V2.4 INCLUDE FILE]`. The note was being
treated as part of the filename, and because these notes usually contain a date
with slashes in the date, extracting an archive whose members carry a note failed
outright with `No such file or directory`. `parse_header` now ends the filename
at the `[`, as UNCR24 does, reports the remainder as `CrunchHeader.note`, and
stops scanning for the terminator past 128 bytes rather than following a corrupt
header as far as the file goes.

Names taken from an archive went into a filesystem path unchecked. A member could
therefore name a path outside the output directory. `un80.cpm.safe_filename` now
replaces every character that is special to a host filesystem, and LBR, ARC and
the single-file decompress path all run member names through `safe_filename`. The
characters are replaced rather than split on, because `/` is an ordinary filename
character under CP/M: `mouse.lbr` holds a member called `CCP/M.COM`, which now
extracts as `CCP_M.COM` instead of losing everything before the slash.

Replacing characters creates collisions of its own, and three further hazards
around member names are handled with it. Two members whose names differ only in a
replaced character now map to one name, so extraction de-duplicates and the name
reported back to the caller is the name actually written; before, the second
member silently overwrote the first while both members were reported as
extracted. An embedded name is arbitrary bytes and can be far longer than a CP/M
name, so a name is capped at 255 bytes with its extension kept - an over-long
name used to abort the whole extraction part-way with a bare `OSError`. A name
that Windows resolves to a device, such as `NUL` or `PRN.TXT`, is prefixed, and a
trailing dot or space is dropped, because Windows drops a trailing dot itself and
would merge two members onto one name.

One member that cannot be decompressed no longer costs the caller the rest of the
archive. `extract_lbr` keeps such a member as stored, under the name in the LBR
directory, the way `extract_arc` already did.

`make` builds both programs again. MBASIC's integer-divide token is a backslash,
and `src/plm/bas.plm` wrote the backslash as a character literal, which the
current uplm80 lexer takes for an escape introducer and rejects, so `make`
stopped with a lexical error after building `80un.com`. The literal is written as
`5CH` instead, and `80unbas.com` produces byte-identical output.

### Added

`tests/samples/lbr/mouse.lbr`, the archive from issue #2, as a regression case.
The archive is a good one: `MOUSE.MZC` fills the dictionary early, `COCONUT.MZE`
fills the dictionary only 181 bytes before the end, and the archive carries
`UNCR24.COM` itself, so the expected output is produced by the original CP/M
uncruncher running under cpmemu rather than recorded from this decoder. All 14
crunched members, plus `COMMON.LZB` which recycles 7177 entries, now decode byte
for byte as UNCR24 decodes them.

Checksum-based tests for ARC and squeeze that validate against the CRC-16 and the
header checksum the formats already carry. Every member of every ARC sample is
checked, with no exclusions.

Unit tests for RLE90's exact semantics and for filename sanitisation, including
the cases sanitising creates: Windows device names, trailing dots, over-long
names, and two members that sanitise to one name. A crafted LBR holding a Crunch
V1 member checks that one unusable member does not stop the extraction.

A reset-code test that a broken reset fails. The previous test passed with the
whole reset handler replaced by `continue`, so the entire reset path was
untested; the replacement checks that dictionary numbering really restarts.

### Known issues

Crunch V1 (siglevel below 0x20) is not implemented. Input is now refused with a
clear error instead of decoded wrongly. UNCR24 handles V1 in a separate routine
with a different algorithm.

The released uplm80 0.3.2 miscompiles this program, so the `80UN.COM` that `make`
produces is wrong even though the PL/M sources are right. Three separate
code-generation defects are involved, all of them in the compiler:

* a BYTE `>` comparison used as a value leaves the left operand in the
  accumulator on the false path instead of zero, so a false `>` reads as true;
* `_gen_byte_binary` parks one operand of an `AND` or `OR` in register `B` while
  generating the other operand, and the other operand can overwrite `B`;
* uplm80 `bdb0f8a` "Implement register tracking phases 3-5" breaks CrLZH.

The first two defects became reachable at uplm80 `273c83a`, which correctly made
PL/M-80's `AND` and `OR` bitwise rather than short-circuit; both defects are
latent in every earlier commit as well, and standalone PL/M programs demonstrate
both under the older compiler too. The result under 0.3.2 is a binary that
decodes all 15 single-file crunch and squeeze samples byte-exactly against
UNCR24, yet truncates every compressed ARC or LBR member to one 128-byte record,
rejects `mouse.lbr` outright as invalid, and decodes CrLZH wrongly. Building the
same sources with uplm80 `01cfcc6` gives a binary that is byte-exact on all 15
single-file samples and reproduces the Python decoders on 107 of the 108 corpus
members; the remaining member is the Crunch V1 file above.

The committed `80un.com` and `80unbas.com` are therefore built with uplm80
`01cfcc6` rather than with the released 0.3.2, and plain `make` will not
reproduce either binary until uplm80 is fixed. `80un.com` is the 107 of 108
binary described above. `80unbas.com` produces output identical to the binary
committed before this change.

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
