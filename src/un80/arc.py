"""
ARC archive format support.

ARC is a compressed archive format popular on CP/M and DOS.
Each member can use a different compression method.

File structure:
- Sequence of member entries
- Each entry: 0x1A marker + method byte + header + data
- Archive ends with 0x1A 0x00

Member header (after marker and method):
  Offset  Size  Description
  0       13    Filename (null-terminated, 13 chars max)
  13      4     Compressed size (little-endian)
  17      4     Date/time in DOS format
  21      2     CRC-16
  23      4     Original size (little-endian)

Compression methods:
  0 - End of archive
  1 - Stored (obsolete, ARC 1.0)
  2 - Stored (ARC 3.1+)
  3 - Packed (RLE)
  4 - Squeezed (Huffman after RLE)
  5 - Crunched (LZW, obsolete)
  6 - Crunched with RLE (obsolete)
  7 - Crunched with faster hash
  8 - Crunched (12-bit LZW)
  9 - Squashed (13-bit LZW, Phil Katz)
"""

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

ARC_MARKER = 0x1A


class ArcError(Exception):
    """Error during ARC processing."""


@dataclass
class ArcEntry:
    """A single entry in an ARC archive."""
    method: int
    filename: str
    compressed_size: int
    original_size: int
    crc: int
    datetime: int
    data_offset: int  # Offset in file where compressed data starts

    @property
    def method_name(self) -> str:
        """Human-readable compression method name."""
        methods = {
            0: 'end',
            1: 'stored (old)',
            2: 'stored',
            3: 'packed (RLE)',
            4: 'squeezed',
            5: 'crunched (old)',
            6: 'crunched+RLE',
            7: 'crunched',
            8: 'crunched LZW',
            9: 'squashed',
        }
        return methods.get(self.method, f'unknown ({self.method})')


def parse_header(f: BinaryIO) -> ArcEntry | None:
    """
    Parse an ARC member header.

    Args:
        f: Open file positioned at start of entry (0x1A byte)

    Returns:
        ArcEntry or None for end of archive
    """
    marker = f.read(1)
    if not marker:
        return None
    if marker[0] != ARC_MARKER:
        raise ArcError(f"Invalid marker: 0x{marker[0]:02X}")

    method_byte = f.read(1)
    if not method_byte:
        return None
    method = method_byte[0]

    if method == 0:
        return None  # End of archive

    # Read header fields (25 bytes total after marker and method)
    # Offset 0: 13 bytes filename (null-terminated, but may use all 13)
    # Offset 13: 4 bytes compressed size
    # Offset 17: 2 bytes date
    # Offset 19: 2 bytes time
    # Offset 21: 2 bytes CRC
    # Offset 23: 4 bytes original size (only present for method >= 2)

    if method == 1:
        # Old format without original size field
        header = f.read(23)
        if len(header) < 23:
            raise ArcError("Truncated header")
        original_size_bytes = b''
    else:
        header = f.read(27)
        if len(header) < 27:
            raise ArcError("Truncated header")
        original_size_bytes = header[23:27]

    # Filename is null-terminated, up to 13 chars
    filename_bytes = header[0:13]
    null_pos = filename_bytes.find(0)
    if null_pos >= 0:
        filename_bytes = filename_bytes[:null_pos]
    filename = filename_bytes.decode('ascii', errors='replace')

    # Parse numeric fields (little-endian)
    compressed_size = struct.unpack('<I', header[13:17])[0]
    datetime = struct.unpack('<I', header[17:21])[0]
    crc = struct.unpack('<H', header[21:23])[0]
    if original_size_bytes:
        original_size = struct.unpack('<I', original_size_bytes)[0]
    else:
        original_size = compressed_size

    data_offset = f.tell()

    return ArcEntry(
        method=method,
        filename=filename,
        compressed_size=compressed_size,
        original_size=original_size,
        crc=crc,
        datetime=datetime,
        data_offset=data_offset,
    )


