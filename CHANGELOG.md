# Changelog

All notable changes to 80un, the unpacker for CP/M compression and packing
formats, are documented here.

## 0.3.3 — unreleased

### Fixed

The PL/M sources `80un.com` and `80unbas.com` are built from no longer rely on
uplm80 widening a shifted BYTE. In PL/M-80 the result of `SHL` and `SHR` has
the type of the value shifted, so `SHL(b, 8)` of a BYTE is a BYTE, and 0;
Intel's PL/M-80 V3.1 compiles it that way. uplm80 before 0.4.3 widened the
BYTE to an ADDRESS first, and 80un was written against that: `lo + shl(b, 8)`
built the 16-bit values in `read16` and `readword`, the ARC and LBR header
sizes, the crunch header checksum, the squeeze node count and the BASIC link
pointers, line numbers and constants; `shl(i, 7)`, `shl(i, 2)` and
`shl(low(node), 2)` of a BYTE addressed the sector and Huffman-node buffers;
`shl(1, n)` set the LZW dictionary limits in `lzw$add$entry` and the ARC
decoders; and CrLZH shifted each input byte into its 16-bit bit buffer
(`lzh$get$bit`) and a `d$code` entry into the upper bits of a V1 match
position (`decode$pos$v1`). Built by a compiler that follows the language,
80un extracted one member of `tests/test.arc` where the 0.4.1 build extracts
13, and from the 23 archives and compressed files under `tests/` it wrote 39
files, 4 of them correct, where the 0.4.1 build writes 136.

The 29 sites where a BYTE is shifted and the bits shifted out of it are wanted
now read `SHL(DOUBLE(x), n)`, which is correct PL/M-80 under any compiler. The
ten BYTE shifts left alone either go into a BYTE (the crunch code-width
threshold, `lzh$get$byte`, the crunch used-code bit mask, `read$bit$sq`) or
cannot pass eight bits (a hex digit `SHR(b, 4)`, the used-code test,
`SHL(dir$sectors, 2)` of at most 32 directory sectors).

`src/plm/archive/80un.plm`, the program in one file from before it was split
into modules, is left as it was. The Makefile does not build it, and it still
relies on the widening: `p(0) + shl(p(1), 8)` in its `readword`,
`+ shl(getbyte, 8)` for the ARC header sizes and the crunch checksum, and other
BYTE shifts like the ones fixed in the modules.

With uplm80 0.4.1 the fixed sources compile to the same assembly, and the same
`80un.com` and `80unbas.com`, byte for byte, as before the change. With uplm80
patched to give a shifted BYTE a BYTE result, the new build extracts from the
23 archives and compressed files under `tests/` the same 136 files the 0.4.1
build extracts, byte for byte, and detokenises BASIC identically. The 23 hold
142 files; both builds lose the same six to older defects this change does not
touch. In `tests/test.arc` the compressed size of `BYE520.ASM` passes 64K and
`input$limit` keeps only its low 16 bits, so that member comes out as 19840 of
its 162304 bytes and the five members after it are lost; and the one file in
`zex-sage.dzc` is stored as `ZEX/SAGE.DOC`, which cannot be created. The
committed binaries are not rebuilt.

An archive member of 64K or more is read to its end. `getbyte` stops at the
end of the member being decoded, and it counted that end in one 16-bit word,
with 0FFFFH standing for no limit at all. An ARC header gives the compressed
size in 32 bits, and `extract$arc$member` kept only the low word, so a member
of 64K or more stopped early and the next header was looked for in the middle
of its data: `BYE520.ASM` in `tests/test.arc`, 75584 bytes compressed, stopped
after 10048 of them with 19840 of its 162304 bytes written, and the five members
after it were lost. A member of exactly 65535 bytes read as no limit and ran on
into the next one, and method 3 took its size as the same low word. The limit is
now 32 bits (`set$input$limit` in `src/plm/io.plm`), every ARC method reads to
it and no further, and all 18 members of `tests/test.arc` come out with the
CRC-16 their headers carry. A member whose file cannot be created is skipped
over rather than leaving the next header unfound.

An LBR member is held to its length too. The length is a count of 128-byte
sectors, at most 65535 of them (8 MB less 128 bytes, the most the format can
describe), and a squeezed, crunched or CrLZH member was decoded with no limit,
so a stream that did not end read on into the next member. It now stops at the
member's last sector, a limit of up to 23 bits. `uncrlzh` reads its header
through `getbyte`, as `unsqueeze` and `uncrunch` do, so that the header counts.

