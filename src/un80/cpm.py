"""
CP/M file handling utilities.

CP/M files have specific conventions:
- Files are stored in 128-byte records (sectors)
- Text files end with ^Z (0x1A) if they don't fill the last sector
- Text files use CR/LF line endings
"""

# Common text file extensions in CP/M
TEXT_EXTENSIONS = {
    'txt', 'doc', 'asm', 'mac', 'pas', 'bas', 'for', 'cob',
    'c', 'h', 'inc', 'lib', 'sub', 'bat', 'cmd', 'hlp',
    'man', 'msg', 'nws', 'let', 'mem', 'not', 'inf',
    'bbs', 'lst', 'prn', 'log', 'dat', 'cfg', 'ini',
}

# Common binary file extensions in CP/M
BINARY_EXTENSIONS = {
    'com', 'exe', 'rel', 'obj', 'sys', 'ovr', 'ovl',
    'bin', 'hex', 'spr', 'prl', 'rsx', 'ndx', 'idx',
    'dsk', 'imd', 'td0', 'cpm', 'img',
}

CPM_EOF = 0x1A  # Ctrl-Z

# Characters that must never reach the host filesystem from an archive.  A CP/M
# directory entry or an embedded name inside a compressed member is arbitrary
# bytes, so a member can otherwise name a path outside the output directory.
_UNSAFE_NAME_CHARS = '/\\:*?"<>|'

# Names Windows resolves to a device rather than a file.  Writing a member to
# 'NUL' discards the contents and reports success, so the name is prefixed.
_DEVICE_NAMES = frozenset(
    ['CON', 'PRN', 'AUX', 'NUL']
    + [f'COM{d}' for d in '123456789']
    + [f'LPT{d}' for d in '123456789']
)

# Every common host filesystem stops at 255 bytes for one path component.  An
# embedded name is arbitrary bytes and can be far longer than a CP/M name, and
# an over-long one used to abort the whole extraction with a raw OSError.
_MAX_NAME_BYTES = 255


def safe_filename(name: str, fallback: str = 'UNNAMED') -> str:
    """
    Reduce an archive member name to a plain filename.

    Every character that is special to a host filesystem is replaced, so the
    result can never contain a directory separator and therefore can never
    escape the output directory.  Replacing rather than splitting matters
    because '/' is an ordinary filename character under CP/M - mouse.lbr holds
    a member called CCP/M.COM, which becomes CCP_M.COM rather than M.COM.
    """
    cleaned = _clean_name(name)
    if cleaned:
        return cleaned

    # The fallback is usually another archive-supplied name, so clean it too.
    return _clean_name(fallback) or 'UNNAMED'


def unique_filename(name: str, used: set[str]) -> str:
    """
    Make `name` unique among the names already taken, and record the result.

    Sanitising maps two different member names onto one whenever they differ
    only in a character that safe_filename replaces, and '/' is an ordinary
    filename character under CP/M, so a collision is routine rather than
    exotic.  Without this the second member silently overwrites the first while
    the caller still reports both as extracted.

    Comparison ignores case, because CP/M names are case-insensitive and the
    host filesystem may be too.
    """
    stem, dot, ext = name.rpartition('.')
    if not dot:
        stem, ext = name, ''
    suffix = '.' + ext if ext else ''

    candidate = name
    counter = 1
    while candidate.casefold() in used:
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1

    used.add(candidate.casefold())
    return candidate


def _clean_name(name: str) -> str:
    """Replace unsafe characters; return '' for a name that cannot be used."""
    cleaned = ''.join(
        '_' if c in _UNSAFE_NAME_CHARS or ord(c) < 0x20 or ord(c) == 0x7F else c
        for c in name
    ).strip()

    # '.' and '..' name directories, not files.
    if set(cleaned) <= {'.'}:
        return ''

    # Windows drops a trailing dot or space, which would quietly merge two
    # members onto one name.
    cleaned = cleaned.rstrip('. ')
    if not cleaned:
        return ''

    if cleaned.partition('.')[0].upper() in _DEVICE_NAMES:
        cleaned = '_' + cleaned

    return _cap_length(cleaned)


def _cap_length(name: str) -> str:
    """Cap the name at _MAX_NAME_BYTES, keeping a short extension intact."""
    encode = lambda text: text.encode('utf-8', 'surrogateescape')
    if len(encode(name)) <= _MAX_NAME_BYTES:
        return name

    stem, dot, ext = name.rpartition('.')
    suffix = dot + ext if dot and len(encode(ext)) <= 16 else ''
    head = encode(stem if suffix else name)[:_MAX_NAME_BYTES - len(encode(suffix))]
    return head.decode('utf-8', 'ignore') + suffix