class BitReader:
    """Read variable-width codes from a byte stream."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.bit_buffer = 0
        self.bits_in_buffer = 0

    def read_bits(self, count: int) -> int:
        while self.bits_in_buffer < count:
            if self.pos >= len(self.data):
                raise ArcError("Unexpected end of data")
            self.bit_buffer |= self.data[self.pos] << self.bits_in_buffer
            self.pos += 1
            self.bits_in_buffer += 8

        result = self.bit_buffer & ((1 << count) - 1)
        self.bit_buffer >>= count
        self.bits_in_buffer -= count
        return result


def decode_rle(data: bytes) -> bytes:
    """Decode RLE90-encoded data."""
    result = bytearray()
    prev = 0
    i = 0

    while i < len(data):
        byte = data[i]
        i += 1

        if byte == 0x90:
            if i >= len(data):
                result.append(0x90)
                break
            count = data[i]
            i += 1
            if count == 0:
                result.append(0x90)
                prev = 0x90
            else:
                result.extend([prev] * count)
        else:
            result.append(byte)
            prev = byte

    return bytes(result)


def decompress_squeezed(data: bytes) -> bytes:
    """
    Decompress ARC method 4 (squeezed) data.

    This is Huffman coding applied after RLE.
    """
    if len(data) < 2:
        return data

    # Read Huffman tree
    bits = BitReader(data)

    # Number of nodes
    node_count = bits.read_bits(16)
    if node_count > 256:
        raise ArcError(f"Too many Huffman nodes: {node_count}")

    # Read node table
    nodes = []
    for _ in range(node_count):
        left = bits.read_bits(16)
        right = bits.read_bits(16)
        # Convert to signed
        if left >= 0x8000:
            left -= 0x10000
        if right >= 0x8000:
            right -= 0x10000
        nodes.append((left, right))

    # Decode using Huffman tree
    result = bytearray()
    while True:
        try:
            node = 0
            while node >= 0:
                bit = bits.read_bits(1)
                left, right = nodes[node]
                node = right if bit else left

            # Leaf: value is -(node + 1)
            value = -(node + 1)
            if value == 256:  # EOF
                break
            result.append(value)
        except ArcError:
            break

    # Decode RLE
    return decode_rle(bytes(result))


def decompress_lzw_arc8(data: bytes) -> bytes:
    """
    Decompress ARC method 8 (Crunched) LZW-encoded data.

    ARC method 8 uses:
    - LSB-first bit order
    - 9-12 bit variable codes
    - Code 256 = clear/reset
    - First dictionary entry at 257
    - 1-byte header (max bits)
    """
    if len(data) < 2:
        return b''

    # First byte is the max bits value
    max_bits = data[0]
    if max_bits < 9 or max_bits > 16:
        max_bits = 12  # Default

    bits = BitReader(data[1:])  # Skip header byte
    dictionary: dict[int, bytes] = {i: bytes([i]) for i in range(256)}

    CLEAR_CODE = 256
    FIRST_CODE = 257

    result = bytearray()
    code_size = 9
    next_code = FIRST_CODE
    max_code_for_size = (1 << code_size) - 1

    prev_string = b''
    first = True

    while True:
        try:
            code = bits.read_bits(code_size)
        except ArcError:
            break

        if code == CLEAR_CODE:
            dictionary = {i: bytes([i]) for i in range(256)}
            code_size = 9
            next_code = FIRST_CODE
            max_code_for_size = (1 << code_size) - 1
            prev_string = b''
            first = True
            continue

        # Decode
        if code < 256:
            string = bytes([code])
        elif code in dictionary:
            string = dictionary[code]
        elif code == next_code and prev_string:
            string = prev_string + prev_string[0:1]
        else:
            break

        result.extend(string)

        # Add to dictionary (except for first code)
        if not first and prev_string:
            if next_code < (1 << max_bits):
                dictionary[next_code] = prev_string + string[0:1]
                next_code += 1

                # Increase code size when needed
                if next_code > max_code_for_size and code_size < max_bits:
                    code_size += 1
                    max_code_for_size = (1 << code_size) - 1

        prev_string = string
        first = False

    return bytes(result)


def decompress_lzw_arc56(data: bytes) -> bytes:
    """
    Decompress ARC methods 5-6 (old crunched) LZW-encoded data.

    Methods 5-6 use:
    - MSB-first bit order
    - Fixed 12-bit codes
    - No clear code
    - Hashed dictionary
    """
    if not data:
        return b''

    # MSB-first bit reader
    bit_buffer = 0
    bits_in_buffer = 0
    pos = 0

    def read_bits_msb(n):
        nonlocal bit_buffer, bits_in_buffer, pos
        while bits_in_buffer < n:
            if pos >= len(data):
                raise ArcError("End of data")
            bit_buffer = (bit_buffer << 8) | data[pos]
            pos += 1
            bits_in_buffer += 8
        code = (bit_buffer >> (bits_in_buffer - n)) & ((1 << n) - 1)
        bits_in_buffer -= n
        if bits_in_buffer > 0:
            bit_buffer &= (1 << bits_in_buffer) - 1
        else:
            bit_buffer = 0
        return code

    dictionary: dict[int, bytes] = {i: bytes([i]) for i in range(256)}
    FIRST_CODE = 256

    result = bytearray()
    next_code = FIRST_CODE
    prev_string = b''
    first = True

    while True:
        try:
            code = read_bits_msb(12)
        except ArcError:
            break

        # Decode
        if code < 256:
            string = bytes([code])
        elif code in dictionary:
            string = dictionary[code]
        elif code == next_code and prev_string:
            string = prev_string + prev_string[0:1]
        else:
            break

        result.extend(string)

        # Add to dictionary
        if not first and prev_string:
            if next_code < 4096:
                dictionary[next_code] = prev_string + string[0:1]
                next_code += 1

        prev_string = string
        first = False

    return bytes(result)


def decompress_member(entry: ArcEntry, data: bytes) -> bytes:
    """
    Decompress a member's data based on its method.
    """
    if entry.method in (1, 2):
        # Stored
        return data

    if entry.method == 3:
        # RLE only
        return decode_rle(data)

    if entry.method == 4:
        # Squeezed (Huffman + RLE)
        return decompress_squeezed(data)

    if entry.method in (5, 6):
        # Old crunched (MSB-first, fixed 12-bit)
        result = decompress_lzw_arc56(data)
        if entry.method == 6:
            result = decode_rle(result)
        return result

    if entry.method == 7:
        # Crunched with faster hash - try arc8 format
        result = decompress_lzw_arc8(data)
        return decode_rle(result)

    if entry.method == 8:
        # Crunched (LSB-first, 9-12 bit variable, with RLE)
        result = decompress_lzw_arc8(data)
        return decode_rle(result)

    if entry.method == 9:
        # Squashed (13-bit LZW, no RLE, no header)
        # Similar to arc8 but max 13 bits and no header byte
        bits = BitReader(data)
        dictionary: dict[int, bytes] = {i: bytes([i]) for i in range(256)}
        CLEAR_CODE = 256
        FIRST_CODE = 257
        result = bytearray()
        code_size = 9
        next_code = FIRST_CODE
        prev_string = b''
        first = True

        while True:
            try:
                code = bits.read_bits(code_size)
            except ArcError:
                break
            if code == CLEAR_CODE:
                dictionary = {i: bytes([i]) for i in range(256)}
                code_size = 9
                next_code = FIRST_CODE
                prev_string = b''
                first = True
                continue
            if code < 256:
                string = bytes([code])
            elif code in dictionary:
                string = dictionary[code]
            elif code == next_code and prev_string:
                string = prev_string + prev_string[0:1]
            else:
                break
            result.extend(string)
            if not first and prev_string and next_code < 8192:
                dictionary[next_code] = prev_string + string[0:1]
                next_code += 1
                if next_code > (1 << code_size) - 1 and code_size < 13:
                    code_size += 1
            prev_string = string
            first = False
        return bytes(result)

    raise ArcError(f"Unsupported compression method: {entry.method}")


def list_arc(path: str | Path) -> list[ArcEntry]:
    """
    List contents of an ARC archive.

    Args:
        path: Path to the ARC file

    Returns:
        List of entries in the archive
    """
    entries = []

    with open(path, 'rb') as f:
        while True:
            entry = parse_header(f)
            if entry is None:
                break
            entries.append(entry)
            f.seek(entry.data_offset + entry.compressed_size)

    return entries


def extract_arc(
    path: str | Path,
    output_dir: str | Path | None = None,
    *,
    convert_text: bool = False,
) -> list[tuple[str, bytes]]:
    """
    Extract all files from an ARC archive.

    Args:
        path: Path to the ARC file
        output_dir: Directory to extract to. If None, returns data in memory.
        convert_text: Whether to convert text files (strip ^Z, CR/LF to LF)

    Returns:
        List of (filename, data) tuples for extracted files
    """
    from .cpm import strip_cpm_eof, crlf_to_lf, is_text_file

    path = Path(path)
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    with open(path, 'rb') as f:
        while True:
            entry = parse_header(f)
            if entry is None:
                break

            # Read compressed data
            compressed_data = f.read(entry.compressed_size)

            # Decompress
            try:
                data = decompress_member(entry, compressed_data)
            except ArcError:
                # Store raw data if decompression fails
                data = compressed_data

            filename = entry.filename

            # Optionally convert text files
            if convert_text and is_text_file(filename):
                data = strip_cpm_eof(data)
                data = crlf_to_lf(data)

            if output_dir:
                out_path = output_dir / filename
                out_path.write_bytes(data)

            results.append((filename, data))

    return results