The squeeze decoders, `unsqueeze` and ARC method 4, stopped as soon as the last
byte of their input had been read. A Huffman code can be a single bit, so whole
symbols after the one that fetched that byte were dropped, and with the limit an
LBR member whose stream fills its last sector would have lost them too. They now
go on while bits are left, and stop at a symbol that would need a bit past the
end.

Nothing else carries a member's size. The squeeze, crunch and CrLZH streams
have no length field and end with a code of their own, the output is written a
128-byte record at a time with no count kept, and the position of the next
header is only ever the input file's own sequential position. Every format here
can hold a member of 64K or more: ARC sizes are 32 bits, an LBR member runs to
65535 sectors, and the streams have no size at all; the bound is CP/M 2.2's own
8 MB file.

Seven archives built to cross the old limits extract correctly under uplm80
0.4.2 and under uplm80 giving a shifted BYTE a BYTE result: a method 2 member of
100000 bytes, method 3 and method 4 members over 64K compressed, a method 4
member of exactly 65535 bytes, a squeezed LBR member of 678 sectors, and an ARC
and an LBR member with whole symbols in their last byte, each followed by a
member that must still be found. Before this change four of them came out wrong:
the method 3 and method 4 members over 64K were cut short and the member after
each was lost, the member after the one of exactly 65535 bytes was lost, and the
ARC member with symbols in its last byte lost them. The LBR members came out
right only because nothing held a member to its length then.

A squeezed file that uses every byte value no longer hangs 80un. With the end
code that is 257 symbols, and a Huffman tree of 256 nodes, and `unsqueeze` and
ARC method 4 counted the nodes read in a BYTE up to `LOW(node$count)`, which is
0 for 256: the tree was read as empty and the decoder walked stale nodes until
cpmemu gave up after 9 billion instructions. Binaries are the files most likely
to use every value. The count is 16 bits now, and a squeezed file and an ARC
method 4 member of all 256 values extract correctly under both compilers.

Nor does an empty squeezed file, or a Huffman tree that never reaches a leaf.
SQ writes an empty file as a tree of no nodes followed by no code bits, and
`src/un80` decodes that to nothing; `unsqueeze` and ARC method 4 read a bit only
inside a node, so with no nodes they read none and went round for ever, whether
the file stood alone or was a member of an LBR or an ARC, and the members after
it were never reached. It hung 24739a3 the same way. They now write an empty
file. And they stop at the first bit read from past the end of the input, leaf
or not, where they stopped only at a leaf: a tree whose nodes lead back to one
another never reaches one, and read on for ever too. It now ends at the end of
the input with what was decoded before it, as it does in `src/un80`.

A Huffman tree with a child past its last node ends the decoding in both, where
80un went back to the root and wrote whatever the rest of the bits made, and
`src/un80`'s ARC method 4 raised `IndexError`, which ended `extract_arc` and
lost the whole archive. `src/un80` raised it too for an empty method 4 member
with a byte of padding after its node count; that is an empty file now, as it
already was in `unsqueeze`.

So does a Huffman leaf above 256, in both. A leaf is a byte, 0 to 255, or the
end code 256, and a child of -300, a leaf of 299, is neither: the tree is
corrupt. 80un wrote the leaf's low byte and went on decoding; `src/un80`'s ARC
method 4 passed 299 to `bytearray.append`, whose `ValueError` `extract_arc`
does not catch, and the whole archive was lost. Its squeeze module already
stopped there. Now all of them stop at the leaf, with what was decoded before
it, as at a child past the tree, and 80un and `src/un80` write the same file:
of `ABAB`, the leaf and more, `ABAB`.

An ARC member that will not decode no longer ends the archive. When a
member's decoder failed, on a Huffman tree of more than 256 nodes for example,
or its file could not be written, `extract$arc$member` returned 0 and
`extract$arc` stopped, although the member's data had been read through and
the next header was where it should be: every member after it was lost. 80un
now says `Error` for that member and goes on, as `src/un80` does and as it
already did for one that cannot be created. What the member's file holds is
what was written of it before the error; `src/un80` writes the member's stored
data instead.

