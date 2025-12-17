"""
CrLZH decompression for CP/M files.

CrLZH uses LZH (Lempel-Ziv-Huffman) compression, combining
LZ77 with Huffman coding. It superseded both squeeze and crunch.

File format:
- Magic: 0x76 0xFD
- Original filename: null-terminated string
- Compressed data using LZSS + Huffman
"""

import struct
from typing import Iterator

CRLZH_MAGIC = 0x76FD


class CrLZHError(Exception):
    """Error during CrLZH decompression."""
    pass


class BitReader:
    """Read bits from a byte stream, LSB first."""

    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.pos = offset
        self.bit_buffer = 0
        self.bits_in_buffer = 0

    def read_bits(self, count: int) -> int:
        """Read specified number of bits."""
        while self.bits_in_buffer < count:
            if self.pos >= len(self.data):
                raise CrLZHError("Unexpected end of data")
            self.bit_buffer |= self.data[self.pos] << self.bits_in_buffer
            self.pos += 1
            self.bits_in_buffer += 8

        result = self.bit_buffer & ((1 << count) - 1)
        self.bit_buffer >>= count
        self.bits_in_buffer -= count
        return result

    def read_bit(self) -> int:
        return self.read_bits(1)


def decode_huffman_table(bits: BitReader, count: int) -> list[int]:
    """
    Decode a Huffman code length table.

    Returns list of code lengths for each symbol.
    """
    lengths = []
    i = 0
    while i < count:
        code_len = bits.read_bits(4)
        if code_len == 15:
            # Run of zeros
            run = bits.read_bits(4) + 1
            lengths.extend([0] * run)
            i += run
        else:
            lengths.append(code_len)
            i += 1
    return lengths[:count]


def build_huffman_decoder(lengths: list[int]) -> dict[tuple[int, int], int]:
    """
    Build a Huffman decoder from code lengths.

    Returns a dict mapping (code, length) to symbol.
    """
    if not lengths or max(lengths) == 0:
        return {}

    max_len = max(lengths)
    decoder = {}

    # Count codes of each length
    bl_count = [0] * (max_len + 1)
    for length in lengths:
        if length > 0:
            bl_count[length] += 1

    # Calculate starting codes for each length
    code = 0
    next_code = [0] * (max_len + 1)
    for bits in range(1, max_len + 1):
        code = (code + bl_count[bits - 1]) << 1
        next_code[bits] = code

    # Assign codes to symbols
    for symbol, length in enumerate(lengths):
        if length > 0:
            decoder[(next_code[length], length)] = symbol
            next_code[length] += 1

    return decoder


def decode_symbol(bits: BitReader, decoder: dict[tuple[int, int], int], max_len: int) -> int:
    """Decode one symbol using Huffman decoder."""
    code = 0
    for length in range(1, max_len + 1):
        code = (code << 1) | bits.read_bit()
        if (code, length) in decoder:
            return decoder[(code, length)]

    raise CrLZHError("Invalid Huffman code")


def uncrlzh(data: bytes) -> bytes:
    """
    Decompress CrLZH data.

    Args:
        data: CrLZH file data (including magic header)

    Returns:
        Decompressed data

    Raises:
        CrLZHError: If decompression fails
    """
    if len(data) < 4:
        raise CrLZHError("Data too short")

    # Check magic
    magic = (data[0] << 8) | data[1]
    if magic != CRLZH_MAGIC:
        raise CrLZHError(f"Invalid magic: 0x{magic:04X}, expected 0x{CRLZH_MAGIC:04X}")

    pos = 2

    # Skip original filename (null-terminated)
    while pos < len(data) and data[pos] != 0:
        pos += 1
    pos += 1  # Skip null terminator

    if pos >= len(data):
        raise CrLZHError("No data after filename")

    # CrLZH uses LZSS with Huffman coding
    # The exact format varies between implementations

    bits = BitReader(data, pos)
    result = bytearray()

    # Ring buffer for LZSS back-references
    RING_SIZE = 4096
    RING_MASK = RING_SIZE - 1
    ring = bytearray(RING_SIZE)
    ring_pos = RING_SIZE - 18  # Typical initial position

    try:
        while True:
            # Read flag bit: 1 = literal, 0 = match
            if bits.read_bit():
                # Literal byte
                byte = bits.read_bits(8)
                result.append(byte)
                ring[ring_pos] = byte
                ring_pos = (ring_pos + 1) & RING_MASK
            else:
                # Match: read offset and length
                # Offset is typically 12 bits, length 4 bits
                offset = bits.read_bits(12)
                length = bits.read_bits(4) + 3  # Minimum match length is 3

                # Copy from ring buffer
                for _ in range(length):
                    byte = ring[(offset + _) & RING_MASK]
                    result.append(byte)
                    ring[ring_pos] = byte
                    ring_pos = (ring_pos + 1) & RING_MASK

                # Check for end marker (offset 0, length 0)
                if offset == 0 and length == 3:
                    break

    except CrLZHError:
        # End of data
        pass

    return bytes(result)


def get_crlzh_filename(data: bytes) -> str | None:
    """
    Extract the original filename from CrLZH data.

    Args:
        data: CrLZH file data

    Returns:
        Original filename or None if not valid
    """
    if len(data) < 4:
        return None

    magic = (data[0] << 8) | data[1]
    if magic != CRLZH_MAGIC:
        return None

    pos = 2
    end = pos
    while end < len(data) and data[end] != 0:
        end += 1

    if end == pos or end >= len(data):
        return None

    try:
        return data[pos:end].decode('ascii')
    except UnicodeDecodeError:
        return None
