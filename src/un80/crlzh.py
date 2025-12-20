"""
CrLZH decompression for CP/M files.

CrLZH uses LZSS compression with adaptive Huffman coding, derived from
LHA's lh1 method. Devised by Roger Warren for CP/M circa 1989.

File format:
- Magic: 0x76 0xFD
- Original filename (null-terminated, may include BBS stamp)
- Version/parameter bytes (vary by encoder version)
- Compressed data using LZSS + adaptive Huffman

Key parameters (from UCRLZH20.COM disassembly):
- N = 2048 byte sliding window (11-bit positions)
- F = 60 max match length
- THRESHOLD = 2 (minimum match length is 3)
- N_CHAR = 315: 256 literals + 1 stop code (256) + 58 lengths (257-314)
- Match lengths 3-60 bytes (symbol - 254 = length)
- Adaptive Huffman tree with frequency-based updates
- MAX_FREQ = 0x8000 triggers tree reconstruction
- Position encoding uses d_code/d_len tables (standard LZHUF style)

References:
- LZHUF.C by Haruyasu Yoshizaki (1988)
- UCRLZH20.COM (CP/M decompressor binary, disassembled for verification)
- CrLZH documentation: http://fileformats.archiveteam.org/wiki/CrLZH
"""

CRLZH_MAGIC = 0x76FD

# Buffer size for sliding window
# CrLZH v2.0 uses 2048-byte window with 11-bit position encoding
# (Verified from UCRLZH20.COM: buffer mask is 0x7FF via AND 07H on H register)
N = 2048
N_MASK = N - 1  # 0x7FF = 2047

# Lookahead buffer size (max match length)
F = 60

# Minimum match length to encode as reference
THRESHOLD = 2

# Number of character codes: 256 literals + 1 stop + 58 lengths = 315
# (CrLZH adds a stop code that LZHUF doesn't have)
N_CHAR = 256 + 1 + (F - THRESHOLD)  # 315

# Huffman tree size
T = N_CHAR * 2 - 1  # 629

# Root of Huffman tree
R = T - 1  # 628

# Maximum frequency before tree reconstruction
MAX_FREQ = 0x8000

# Position decoding tables from LZHUF.C
# d_code: maps byte value to upper bits of position
D_CODE = [
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
    0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
    0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
    0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
    0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03,
    0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03,
    0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04,
    0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
    0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06,
    0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08,
    0x09, 0x09, 0x09, 0x09, 0x09, 0x09, 0x09, 0x09,
    0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A,
    0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B,
    0x0C, 0x0C, 0x0C, 0x0C, 0x0D, 0x0D, 0x0D, 0x0D,
    0x0E, 0x0E, 0x0E, 0x0E, 0x0F, 0x0F, 0x0F, 0x0F,
    0x10, 0x10, 0x10, 0x10, 0x11, 0x11, 0x11, 0x11,
    0x12, 0x12, 0x12, 0x12, 0x13, 0x13, 0x13, 0x13,
    0x14, 0x14, 0x14, 0x14, 0x15, 0x15, 0x15, 0x15,
    0x16, 0x16, 0x16, 0x16, 0x17, 0x17, 0x17, 0x17,
    0x18, 0x18, 0x19, 0x19, 0x1A, 0x1A, 0x1B, 0x1B,
    0x1C, 0x1C, 0x1D, 0x1D, 0x1E, 0x1E, 0x1F, 0x1F,
    0x20, 0x20, 0x21, 0x21, 0x22, 0x22, 0x23, 0x23,
    0x24, 0x24, 0x25, 0x25, 0x26, 0x26, 0x27, 0x27,
    0x28, 0x28, 0x29, 0x29, 0x2A, 0x2A, 0x2B, 0x2B,
    0x2C, 0x2C, 0x2D, 0x2D, 0x2E, 0x2E, 0x2F, 0x2F,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
    0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F,
]

# d_len: number of bits used to encode this position value
D_LEN = [
    0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03,
    0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03,
    0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03,
    0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03,
    0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04,
    0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04,
    0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04,
    0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04,
    0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04,
    0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04,
    0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
    0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
    0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
    0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
    0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
    0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
    0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
    0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
    0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06,
    0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06,
    0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06,
    0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06,
    0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06,
    0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06,
    0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08,
    0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08,
]


class CrLZHError(Exception):
    """Error during CrLZH decompression."""


class BitReader:
    """Read bits from a byte stream, MSB first."""

    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.pos = offset
        self.buf = 0
        self.buf_len = 0

    def get_bit(self) -> int:
        """Get one bit."""
        while self.buf_len <= 8:
            if self.pos < len(self.data):
                byte = self.data[self.pos]
                self.pos += 1
            else:
                byte = 0
            self.buf |= byte << (8 - self.buf_len)
            self.buf_len += 8

        result = 1 if self.buf & 0x8000 else 0
        self.buf = (self.buf << 1) & 0xFFFF
        self.buf_len -= 1
        return result

    def get_bits(self, count: int) -> int:
        """Get multiple bits MSB first."""
        result = 0
        for _ in range(count):
            result = (result << 1) | self.get_bit()
        return result

    def get_byte(self) -> int:
        """Get 8 bits as a byte."""
        return self.get_bits(8)


