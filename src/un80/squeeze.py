"""
Squeeze decompression for CP/M files.

Squeeze uses Huffman coding combined with run-length encoding (RLE).
It was devised by Richard Greenlaw circa 1981.

File format:
- Magic: 0x76 0xFF
- Original filename: null-terminated string
- Checksum: 2 bytes (little-endian, sum of decoded bytes)
- Huffman tree node count: 2 bytes (little-endian, signed)
- Huffman tree: array of node pairs (2 bytes each, little-endian signed)
- Compressed data: bit stream

Huffman tree:
- Each node has two children (left and right)
- Positive values are child node indices
- Negative values are leaf values (-1 = value 0, -2 = value 1, etc.)
- Special value -1 (as leaf, not -2 for byte 0) can mean EOF

RLE encoding (RLE90):
- 0x90 is the escape byte
- 0x90 0x00 = literal 0x90
- 0x90 N = repeat previous byte N times (N > 0)
"""

import struct
from typing import Iterator

SQUEEZE_MAGIC = 0x76FF
RLE_MARKER = 0x90
EOF_VALUE = 256  # Special EOF marker in Huffman tree


class SqueezeError(Exception):
    """Error during squeeze decompression."""


class BitReader:
    """Read individual bits from a byte stream, LSB first."""

    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.pos = offset
        self.bit_pos = 8  # Force initial read (like USQ's bpos=99)
        self.current_byte = 0

    def read_bit(self) -> int:
        """Read a single bit LSB-first, returns 0 or 1."""
        if self.bit_pos >= 8:
            if self.pos >= len(self.data):
                raise SqueezeError("Unexpected end of data")
            self.current_byte = self.data[self.pos]
            self.pos += 1
            self.bit_pos = 0

        bit = (self.current_byte >> self.bit_pos) & 1
        self.bit_pos += 1
        return bit


class HuffmanTree:
    """Huffman tree for squeeze decompression."""

    def __init__(self, nodes: list[tuple[int, int]]):
        """
        Initialize with node array.

        Args:
            nodes: List of (left, right) child indices.
                   Positive = node index, negative = -(value + 1)
        """
        self.nodes = nodes

    def decode_symbol(self, bits: BitReader) -> int:
        """
        Decode one symbol from the bit stream.

        Returns:
            The decoded byte value (0-255) or EOF_VALUE (256)
        """
        if not self.nodes:
            raise SqueezeError("Empty Huffman tree")

        node_idx = 0

        while True:
            if node_idx < 0 or node_idx >= len(self.nodes):
                raise SqueezeError(f"Invalid node index: {node_idx}")

            left, right = self.nodes[node_idx]
            bit = bits.read_bit()

            child = right if bit else left

            if child < 0:
                # Leaf node: value is -(child + 1)
                value = -(child + 1)
                return value

            # Internal node: continue traversal
            node_idx = child


def decode_rle(data: Iterator[int]) -> bytes:
    """
    Decode RLE90-encoded data.

    Args:
        data: Iterator of byte values

    Returns:
        Decoded bytes
    """
    result = bytearray()
    prev_byte = 0

    for byte in data:
        if byte == RLE_MARKER:
            try:
                count = next(data)
            except StopIteration:
                # Trailing RLE marker, treat as literal
                result.append(RLE_MARKER)
                break

            if count == 0:
                # Literal 0x90
                result.append(RLE_MARKER)
                prev_byte = RLE_MARKER
            else:
                # Repeat previous byte count times
                result.extend([prev_byte] * count)
        else:
            result.append(byte)
            prev_byte = byte

    return bytes(result)


def unsqueeze(data: bytes) -> bytes:
    """
    Decompress squeezed data.

    Args:
        data: Squeezed file data (including magic header)

    Returns:
        Decompressed data

    Raises:
        SqueezeError: If decompression fails
    """
    if len(data) < 4:
        raise SqueezeError("Data too short")

    # Check magic
    magic = (data[0] << 8) | data[1]
    if magic != SQUEEZE_MAGIC:
        raise SqueezeError(f"Invalid magic: 0x{magic:04X}, expected 0x{SQUEEZE_MAGIC:04X}")

    pos = 2

    # Read checksum (comes BEFORE filename per original USQ format)
    if pos + 2 > len(data):
        raise SqueezeError("Data too short for checksum")
    _ = struct.unpack('<H', data[pos:pos+2])[0]  # checksum (unused)
    pos += 2

    # Skip original filename (null-terminated)
    while pos < len(data) and data[pos] != 0:
        pos += 1
    pos += 1  # Skip null terminator

    if pos + 2 > len(data):
        raise SqueezeError("Data too short for header")

    # Read node count (signed 16-bit)
    node_count = struct.unpack('<h', data[pos:pos+2])[0]
    pos += 2

    if node_count < 0:
        raise SqueezeError(f"Invalid node count: {node_count}")

    # Read Huffman tree nodes
    nodes = []
    for _ in range(node_count):
        if pos + 4 > len(data):
            raise SqueezeError("Data too short for Huffman tree")
        left, right = struct.unpack('<hh', data[pos:pos+4])
        nodes.append((left, right))
        pos += 4

    # Build tree and decode
    tree = HuffmanTree(nodes)
    bits = BitReader(data, pos)

    # Decode Huffman symbols
    decoded_symbols = []
    try:
        while True:
            symbol = tree.decode_symbol(bits)
            if symbol == EOF_VALUE:
                break
            if symbol > 255:
                raise SqueezeError(f"Invalid symbol: {symbol}")
            decoded_symbols.append(symbol)
    except SqueezeError:
        # End of data, might be okay
        pass

    # Decode RLE
    result = decode_rle(iter(decoded_symbols))

    return result


def get_squeezed_filename(data: bytes) -> str | None:
    """
    Extract the original filename from squeezed data.

    Args:
        data: Squeezed file data

    Returns:
        Original filename or None if not valid
    """
    if len(data) < 6:  # magic + checksum + at least 1 char + null
        return None

    magic = (data[0] << 8) | data[1]
    if magic != SQUEEZE_MAGIC:
        return None

    # Skip checksum (2 bytes after magic)
    pos = 4

    # Find null terminator for filename
    end = pos
    while end < len(data) and data[end] != 0:
        end += 1

    if end == pos or end >= len(data):
        return None

    try:
        return data[pos:end].decode('ascii')
    except UnicodeDecodeError:
        return None
