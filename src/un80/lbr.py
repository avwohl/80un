"""
LBR (Library) archive format support.

LBR is an archive format (like tar) used on CP/M. It stores files
without compression, but individual members are often squeezed or crunched.

Format:
- Files are organized into 128-byte sectors
- First sector(s) contain the directory
- Each directory entry is 32 bytes
- First entry is the directory itself (name = spaces)

Directory entry format (32 bytes):
  Offset  Size  Description
  0       1     Status: 0x00=active, 0xFE=deleted, 0xFF=unused
  1       8     Filename (space-padded, high bit may have attributes)
  9       3     Extension (space-padded, high bit may have attributes)
  12      2     Index: first sector of member (little-endian)
  14      2     Length: size in sectors (little-endian)
  16      2     CRC-16 (XMODEM style)
  18      2     Creation date (days since Dec 31, 1977)
  20      2     Last change date
  22      2     Creation time (DOS format)
  24      2     Last change time
  26      1     Pad count: trailing pad bytes in final sector (0-127)
  27      5     Reserved (zeros)
"""

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

SECTOR_SIZE = 128
ENTRY_SIZE = 32

STATUS_ACTIVE = 0x00
STATUS_DELETED = 0xFE
STATUS_UNUSED = 0xFF


@dataclass
class LbrEntry:
    """A single entry in an LBR archive."""
    status: int
    name: str
    ext: str
    index: int  # First sector
    length: int  # Length in sectors
    crc: int
    creation_date: int
    change_date: int
    creation_time: int
    change_time: int
    pad_count: int

    @property
    def filename(self) -> str:
        """Full filename with extension."""
        if self.ext.strip():
            return f"{self.name.strip()}.{self.ext.strip()}"
        return self.name.strip()

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE

    @property
    def is_deleted(self) -> bool:
        return self.status == STATUS_DELETED

    @property
    def is_directory(self) -> bool:
        """Check if this is the directory entry itself."""
        return self.name.strip() == '' and self.ext.strip() == '' and self.index == 0

    @property
    def data_size(self) -> int:
        """Actual data size in bytes (accounting for padding)."""
        if self.length == 0:
            return 0
        return (self.length * SECTOR_SIZE) - self.pad_count


def parse_entry(data: bytes) -> LbrEntry:
    """Parse a 32-byte directory entry."""
    if len(data) < ENTRY_SIZE:
        raise ValueError(f"Entry too short: {len(data)} bytes")

    status = data[0]

    # Extract name and extension, masking high bits (CP/M attributes)
    name = ''.join(chr(b & 0x7F) for b in data[1:9])
    ext = ''.join(chr(b & 0x7F) for b in data[9:12])

    # Parse numeric fields (little-endian)
    index, length, crc = struct.unpack('<HHH', data[12:18])
    creation_date, change_date = struct.unpack('<HH', data[18:22])
    creation_time, change_time = struct.unpack('<HH', data[22:26])
    pad_count = data[26]

    return LbrEntry(
        status=status,
        name=name,
        ext=ext,
        index=index,
        length=length,
        crc=crc,
        creation_date=creation_date,
        change_date=change_date,
        creation_time=creation_time,
        change_time=change_time,
        pad_count=pad_count,
    )


def read_directory(f: BinaryIO) -> list[LbrEntry]:
    """
    Read the LBR directory from an open file.

    Args:
        f: Open file handle positioned at start

    Returns:
        List of directory entries (excluding the directory entry itself)
    """
    entries = []

    # Read first entry to get directory size
    first_sector = f.read(SECTOR_SIZE)
    if len(first_sector) < ENTRY_SIZE:
        raise ValueError("File too small to be an LBR")

    dir_entry = parse_entry(first_sector[:ENTRY_SIZE])
    if not dir_entry.is_directory:
        raise ValueError("First entry is not a directory entry")

    dir_sectors = dir_entry.length
    entries_per_sector = SECTOR_SIZE // ENTRY_SIZE

    # Parse remaining entries in first sector
    for i in range(1, entries_per_sector):
        offset = i * ENTRY_SIZE
        if offset + ENTRY_SIZE <= len(first_sector):
            entry = parse_entry(first_sector[offset:offset + ENTRY_SIZE])
            if entry.status == STATUS_UNUSED:
                break
            if entry.is_active:
                entries.append(entry)

    # Read remaining directory sectors
    for _ in range(1, dir_sectors):
        sector = f.read(SECTOR_SIZE)
        if len(sector) < SECTOR_SIZE:
            break

        for i in range(entries_per_sector):
            offset = i * ENTRY_SIZE
            entry = parse_entry(sector[offset:offset + ENTRY_SIZE])
            if entry.status == STATUS_UNUSED:
                return entries
            if entry.is_active:
                entries.append(entry)

    return entries


def read_member(f: BinaryIO, entry: LbrEntry) -> bytes:
    """
    Read a member's data from the archive.

    Args:
        f: Open file handle
        entry: The directory entry for the member

    Returns:
        The member's data
    """
    f.seek(entry.index * SECTOR_SIZE)
    data = f.read(entry.length * SECTOR_SIZE)

    # Trim padding if pad_count is set
    if entry.pad_count > 0 and len(data) >= entry.pad_count:
        data = data[:-entry.pad_count]

    return data


def list_lbr(path: str | Path) -> list[LbrEntry]:
    """
    List contents of an LBR archive.

    Args:
        path: Path to the LBR file

    Returns:
        List of entries in the archive
    """
    with open(path, 'rb') as f:
        return read_directory(f)


def extract_lbr(
    path: str | Path,
    output_dir: str | Path | None = None,
    *,
    decompress: bool = True,
    convert_text: bool = False,
) -> list[tuple[str, bytes]]:
    """
    Extract all files from an LBR archive.

    Args:
        path: Path to the LBR file
        output_dir: Directory to extract to. If None, returns data in memory.
        decompress: Whether to decompress squeezed/crunched members
        convert_text: Whether to convert text files (strip ^Z, CR/LF to LF)

    Returns:
        List of (filename, data) tuples for extracted files
    """
    from . import unsqueeze, uncrunch, uncrlzh
    from .cpm import strip_cpm_eof, crlf_to_lf, is_text_file, detect_compression

    path = Path(path)
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    with open(path, 'rb') as f:
        entries = read_directory(f)

        for entry in entries:
            data = read_member(f, entry)
            filename = entry.filename

            # Optionally decompress
            if decompress and data:
                compression = detect_compression(data)
                if compression == 'squeeze':
                    from .squeeze import get_squeezed_filename
                    orig_name = get_squeezed_filename(data)
                    data = unsqueeze(data)
                    if orig_name:
                        filename = orig_name
                elif compression == 'crunch':
                    from .crunch import get_crunched_filename
                    orig_name = get_crunched_filename(data)
                    data = uncrunch(data)
                    if orig_name:
                        filename = orig_name
                elif compression == 'crlzh':
                    from .crlzh import get_crlzh_filename
                    orig_name = get_crlzh_filename(data)
                    data = uncrlzh(data)
                    if orig_name:
                        filename = orig_name

            # Optionally convert text files
            if convert_text and is_text_file(filename):
                data = strip_cpm_eof(data)
                data = crlf_to_lf(data)

            if output_dir:
                out_path = output_dir / filename
                out_path.write_bytes(data)

            results.append((filename, data))

    return results
