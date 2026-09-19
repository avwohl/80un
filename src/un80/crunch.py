"""
Crunch decompression for CP/M files.

Crunch uses LZW compression, similar to Unix compress.
It was derived from squeeze but uses different algorithms.

File format:
- Magic: 0x76 0xFE
- Original filename: null-terminated string
- 4 info bytes: reflevel, siglevel, errdetect, spare
- Checksum: 2 bytes (if errdetect > 0)
- Compressed data (MSB-first bit stream)

There are two main versions:
- V1.x: siglevel 0x10-0x1F, 12-bit fixed codes (a different algorithm; see below)
- V2.x: siglevel 0x20-0x2F, 9-12 bit variable codes

Special codes:
- 0x100 (256): EOF
- 0x101 (257): Adaptive reset (V2)
- 0x102-0x103 (258-259): Filler codes (skip)
- 0x104+ (260+): Dictionary entries

The V2 decoder below follows GEL Uncruncher v2.4 (UNCR24.COM), because CRUNCH's
dictionary does not simply freeze when it fills up.  Once 4096 entries exist,
UNCR switches to a second mode that *replaces* entries which have never been
referenced, and it picks the victim by walking the same open-addressed hash
table the compressor used.  A decoder that freezes the table instead
desynchronises from the compressor the moment the table fills, which corrupts
everything from that point on.  Comments name the UNCR24 addresses each
behaviour was taken from.

V1 (siglevel below 0x20) is a different algorithm living in a separate routine
of UNCR24 and is not implemented here; V1 input decodes to little or nothing.
"""

import struct
from dataclasses import dataclass

CRUNCH_MAGIC = 0x76FE
RLE_MARKER = 0x90

# LZW constants
EOF_CODE = 0x100      # 256
RESET_CODE = 0x101    # 257
FIRST_CODE = 0x104    # 260 - first dictionary entry
MAX_BITS = 12
TABLE_SIZE = 4096

# A crunch header's name field holds a CP/M name plus an optional free-form
# note.  Anything longer than this is corrupt input.
_MAX_NAME_FIELD = 128

# UNCR24 dictionary internals.
_HASH_SIZE = 0x138B   # 5003, the prime hash table size; wrap-around added at 0594
_HASH_BASE = 0x6000   # UNCR24 addresses the hash table from here (0549)
_EMPTY = 0x80         # "slot unused" marker written by the table clear at 0549
_USED = 0x20          # bit 5: "code has been referenced"; SET 5,(HL) at 03BB
_ROOT = 0x80          # bit 7: single-byte entry (prefix 0xFFFF); BIT 7,D at 03F8

# UNCR24's 19E6H, the dictionary-full state machine.
_FILLING = 0          # still appending entries
_LAST_PASS = 0xFE     # table just filled; one further append happens first
_REPLACING = 0xFF     # from here on, recycle never-referenced entries


class CrunchError(Exception):
    """Error during crunch decompression."""


@dataclass
class CrunchHeader:
    """Crunch file header information."""
    filename: str
    reflevel: int
    siglevel: int
    errdetect: int
    spare: int
    checksum: int
    data_offset: int
    note: str = ''

    @property
    def is_v2(self) -> bool:
        return self.siglevel >= 0x20

    @property
    def initial_bits(self) -> int:
        return 9 if self.is_v2 else 12


class BitReader:
    """Read variable-width codes from a byte stream, MSB first."""

    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.pos = offset
        self.bit_buffer = 0
        self.bits_in_buffer = 0

    def read_code(self, bits: int) -> int:
        """Read a code of the specified bit width (MSB first)."""
        while self.bits_in_buffer < bits:
            if self.pos >= len(self.data):
                return EOF_CODE  # Return EOF on end of data
            self.bit_buffer = (self.bit_buffer << 8) | self.data[self.pos]
            self.pos += 1
            self.bits_in_buffer += 8

        # Extract from the MSB side
        code = (self.bit_buffer >> (self.bits_in_buffer - bits)) & ((1 << bits) - 1)
        self.bits_in_buffer -= bits
        if self.bits_in_buffer > 0:
            self.bit_buffer &= (1 << self.bits_in_buffer) - 1
        else:
            self.bit_buffer = 0
        return code


