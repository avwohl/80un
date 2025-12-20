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
- V1.x: siglevel 0x10-0x1F, 12-bit fixed codes
- V2.x: siglevel 0x20-0x2F, 9-12 bit variable codes

Special codes:
- 0x100 (256): EOF
- 0x101 (257): Adaptive reset (V2)
- 0x102-0x103 (258-259): Filler codes (skip)
- 0x104+ (260+): Dictionary entries
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
    - 0x90 0x00 = literal 0x90
    - 0x90 N = repeat previous byte N times (N > 0)
    """
    result = bytearray()
    prev_byte = 0
    i = 0

    while i < len(data):
        byte = data[i]
        i += 1

        if byte == RLE_MARKER:
            if i >= len(data):
                result.append(RLE_MARKER)
                break

            count = data[i]
            i += 1

            if count == 0:
                result.append(RLE_MARKER)
                prev_byte = RLE_MARKER
            else:
                result.extend([prev_byte] * count)
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

    # Read filename (null-terminated)
    filename_start = pos
    while pos < len(data) and data[pos] != 0:
        pos += 1

    if pos >= len(data):
        raise CrunchError("Unterminated filename")

    # Mask high bits (CP/M attributes)
    filename = ''.join(chr(b & 0x7F) for b in data[filename_start:pos])
    pos += 1  # Skip null

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
    )


def uncrunch_lzw(data: bytes, start_pos: int, initial_bits: int, is_v2: bool) -> bytes:
    """
    Decompress LZW-encoded data.

    Args:
        data: Full file data
        start_pos: Offset where compressed data starts
        initial_bits: Initial code width (9 for V2, 12 for V1)
        is_v2: Whether this is V2 format (variable bit width)
    """
    bits = BitReader(data, start_pos)

    # Build initial dictionary with single-byte entries
    dictionary: dict[int, bytes] = {i: bytes([i]) for i in range(256)}

    result = bytearray()
    code_size = initial_bits
    next_code = FIRST_CODE  # 260
    prev_string = b''
    first_code = True

    while True:
        # V2: Increase code size when next_code reaches max for current size - 1
        # This ensures we have enough bits for the next code we might create
        if is_v2 and next_code == (1 << code_size) - 1 and code_size < MAX_BITS:
            code_size += 1

        code = bits.read_code(code_size)

        # Skip filler codes (V2 only)
        while code in (258, 259):
            code = bits.read_code(code_size)

        # Handle special codes
        if code == EOF_CODE:
            break

        if code == RESET_CODE:
            # Reset dictionary
            dictionary = {i: bytes([i]) for i in range(256)}
            code_size = initial_bits
            next_code = FIRST_CODE
            prev_string = b''
            first_code = True
            continue

        # Decode the code
        if code < 256:
            # Literal byte
            string = bytes([code])
        elif code in dictionary:
            # Known dictionary entry
            string = dictionary[code]
        elif code == next_code and prev_string:
            # Special case: code not yet in dictionary
            # This happens when the encoder outputs a code it just created
            string = prev_string + prev_string[0:1]
        else:
            # Unknown code - probably end of valid data
            break

        result.extend(string)

        # Add new dictionary entry (except for first code)
        if not first_code and prev_string:
            if next_code < TABLE_SIZE:
                dictionary[next_code] = prev_string + string[0:1]
                next_code += 1

        prev_string = string
        first_code = False

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
            'version': version,
            'siglevel': header.siglevel,
            'bits': f"{header.initial_bits}-12" if header.is_v2 else "12 (fixed)",
            'description': f"V{version}.x ({'variable' if header.is_v2 else 'fixed'} codes)",
        }
    except CrunchError:
        return None