An LBR member that will not decode says `Error` too, and 80un goes on to the
next member, as in an ARC. When `unsqueeze`, `uncrunch` or `uncrlzh` failed on
an LBR member, on a squeeze tree of more than 256 nodes or a Crunch V1 member
of siglevel 15H for example, or its file would not take all of it, 80un said
`OK` and counted it. So it did for a stored member whose sectors ran past the
end of the file, writing the last sector read again in place of each one
missing, and a member none of whose sectors were in the file got no word at
all. Each of them says `Error` now and is not counted. As in an ARC, the
member's file holds the 128-byte records written before the error, without the
part record after them: nothing, for a tree too large or a siglevel refused,
which fail before a byte is decoded, and the sectors that are there for a
stored member cut short, which is what `src/un80` writes for it. For a member
that will not decode, `src/un80` writes the member's stored data. Its squeeze
module now refuses a tree of more than 256 nodes, as USQ, 80un and its own ARC
method 4 refuse it: the 257 symbols, the bytes and the end code, take a node
for each but one. It decoded such a tree when the file was long enough to hold
it.

A squeezed or Crunch V2 member cut short in its codes, its sectors not all in
the file, comes out as `src/un80` writes it. The Crunch V2 decoder went on
while a byte of its input was left, and a code is 9 to 12 bits, so it finished
the last code with bits of the ^Z that `getbyte` gives past the end, and
decoded it: `-SOURCE.NZT` cut to one sector gave 110 bytes ending `bably not.`,
where `src/un80`, whose bit reader gives the end code when fewer bits than a
code are left, writes 109 ending `bably not`. A code that needs a bit from past
the end now ends the decoding. A squeezed member cut short in its Huffman tree
said `OK` with an empty file: the nodes missing were read as ^Z, whose children
are past the tree. `src/un80` refuses it ("Data too short for Huffman tree")
and writes it as it is stored; 80un says `Error` now, as for any member that
will not decode, and so it does for a crunched member cut short in its header,
which said `OK` with an empty file when it was V2, and for an ARC method 4
member whose tree is not all in the member. Each sample of the two formats was
made the last member of an LBR, its directory length left whole, and cut at
every sector, and each cut was run under both compilers alike: of the 544 cuts
of the four Crunch V2 samples (`-SOURCE.NZT`, `COMMON.LZB`, `CRUNCH.CZM`,
`tests/test.lzt`), 177 wrote 1 to 144 bytes more than `src/un80`, and all 544
are what it writes now; of the 71 cuts of the four squeezed ones (`555-ic.bqs`,
`mbastip.tqt`, `tests/test.aqm`, `tests/test.dqc`), the 9 in the tree say
`Error`, and the other 62 are what `src/un80` writes, as they were.

So a squeezed or Crunch V2 LBR member cut short says `OK` when its header, and
a squeezed member's tree, are in the file, and holds what the codes before the
first one cut short decode to, and it is an `Error` when they are not. A Crunch
V1 member cut short is an `Error`. A CrLZH member is decoded on past the end,
by 80un from the ^Z it reads there and by `src/un80` from zero bits, until that
happens to make the stop code, so the two write different bytes after the data
there.

Crunch V1 is decoded, by 80un and by `src/un80`. The one file in
`tests/samples/crunch/zex-sage.dzc` is V1 (siglevel 10H): `src/un80` refused
it, and 80un, had it been able to create the file, would have run it through
the V2 decoder with 12-bit codes and written rubbish. V1 is the second decoder
in GEL's UNCR24 (1768-19AA), and both now follow it. Its codes are 12 bits
throughout, and a code is the slot in a 4096-entry table that its string was
hashed into: the middle twelve bits of ((prefix + suffix) OR 800H) squared, and
on a collision the first free slot from 101 past the end of the chain that
starts there. That is the "crunched" LZW of ARC methods 5 and 6 except that
slot 0 is reserved, which makes code 0 the end of the stream; a table that
takes slot 0 as free goes wrong at the first string hashed there, 900 bytes
into `ZEX/SAGE.DOC`. Past 4095 entries no more are made. UNCR24 decodes V1 only
up to siglevel 10H, and so do these; 11H to 1FH is refused. `zex-sage.dzc` now
decodes to the 4992 bytes UNCR24 writes for it under cpmemu, whose byte sum is
the 9882H the file stores after its end code, and a 60000-byte V1 stream that
fills the table decodes to its input under UNCR24, `src/un80` and both builds
of 80un. Its tables take the space of the V2 ones, so 80un needs no more
memory.