def decode_rle(data: bytes) -> bytes:
    """
    Decode RLE90-encoded data.

    RLE90 uses 0x90 as an escape byte:
    - 0x90 0x00 = a literal 0x90; the "previous byte" register is left alone
    - 0x90 N (N > 0) = the previous byte occurs N times in TOTAL, so only N-1
      further copies are emitted - the previous byte was already written when
      it was read as a literal.
    - a 0x90 with no count byte after it is dropped.

    The N-1 is UNCR24's DEC A at 04AF; the untouched previous byte is the 04BF
    path, which writes 0x90 without reloading the previous-byte register; and a
    dangling 0x90 only arms the escape flag (04A9), so nothing is written.  All
    three were confirmed by running UNCR24.COM on crafted input under cpmemu.

    One deliberate difference from UNCR24: it decrements the count into the Z80
    B register and then runs a do-while loop, so `0x90 0x01` underflows to 256
    copies instead of none.  No encoder emits `0x90 0x01` - a run of one is just
    a literal - and reproducing the underflow would turn three bytes into 257,
    so this emits nothing, which is what the count actually means.
    """
    result = bytearray()
    prev_byte = 0
    i = 0

    while i < len(data):
        byte = data[i]
        i += 1

        if byte == RLE_MARKER:
            if i >= len(data):
                break

            count = data[i]
            i += 1

            if count == 0:
                result.append(RLE_MARKER)
            else:
                result.extend([prev_byte] * (count - 1))
        else:
            result.append(byte)
            prev_byte = byte

    return bytes(result)


def parse_header(data: bytes) -> CrunchHeader:
    """Parse the crunch file header."""
    if len(data) < 4:
        raise CrunchError("Data too short")

    # Check magic
    magic = (data[0] << 8) | data[1]
    if magic != CRUNCH_MAGIC:
        raise CrunchError(f"Invalid magic: 0x{magic:04X}")

    pos = 2

    # Read filename (null-terminated).  UNCR24 copies the name into a fixed
    # buffer, so a name that runs on past _MAX_NAME_FIELD is corrupt input, not
    # a name to hand to the filesystem.
    filename_start = pos
    scan_limit = min(len(data), filename_start + _MAX_NAME_FIELD)
    while pos < scan_limit and data[pos] != 0:
        pos += 1

    if pos >= scan_limit:
        raise CrunchError("Unterminated filename")

    # Mask high bits (CP/M attributes)
    name_field = ''.join(chr(b & 0x7F) for b in data[filename_start:pos])
    pos += 1  # Skip null

    # CRUNCH may append a free-form note to the name, e.g.
    # "MOUSE.MAC[04/01/87]" or "COMMON.LIB[ V2.4 INCLUDE FILE]".  UNCR24 stops
    # the filename at the '[' (0287-0291) and only displays the remainder, so
    # the note is not part of the name.  Leaving it in produced names with path
    # separators in them, which broke extraction of the whole archive.
    filename, bracket, rest = name_field.partition('[')
    note = (bracket + rest) if bracket else ''
    filename = filename.rstrip()

    if pos + 4 > len(data):
        raise CrunchError("Data too short for info bytes")

    # Read 4 info bytes
    reflevel = data[pos]
    siglevel = data[pos + 1]
    errdetect = data[pos + 2]
    spare = data[pos + 3]
    pos += 4

    # Read checksum if present
    checksum = 0
    if errdetect > 0:
        if pos + 2 > len(data):
            raise CrunchError("Data too short for checksum")
        checksum = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2

    return CrunchHeader(
        filename=filename,
        reflevel=reflevel,
        siglevel=siglevel,
        errdetect=errdetect,
        spare=spare,
        checksum=checksum,
        data_offset=pos,
        note=note,
    )


