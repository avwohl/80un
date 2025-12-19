"""
CrLZH decompression for CP/M files.

CrLZH uses LZSS compression with adaptive Huffman coding, similar to
LHA's lh1 method. Devised by Roger Warren for CP/M circa 1989.

File format:
- Magic: 0x76 0xFD
- Original filename (null-terminated, may include BBS stamp)
- 4 bytes: padding/version info
- Compressed data using LZSS + adaptive Huffman

Key parameters:
- 315 symbols: 256 literals + 1 stop code + 58 lengths (3-60)
- Symbol 256 = stop code
- Symbols 257-314 = match lengths (3-60 bytes)
- Adaptive Huffman tree with frequency-based updates
- 256-byte sliding window with 8-bit position encoding

EXPERIMENTAL: CrLZH v2.0 uses a position encoding algorithm that differs
from the standard LZHUF implementation. The original CrLZH source code
(circa 1989-1991) is not fully accessible, and the exact algorithm is
not documented. This implementation correctly handles the Huffman coding
but may produce incorrect output for files with match references.

For reliable decompression, use the original UCRLZH20.COM via a CP/M
emulator (available on the Walnut Creek CP/M CD-ROM).
"""

CRLZH_MAGIC = 0x76FD

# Buffer size for sliding window
# CrLZH v2.0 documentation mentions "file limit changed to 256"
N = 256
N_MASK = N - 1

# Lookahead buffer size (max match length)
F = 60

# Minimum match length to encode as reference
THRESHOLD = 2

# Number of character codes: 256 literals + 1 stop + 58 lengths = 315
N_CHAR = 256 + 1 + (F - THRESHOLD)  # 315

# Huffman tree size
T = N_CHAR * 2 - 1  # 629

# Root of Huffman tree
R = T - 1  # 628

# Maximum frequency before tree reconstruction
MAX_FREQ = 0x8000


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


def decode_position(bits: BitReader) -> int:
    """
    Decode position for CrLZH.

    With N=256, uses simple 8-bit position encoding.
    """
    return bits.get_byte()


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

    # Skip null terminator
    pos += 1

    # Skip 4 bytes of padding/version info if present
    if pos + 4 <= len(data):
        # Check if this looks like padding (spaces or low bytes)
        if all(b < 0x20 or b == 0x20 for b in data[pos:pos + 4]):
            pos += 4

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

    # Initialize
    bits = BitReader(data, data_offset)
    tree = HuffmanTree()
    result = bytearray()

    # Sliding window buffer, initialized to spaces (like CP/M)
    text_buf = bytearray(b' ' * N)
    r = N - F  # Current position in buffer

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