80un makes a CP/M name for every member, from any stored name, by one rule
(`src/plm/names.plm`, described in the README under "Member names on CP/M").
`ZEX/SAGE.DOC` could not be created: the ARC, squeeze, crunch and CrLZH paths
copied the stored name into the FCB as it stood, so a `/`, a lower-case name
from MS-DOS or Unix, or any other character CP/M does not take either failed
with "cannot create" or made a file the CCP cannot name, and a one- or
two-letter ARC type put NULs into the FCB. Only LBR mapped a few delimiters, to
`_`. Now bit 7 and the blanks around the name go, lower case becomes upper
case, the type is what follows the last `.`, every character CP/M does not take
in a name becomes `-`, the name is cut to 8 and the type to 3, an empty name
becomes `UNNAMED`, and a name already made in the run gets `-1`, `-2`, ... on
its end instead of overwriting the earlier file. A crunched or CrLZH name ends
at a `[`, as UNCR24 and `src/un80` end it, instead of carrying the note's `[`
into the name. When the name made differs from the one stored, 80un prints
`stored -> made`. `zex-sage.dzc` now extracts as `ZEX-SAGE.DOC`, and mouse.lbr's
`CCP/M.COM` and `CCP/M.LTR` as `CCP-M.COM` and `CCP-M.LTR`.

It is `src/un80`'s rule (replace, never split, number the duplicates) made for
CP/M, and it differs in the stand-in: `src/un80` writes `_`, and the CP/M 2.2
CCP takes `_` as a delimiter, like `=`, so `TYPE ZEX_SAGE.DOC` types a file
called `ZEX` and `ERA ZEX_SAGE.DOC` erases it. `-` is taken by every CCP and
every host. For the same reason a `_` in a stored name becomes `-` on CP/M.

An LBR member of no sectors is written as an empty file, as `src/un80` writes
it. 80un made no file for it, while `cpm$name` took its name all the same, so a
later member of that name came out as `NAME-1` with no `NAME`.

An LBR's directory length is 16 bits, as every length in the directory is, and
80un read only its low byte, so a directory of 260 (0104H) sectors was taken as
4: of the 20 members of such an LBR it extracted the 15 in the first four
sectors, said nothing of the other 5, and ended `15 file(s) extracted`.
`src/un80` refuses that directory ("Invalid directory size"), and so does 80un
now: its buffer holds 32 sectors, 128 entries, the most `src/un80` takes, and a
directory of no sectors or of more than 32, a high byte other than 0 among
them, is refused with `Invalid LBR file`, and nothing is extracted. An LBR that
ends inside its directory has only the entries in the sectors there, as in
`src/un80`; 80un took the rest from whatever its buffer held before, and made
members called `UNNAMED` out of them.