class _LzwTable:
    """
    UNCR24's LZW dictionary, including the parts a textbook decoder omits.

    Three parallel byte arrays hold the dictionary (UNCR24 keeps them at 3000H,
    4000H and 5000H):

      flags[code]   bit 7 = root entry, bit 5 = "referenced", low bits = prefix >> 8
      prefix[code]  low byte of the prefix code
      suffix[code]  the byte this entry appends to its prefix

    A separate open-addressed hash table (6000H and 7400H) maps a
    (prefix, suffix) pair to the code holding it.  Decoding never needs to look
    a pair up, but choosing a replacement victim does, and the victim has to be
    the one the compressor chose - so the decoder keeps the hash table too.

    The code width and the dictionary-full state live here as well because
    UNCR24 advances them from inside its insert routine (041B), which means an
    entry created by the KwKwK path widens the codes just like any other.
    """

    def __init__(self, initial_bits: int) -> None:
        self.initial_bits = initial_bits
        self.seed()

    def clear(self) -> None:
        """Clear the dictionary and the hash table (UNCR24 0549)."""
        self.flags = bytearray([_EMPTY] * TABLE_SIZE)
        self.prefix = bytearray(TABLE_SIZE)
        self.suffix = bytearray(TABLE_SIZE)
        # The initial probe can land one slot past the last real entry, so
        # over-allocate rather than mask every address.
        self.hash_hi = bytearray([_EMPTY] * (_HASH_SIZE + 0x200))
        self.hash_lo = bytearray([_EMPTY] * (_HASH_SIZE + 0x200))
        self.hash_hi[0] = 0x7F      # 056A: slot 0 never reads as empty
        self.next_code = 0
        self.code_size = self.initial_bits
        # UNCR24 compares the high byte of next_code + 1 against a doubling
        # threshold (0440) instead of testing next_code directly.
        self.threshold = 1 << (self.initial_bits - 8)
        self.state = _FILLING
        self.replacements = 0

    def seed(self) -> None:
        """Seed codes 0-255 (roots) and the four reserved codes (UNCR24 0521)."""
        self.clear()
        for byte in range(256):
            self.insert(0xFFFF, byte, flag=_USED)
        for _ in range(4):
            self.insert(0x7FFF, 0, flag=_USED)

    # -- hashing ----------------------------------------------------------
    @staticmethod
    def _hash(prefix: int, suffix: int) -> tuple[int, int]:
        """
        Hash a (prefix, suffix) pair (UNCR24 05D3).

        Returns the initial probe address and the probe stride.  Addresses keep
        UNCR24's own 0x6000 base so the stride arithmetic and the wrap test
        below read the same as the Z80 code does.
        """
        shifted = (prefix << 4) & 0xFFFF
        lo = suffix ^ (shifted >> 8)            # 05D8: XOR H
        hi = (0x60 + (prefix & 0x0F)) & 0xFF    # 05DB-05DF
        addr = ((hi << 8) | lo) + 1             # 05E0: INC HL
        stride = (addr + 0x8C75) & 0xFFFF       # 05E2-05E6: a large, hence
        return addr, stride                     # effectively negative, step

    @staticmethod
    def _probe(addr: int, stride: int) -> int:
        """Step to the next slot on a probe chain (UNCR24 058A)."""
        addr = (addr + stride) & 0xFFFF
        if (addr >> 8) < 0x60:                  # 058F-0592: dropped below 6000H
            addr = (addr + _HASH_SIZE) & 0xFFFF
        return addr

    def _hash_insert(self, prefix: int, suffix: int) -> None:
        """Record (prefix, suffix) -> next_code in the hash table (UNCR24 0570)."""
        addr, stride = self._hash(prefix, suffix)
        # A well-formed stream leaves free slots, so the chain always ends. The
        # bound only stops corrupt input from spinning here forever, which is
        # what UNCR24 itself would do.
        for _ in range(_HASH_SIZE):
            if self.hash_hi[addr - _HASH_BASE] == _EMPTY:
                slot = addr - _HASH_BASE
                self.hash_hi[slot] = (self.next_code >> 8) & 0xFF
                self.hash_lo[slot] = self.next_code & 0xFF
                return
            addr = self._probe(addr, stride)

    # -- table maintenance ------------------------------------------------
    def insert(self, prefix: int, suffix: int, flag: int = 0) -> None:
        """Append a dictionary entry and advance the code width (UNCR24 041B)."""
        self._hash_insert(prefix, suffix)
        code = self.next_code
        if code < TABLE_SIZE:
            self.flags[code] = flag | ((prefix >> 8) & 0xFF)
            self.prefix[code] = prefix & 0xFF
            self.suffix[code] = suffix
        self.next_code = code + 1

        # 0440: widen the codes, or declare the dictionary full.
        if ((self.next_code + 1) >> 8) & 0xFF == self.threshold:
            self.threshold = (self.threshold << 1) & 0xFF
            if self.code_size + 1 > MAX_BITS:   # 044E: CP 0DH
                self.state = _LAST_PASS         # 0456
            else:
                self.code_size += 1

    def replace(self, prefix: int, suffix: int) -> None:
        """
        Reuse a never-referenced entry for (prefix, suffix) (UNCR24 0599).

        The victim is the first entry on this pair's probe chain whose
        "referenced" bit is clear.  The victim keeps its code number and its
        hash slot, so the chain stays intact and a later lookup of the new pair
        still finds it.  If the chain reaches an unused slot first, nothing is
        added at all - that is UNCR24's RZ at 059F, and it is why a full
        dictionary still turns away most new strings.
        """
        addr, stride = self._hash(prefix, suffix)
        # Bounded for the same reason as _hash_insert: corrupt input must not
        # be able to spin on a chain with no free slot and no unused entry.
        for _ in range(_HASH_SIZE):
            slot = addr - _HASH_BASE
            if self.hash_hi[slot] == _EMPTY:            # 059D-059F
                return
            victim = (self.hash_hi[slot] << 8) | self.hash_lo[slot]
            if victim < TABLE_SIZE and not self.flags[victim] & _USED:   # 05AB
                self.replacements += 1                  # 05B6
                self.flags[victim] = (prefix >> 8) & 0xFF
                self.prefix[victim] = prefix & 0xFF
                self.suffix[victim] = suffix
                return
            addr = self._probe(addr, stride)