def decode_position_v1(bits: BitReader) -> int:
    """
    Decode position using LZHUF d_code/d_len tables (for version < 0x20).
    """
    # Read first byte
    i = bits.get_byte()

    # Upper 6 bits from d_code table
    c = D_CODE[i] << 6

    # Number of additional bits to read
    j = D_LEN[i] - 2

    # Read lower bits, shifting i to accumulate them
    while j > 0:
        j -= 1
        i = (i << 1) | bits.get_bit()

    # Combine upper and lower 6 bits
    return c | (i & 0x3F)


def decode_position_v2(bits: BitReader) -> int:
    """
    Decode position for CrLZH v2.0 format (version >= 0x20).

    v2.0 uses d_code/d_len tables like v1, but with different parameters:
    - Read (d_len - 3) extra bits (vs d_len - 2 for v1)
    - Position = (d_code << 5) | (lower 5 bits) (vs << 6 and 6 bits for v1)

    This gives 11-bit positions (0-2047) for the 2048-byte sliding window.
    """
    # Read initial 8-bit value
    byte_val = bits.get_byte()

    # Look up d_code and d_len
    d_code = D_CODE[byte_val]
    d_len = D_LEN[byte_val]

    # Number of extra bits to read: d_len - 3 (minimum 0)
    extra_count = d_len - 3

    # Accumulate extra bits by shifting and adding
    # Start with original byte, shift left for each extra bit read
    accum = byte_val
    for _ in range(extra_count):
        accum = (accum << 1) | bits.get_bit()

    # Final position: d_code in upper bits, accumulated lower 5 bits
    return (d_code << 5) | (accum & 0x1F)


class HuffmanTree:
    """Adaptive Huffman tree for CrLZH decompression."""

    def __init__(self):
        # Frequency table for each node
        self.freq = [0] * (T + 1)

        # Parent pointers: prnt[T..T+N_CHAR-1] map codes to leaf positions
        self.prnt = [0] * (T + N_CHAR)

        # Child pointers: son[i] and son[i]+1 are children of node i
        self.son = [0] * T

        self._init_tree()

    def _init_tree(self):
        """Initialize tree with uniform frequencies."""
        # Initialize leaf nodes
        for i in range(N_CHAR):
            self.freq[i] = 1
            self.son[i] = i + T
            self.prnt[i + T] = i

        # Build internal nodes
        i = 0
        j = N_CHAR
        while j <= R:
            self.freq[j] = self.freq[i] + self.freq[i + 1]
            self.son[j] = i
            self.prnt[i] = self.prnt[i + 1] = j
            i += 2
            j += 1

        # Sentinel
        self.freq[T] = 0xFFFF
        self.prnt[R] = 0

    def _reconst(self):
        """Reconstruct tree when frequency counter saturates."""
        # Collect leaf nodes and halve frequencies
        j = 0
        for i in range(T):
            if self.son[i] >= T:
                self.freq[j] = (self.freq[i] + 1) // 2
                self.son[j] = self.son[i]
                j += 1

        # Rebuild tree by connecting sons
        i = 0
        j = N_CHAR
        while j < T:
            k = i + 1
            f = self.freq[j] = self.freq[i] + self.freq[k]

            # Find insertion point
            k = j - 1
            while f < self.freq[k]:
                k -= 1
            k += 1

            # Shift arrays
            l = j - k
            self.freq[k + 1:j + 1] = self.freq[k:j]
            self.freq[k] = f
            self.son[k + 1:j + 1] = self.son[k:j]
            self.son[k] = i

            i += 2
            j += 1

        # Reconnect parent pointers
        for i in range(T):
            k = self.son[i]
            if k >= T:
                self.prnt[k] = i
            else:
                self.prnt[k] = self.prnt[k + 1] = i

    def update(self, c: int):
        """Increment frequency of given code and update tree."""
        if self.freq[R] == MAX_FREQ:
            self._reconst()

        c = self.prnt[c + T]
        while True:
            self.freq[c] += 1
            k = self.freq[c]

            # Check if order is disturbed
            l = c + 1
            if k > self.freq[l]:
                # Find node to swap with
                while k > self.freq[l + 1]:
                    l += 1

                # Swap frequencies
                self.freq[c] = self.freq[l]
                self.freq[l] = k

                # Swap children and update parent pointers
                i = self.son[c]
                self.prnt[i] = l
                if i < T:
                    self.prnt[i + 1] = l

                j = self.son[l]
                self.son[l] = i
                self.prnt[j] = c
                if j < T:
                    self.prnt[j + 1] = c
                self.son[c] = j

                c = l

            c = self.prnt[c]
            if c == 0:
                break

    def decode_char(self, bits: BitReader) -> int:
        """Decode one character from bit stream."""
        c = self.son[R]

        # Traverse from root to leaf
        while c < T:
            c += bits.get_bit()
            c = self.son[c]

        c -= T
        self.update(c)
        return c