80un keeps its table of names below the BDOS, and refuses a TPA too small for
its buffers. The buffers end 34120 bytes past the program, and 256 names of 11
bytes after them ended near F05AH with uplm80 0.4.2. 80un never compared either
with the BDOS address at 0006H, and a 64K CP/M 2.2 has its BDOS entry at EC06H:
there an ARC of more than about 150 members wrote names over the BDOS, where
24739a3, whose data ended at E058H, fit. 80un now reads 0006H at startup, keeps
128 bytes under it for the stack (which goes no deeper than 24 bytes on any
test input), and keeps as many names as fit in the rest, up to 256: about 100
in a 64K CP/M 2.2 (95 with uplm80 0.4.2, 101 with the BYTE shift rule, the
archive's own among them). Past that, names are still made by the rule but no
longer kept, so two members made alike after the first hundred or so can land
on one file; an archive of fewer members, or of more with names that do not
come out alike, is not touched by it. When the buffers and one name do not fit
below the BDOS, 80un says `Not enough memory` and stops, where it used to run
and write over the BDOS. It needs about 58K of TPA: the BDOS entry at 0006H
must be at E7F6H or above (E7B3H with the BYTE shift rule).

No member is written over the archive being read. A member whose name, as made
by the rule, was the archive's own deleted the archive and wrote itself in its
place: under cpmemu `SELF.ARC` holding `SELF.ARC` was overwritten, an LBR,
which is reopened for each member, lost every member after that one, and on
CP/M the blocks freed can go to the new file in the middle of the read. The
archive's name now counts as one made already, when the archive is on the
drive the members are written to, so such a member is written as `SELF-1.ARC`.

The count of files extracted is 16 bits. It was a BYTE, and an ARC can hold
more than 255 members: one of 300 ended `44 file(s) extracted`.

With these changes 80un extracts all 142 files under `tests/`, under uplm80
0.4.2 and under uplm80 with the BYTE shift rule alike: 133 byte for byte as
`src/un80` extracts them and the other 9 the same up to the ^Z padding of the
last record, with every ARC member's CRC-16, the squeeze checksums and the
crunch byte sums checking. An ARC, an LBR and a squeezed file of 25 names CP/M
cannot take as they stand come out under the names the rule gives, and the 17
files of the nine big-member archives come out right: the seven above, and
`ALL256.ARC` and `ALL256.BQN`, the ARC method 4 member and the squeezed file of
all 256 byte values. Sixteen more inputs were made for the fixes after those:
empty squeezed files and trees that loop or point past their end, an ARC member
that will not decode, an LBR member of no sectors, archives holding their own
names, and archives of 100 and 300 members run with the BDOS entry at FD00H and
EC06H, and one at D006H. Of the 722 files they give, 721 are what `src/un80`
writes; the other is the member that will not decode, which 80un leaves as far
as it got (empty) and `src/un80` writes as stored. The D006H run says `Not
enough memory` and writes nothing. Both compilers give the same files and the
same console output for every one of these inputs. The four fixes made after
those, to the LBR directory's length, a Huffman leaf above 256, an LBR member
that will not decode and a member cut short, leave the files and the console
output of all of these inputs as they were, under both compilers, but for one
run. The checks for a member cut short take 62 bytes, and with uplm80 0.4.2
that leaves room below EC06H for 95 names where there was room for 101: of the
100 members of one name in the archive of 100 run there, the first 94 come out
as `D.TXT` and `D-1.TXT` to `D-93.TXT`, and the other six all as `D-94.TXT`,
which holds the last of them, as happens past the names kept (above). With the
BYTE shift rule there is room for 101, and all 100 come out. They were checked
on the review's `badleaf.arc`, whose `BADLEAF.TXT` 80un and `src/un80` now both
write as `A`, on its LBR of a 260-sector directory, which both now refuse, on
every sector cut of the squeeze and Crunch V2 samples above, and on the inputs
of the tests below.

### Added

`tests/test_80un_com.py` checks the CP/M program itself. It builds `80un.com`
from `src/plm` with the Makefile's rule in a scratch directory (the committed
binary is left alone), with the uplm80 on PATH or the command in `$UPLM80`,
runs it under cpmemu in binary mode, and compares every file it writes with
what `src/un80` extracts: all 18 members of `tests/test.arc`, `zex-sage.dzc`
(Crunch V1, stored as `ZEX/SAGE.DOC`), an ARC made on the fly with a stored
member of 100000 bytes and a packed one over 64K, and one of names CP/M cannot
take. Ten more tests build their inputs the same way: an empty squeezed file
alone, in an LBR and in an ARC, with ARC method 4 trees that loop and that
point past their end; a Huffman leaf of 299 in a squeezed file alone, as an LBR
member and as an ARC member; an ARC member that will not decode, followed by
two that must come out; an LBR of a squeezed member of 300 nodes, a Crunch V1
member of siglevel 15H, a stored member cut short and one wholly past the end
of the file, which must each say `Error`, and a member that must come out; an
LBR of `-SOURCE.NZT` cut to one sector, which must come out as `src/un80`
writes it, and of a Crunch V2 member cut short in its header, and an LBR member
and an ARC method 4 member cut short in their Huffman trees, which must each
say `Error`, each followed by a member that must come out; an LBR member of no
sectors followed by one of the same name; an ARC and an LBR that each hold a
member of their own name, which must be left as they were; an ARC of 300
members, run as it is, with 80un.com patched to find its BDOS at EC06H as in a
64K CP/M 2.2, and at D006H, where it must say `Not enough memory`; and an LBR
whose directory is 260 sectors long, which must be refused, and one that ends
inside its directory. Every run of 80un is given 60 seconds, where the longest
takes under 10, so that a decoder that never ends fails its test there; three
of the nine tests before these fixes gave it 60 seconds and the other six 300.
The tests are skipped when make, uplm80, um80, ul80 or cpmemu is missing. All
fourteen fail on the sources at 24739a3, the ten that build their inputs on
those at 782334d, the five for the directory's length, the leaf, the LBR member
that will not decode and the members cut short on those at 3cfeaf3, and the two
for the members cut short on those at 4fa1e83.

`tests/test_arc.py` checks that `src/un80`'s ARC method 4 reads an empty tree
with padding after it, a tree whose child is past its end and one with a leaf
of 299, and that an archive holding them extracts to its end.
`tests/test_squeeze.py` checks that its squeeze module takes a tree of 256
nodes and refuses one of 257.

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