def uncrunch_lzw(data: bytes, start_pos: int, initial_bits: int, is_v2: bool) -> bytes:
    """
    Decompress LZW-encoded data.

    Args:
        data: Full file data
        start_pos: Offset where compressed data starts
        initial_bits: Initial code width (9 for V2, 12 for V1)
        is_v2: Whether this is V2 format (variable bit width)

    Returns:
        The decoded byte stream, still RLE90-encoded - run decode_rle over it.
    """
    bits = BitReader(data, start_pos)
    table = _LzwTable(initial_bits)

    result = bytearray()
    prev_code = 0xFFFF      # 19FBH
    first_byte = 0          # 1A7FH: first byte of the string last emitted
    skip_insert = True      # 19FDH: the very first code creates no entry
    replacing = False       # running the 030A loop rather than the 02DB one

    def emit(code: int) -> bool:
        """
        Append the string for `code` to result (UNCR24 03BE).

        Returns False when the code names an entry that does not exist and
        cannot be synthesised, i.e. the stream is corrupt or truncated.
        """
        nonlocal first_byte, skip_insert
        stack = []
        # A prefix chain cannot be longer than the table.  Corrupt input, or a
        # replacement that closes a cycle, would otherwise walk forever; UNCR24
        # catches the same case with its "Stack Overflow" check at 03BE.
        while len(stack) <= TABLE_SIZE:
            flags = table.flags[code]
            if (flags & ~_USED & 0xFF) == _EMPTY:   # 03CE: AND 0DFH / CP 80H
                # The compressor used the code for the entry it is about to
                # create (the classic KwKwK case), so create it here and now.
                skip_insert = True                  # 03D4
                table.insert(prev_code, first_byte, flag=_USED)
                flags = table.flags[code]
                if (flags & ~_USED & 0xFF) == _EMPTY:   # 03EE: still missing
                    return False
            stack.append(table.suffix[code])
            if flags & _ROOT:                       # 03F8: single-byte entry
                first_byte = table.suffix[code]     # 040F: LD (1A7FH),A
                break
            # 03FC: RES 5,D - bit 5 is a flag, not part of the prefix code
            code = ((flags & ~_USED & 0xFF) << 8) | table.prefix[code]
            if code >= TABLE_SIZE:
                return False
        else:
            # Fell out of the bound without reaching a root entry.
            return False
        result.extend(reversed(stack))
        return True

    while True:
        code = bits.read_code(table.code_size)

        # Skip filler codes (V2 only)
        while code in (258, 259):
            code = bits.read_code(table.code_size)

        if code == EOF_CODE:
            break

        if code == RESET_CODE:
            table.seed()                            # 032E
            prev_code = 0xFFFF
            skip_insert = True
            replacing = False
            continue

        table.flags[code] |= _USED                  # 03BB: SET 5,(HL)
        if not emit(code):
            break

        if replacing:
            # 030A: the dictionary is full, so recycle rather than append.
            table.replace(prev_code, first_byte)
        else:
            was_skipped = skip_insert               # 02EC: SRL (HL) tests, clears
            skip_insert = False
            if not was_skipped:
                table.insert(prev_code, first_byte)
            # 02F9-0308: 0xFE grants one further append, then replacement mode.
            if table.state == _LAST_PASS:
                table.state = _REPLACING
            elif table.state == _REPLACING:
                replacing = True

        prev_code = code

    return bytes(result)