def parse_header(data: bytes) -> tuple[str | None, int]:
    """
    Parse CrLZH header and return (filename, data_offset).

    Header format:
    - 0x76 0xFD magic
    - Filename (null-terminated, may include BBS stamp)
    - 4 bytes padding/version
    - Compressed data
    """
    if len(data) < 4:
        raise CrLZHError("Data too short")

    # Check magic
    if data[0] != 0x76 or data[1] != 0xFD:
        raise CrLZHError(f"Invalid magic: 0x{data[0]:02X}{data[1]:02X}")

    # Find null terminator for filename
    pos = 2
    filename_end = pos
    while pos < len(data) and data[pos] != 0:
        # Check for high bit marking end of original filename
        if data[pos] & 0x80:
            if filename_end == 2:  # First high-bit char is end of filename
                filename_end = pos + 1
        pos += 1

    if pos >= len(data):
        raise CrLZHError("No null terminator in header")

    # Extract filename (strip BBS stamp if present)
    filename_bytes = data[2:filename_end] if filename_end > 2 else data[2:pos]

    # Clear high bit on last character if set
    if filename_bytes and filename_bytes[-1] & 0x80:
        filename_bytes = filename_bytes[:-1] + bytes([filename_bytes[-1] & 0x7F])

    try:
        filename = filename_bytes.decode('ascii').strip()
        # Remove any BBS stamp in brackets
        if '[' in filename:
            filename = filename[:filename.index('[')].strip()
    except (UnicodeDecodeError, ValueError):
        filename = None

    # Skip null terminator - data stream starts immediately after
    # (The first 4 bytes are version/mode info read by the decompressor)
    pos += 1

    return filename, pos


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
    filename, data_offset = parse_header(data)

    # Initialize bit reader
    bits = BitReader(data, data_offset)

    # Read 4 header bytes (version/mode info)
    # First two bytes determine decoding mode (checked against 0x20, 0x21)
    # UCRLZH20.COM uses these for self-modifying code to select position encoding
    version1 = bits.get_byte()
    version2 = bits.get_byte()

    # Check version (UCRLZH20 rejects if >= 0x21)
    if version1 >= 0x21:
        raise CrLZHError(f"Unsupported version: {version1:02X}")

    # Select position decoder based on version
    # Version >= 0x20: simple 8-bit positions (v2.0 format)
    # Version < 0x20: d_code/d_len tables (v1.x format)
    use_v2_position = version1 >= 0x20
    decode_position = decode_position_v2 if use_v2_position else decode_position_v1

    # Read two more header bytes (consumed but not used for version check)
    bits.get_byte()
    bits.get_byte()

    # Initialize tree and buffers
    tree = HuffmanTree()
    result = bytearray()

    # Sliding window buffer, initialized to spaces (like CP/M)
    text_buf = bytearray(b' ' * N)
    r = N - F  # Current position in buffer (N - F = 1988)

    # Main decode loop
    while True:
        c = tree.decode_char(bits)

        if c < 256:
            # Literal byte
            result.append(c)
            text_buf[r] = c
            r = (r + 1) & N_MASK

        elif c == 256:
            # Stop code
            break

        else:
            # Match reference: c encodes length
            # Length = c - 256 + THRESHOLD + 1 = c - 254
            # (symbols 257-314 encode lengths 3-60)
            match_len = c - 254

            # Decode position using LZHUF-style encoding
            pos = decode_position(bits)

            # Calculate source position in ring buffer
            i = (r - pos - 1) & N_MASK

            # Copy from buffer
            for _ in range(match_len):
                c = text_buf[i]
                result.append(c)
                text_buf[r] = c
                r = (r + 1) & N_MASK
                i = (i + 1) & N_MASK

    return bytes(result)


def get_crlzh_filename(data: bytes) -> str | None:
    """
    Extract the original filename from CrLZH data.

    Args:
        data: CrLZH file data

    Returns:
        Original filename or None if not valid
    """
    try:
        filename, _ = parse_header(data)
        return filename if filename else None
    except CrLZHError:
        return None


def get_crlzh_info(data: bytes) -> dict | None:
    """
    Get detailed info about a CrLZH file.

    Args:
        data: CrLZH file data

    Returns:
        Dictionary with version info, or None if not valid
    """
    try:
        filename, data_offset = parse_header(data)

        # Read version bytes from data stream
        if data_offset + 2 > len(data):
            return None

        version1 = data[data_offset]
        version2 = data[data_offset + 1]

        is_v2 = version1 >= 0x20
        version_str = "2.0" if is_v2 else f"1.x (0x{version1:02X})"

        return {
            'filename': filename,
            'version': version1,
            'version_str': version_str,
            'position_bits': 5 if is_v2 else 6,
            'description': f"V{version_str} ({'11-bit' if is_v2 else '12-bit'} positions)",
        }
    except CrLZHError:
        return None