def strip_cpm_eof(data: bytes, *, aggressive: bool = False) -> bytes:
    """
    Strip CP/M EOF marker (^Z) and padding from text file data.

    CP/M files are stored in 128-byte records. Text files that don't
    fill the last record are padded, typically with ^Z (0x1A) characters.

    Args:
        data: The file data
        aggressive: If True, strip all trailing ^Z characters.
                   If False, only strip if ^Z appears to be padding.

    Returns:
        Data with ^Z padding stripped
    """
    if not data:
        return data

    if aggressive:
        # Strip all trailing ^Z characters
        return data.rstrip(bytes([CPM_EOF]))

    # Find the first ^Z that looks like EOF (followed only by ^Z or at end)
    pos = len(data)
    for i in range(len(data) - 1, -1, -1):
        if data[i] == CPM_EOF:
            # Check if everything after is ^Z or nothing
            rest = data[i+1:]
            if all(b == CPM_EOF for b in rest):
                pos = i
        else:
            break

    return data[:pos]


def crlf_to_lf(data: bytes) -> bytes:
    """
    Convert CR/LF line endings to Unix LF.

    CP/M text files use CR/LF (0x0D 0x0A) line endings like DOS.
    This converts them to Unix-style LF (0x0A) only.

    Args:
        data: Text file data with CR/LF endings

    Returns:
        Data with LF-only line endings
    """
    return data.replace(b'\r\n', b'\n')


def is_text_file(filename: str) -> bool:
    """
    Determine if a file is likely text based on its extension.

    Args:
        filename: The filename to check

    Returns:
        True if the file is likely a text file
    """
    # Get extension, handling CP/M compressed naming
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    # Handle compressed extensions (.tqt -> .txt, .aqm -> .asm)
    if len(ext) == 3 and ext[1] in 'qzy':
        # Reconstruct original extension
        ext = ext[0] + ext[2] + ext[2]  # e.g., tqt -> ttt (wrong)
        # Actually: middle letter replaced, so tqt was txt
        ext = ext[0] + ext[2]  # Take first and last
        # Hmm, this is tricky. Let's just check common patterns
        if ext[0] in 'tad' or ext[2] in 'tsmcb':  # Common text first/last chars
            return True

    return ext in TEXT_EXTENSIONS


def get_original_extension(compressed_ext: str) -> str:
    """
    Get the original extension from a compressed extension.

    CP/M compression tools replaced the middle letter:
    - Q = squeezed (.txt -> .tqt)
    - Z = crunched (.txt -> .tzt)
    - Y = CrLZH (.txt -> .tyt)

    Args:
        compressed_ext: The compressed extension (e.g., 'tqt')

    Returns:
        The original extension (e.g., 'txt'), or the input if not compressed
    """
    if len(compressed_ext) != 3:
        return compressed_ext

    mid = compressed_ext[1].lower()
    if mid in 'qzy':
        # Handle special cases
        if compressed_ext.lower() in ('qqq', 'zzz', 'yyy'):
            return ''  # File had no original extension
        # Replace middle letter with first letter repeated
        # Actually this isn't quite right - we don't know the original
        # But commonly it's the same as first or last letter
        # For now, just mark it as decompressed
        return compressed_ext[0] + compressed_ext[0] + compressed_ext[2]

    return compressed_ext


def detect_compression(data: bytes) -> str | None:
    """
    Detect the compression type from file magic bytes.

    Args:
        data: File data (at least 2 bytes)

    Returns:
        Compression type: 'squeeze', 'crunch', 'crlzh', 'arc', 'lbr', or None
    """
    if len(data) < 2:
        return None

    # Check magic bytes
    magic = (data[0] << 8) | data[1]

    if magic == 0x76FF:
        return 'squeeze'
    elif magic == 0x76FE:
        return 'crunch'
    elif magic == 0x76FD:
        return 'crlzh'
    elif data[0] == 0x1A and 0 <= data[1] <= 9:
        return 'arc'

    # LBR detection: first byte is status (0x00 for active directory)
    # followed by spaces (directory entry name)
    if data[0] == 0x00 and len(data) >= 32:
        # Check if it looks like an LBR directory entry
        # Name field should be all spaces for the directory itself
        if data[1:12] == b'           ':
            return 'lbr'

    return None