def uncrunch(data: bytes) -> bytes:
    """
    Decompress crunched data.

    Args:
        data: Crunched file data (including magic header)

    Returns:
        Decompressed data

    Raises:
        CrunchError: If decompression fails
    """
    header = parse_header(data)

    # V1 (siglevel below 0x20) is a different algorithm, which UNCR24 handles in
    # a separate routine.  Running the V2 decoder over V1 input produces a short
    # run of rubbish, so say so rather than reporting success.
    if not header.is_v2:
        raise CrunchError(
            f"Crunch V1 (siglevel 0x{header.siglevel:02X}) is not supported; "
            "V1 uses a different algorithm from V2"
        )

    # Decompress using LZW
    result = uncrunch_lzw(
        data,
        header.data_offset,
        header.initial_bits,
        header.is_v2,
    )

    # Decode RLE if present
    if RLE_MARKER in result:
        result = decode_rle(result)

    return result


def get_crunched_filename(data: bytes) -> str | None:
    """
    Extract the original filename from crunched data.

    Args:
        data: Crunched file data

    Returns:
        Original filename or None if not valid
    """
    try:
        header = parse_header(data)
        return header.filename
    except CrunchError:
        return None


def get_crunch_info(data: bytes) -> dict | None:
    """
    Get detailed info about a crunched file.

    Args:
        data: Crunched file data

    Returns:
        Dictionary with version info, or None if not valid
    """
    try:
        header = parse_header(data)
        version = 2 if header.is_v2 else 1
        return {
            'filename': header.filename,
            'note': header.note,
            'version': version,
            'siglevel': header.siglevel,
            'bits': f"{header.initial_bits}-12" if header.is_v2 else "12 (fixed)",
            'description': f"V{version}.x ({'variable' if header.is_v2 else 'fixed'} codes)",
        }
    except CrunchError:
        return None
