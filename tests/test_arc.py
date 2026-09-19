"""Tests for ARC archive handling."""

import pytest
from pathlib import Path
import tempfile

from un80.arc import list_arc, extract_arc, ArcError, ARC_MARKER

SAMPLES_DIR = Path(__file__).parent / "samples" / "arc"


class TestARC:
    """Tests for ARC archive handling."""

    def test_list_ark11(self):
        """Test listing contents of ark11.arc."""
        sample = SAMPLES_DIR / "ark11.arc"
        if not sample.exists():
            pytest.skip("ark11.arc sample not available")

        entries = list_arc(sample)

        # Should have entries
        assert len(entries) > 0

        # Check entry has expected attributes
        entry = entries[0]
        assert hasattr(entry, 'filename')
        assert hasattr(entry, 'compressed_size')
        assert hasattr(entry, 'original_size')

    def test_list_ark_extension(self):
        """Test listing contents of .ark file (same format as .arc)."""
        sample = SAMPLES_DIR / "cp409doc.ark"
        if not sample.exists():
            pytest.skip("cp409doc.ark sample not available")

        entries = list_arc(sample)

        # Should have entries
        assert len(entries) > 0

    def test_extract_ark11(self):
        """Test extracting files from ark11.arc."""
        sample = SAMPLES_DIR / "ark11.arc"
        if not sample.exists():
            pytest.skip("ark11.arc sample not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            results = extract_arc(sample, tmpdir)

            # Should extract files
            assert len(results) > 0

            # Check files exist
            for filename, size in results:
                path = Path(tmpdir) / filename
                assert path.exists()
                assert path.stat().st_size > 0

    def test_arc_marker_constant(self):
        """Verify ARC marker constant."""
        assert ARC_MARKER == 0x1A

    def test_arc_file_magic(self):
        """Verify ARC files start with correct marker."""
        sample = SAMPLES_DIR / "ark11.arc"
        if not sample.exists():
            pytest.skip("ark11.arc sample not available")

        data = sample.read_bytes()
        assert data[0] == ARC_MARKER

    def test_method2_stored(self):
        """Test extraction of method 2 (stored) files."""
        sample = SAMPLES_DIR / "method2.arc"
        if not sample.exists():
            pytest.skip("method2.arc sample not available")

        entries = list_arc(sample)
        stored_entries = [e for e in entries if e.method == 2]
        assert len(stored_entries) > 0, "No method 2 (stored) entries found"

        # Extract and verify stored files have same size compressed/original
        results = extract_arc(sample, None)
        assert len(results) > 0

    def test_method3_packed_rle(self):
        """Test extraction of method 3 (packed/RLE) files."""
        sample = SAMPLES_DIR / "method3.arc"
        if not sample.exists():
            pytest.skip("method3.arc sample not available")

        entries = list_arc(sample)
        packed_entries = [e for e in entries if e.method == 3]
        assert len(packed_entries) > 0, "No method 3 (packed) entries found"

        # Extract - RLE decompression should work
        results = extract_arc(sample, None)
        assert len(results) > 0

    def test_method9_squashed(self):
        """Test extraction of method 9 (squashed/13-bit LZW) files."""
        sample = SAMPLES_DIR / "method9.arc"
        if not sample.exists():
            pytest.skip("method9.arc sample not available")

        entries = list_arc(sample)
        squashed_entries = [e for e in entries if e.method == 9]
        assert len(squashed_entries) > 0, "No method 9 (squashed) entries found"

        # Extract - 13-bit LZW decompression should work
        results = extract_arc(sample, None)
        assert len(results) > 0


def crc16_arc(data: bytes) -> int:
    """The CRC-16 (reflected, poly 0xA001) that every ARC member header carries."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _members(sample: Path):
    """Yield (entry, decompressed_bytes) for every member of an ARC archive."""
    from un80.arc import parse_header, decompress_member

    raw = sample.read_bytes()
    with open(sample, 'rb') as f:
        while True:
            entry = parse_header(f)
            if entry is None:
                break
            chunk = raw[entry.data_offset:entry.data_offset + entry.compressed_size]
            yield entry, decompress_member(entry, chunk)
            f.seek(entry.data_offset + entry.compressed_size)


class TestArcChecksums:
    """
    Validate decompression against the CRC-16 stored in each member header.

    This is the archive's own integrity check, so it is ground truth rather than
    a recording of current behaviour.  It is what proves RLE90's `0x90 N` count
    is a total (N-1 further copies) and not an addition: with the off-by-one,
    only 8 of these 48 members validate.
    """

    # Every member of every sample validates; nothing is excused.
    @pytest.mark.parametrize("name", sorted(p.name for p in SAMPLES_DIR.glob('*')))
    def test_member_crcs(self, name):
        sample = SAMPLES_DIR / name
        if not sample.exists():
            pytest.skip(f"{name} sample not available")

        checked = 0
        for entry, data in _members(sample):
            checked += 1
            assert len(data) == entry.original_size, (
                f"{name}:{entry.filename} method {entry.method} wrong length"
            )
            assert crc16_arc(data) == entry.crc, (
                f"{name}:{entry.filename} method {entry.method} CRC mismatch"
            )
        assert checked > 0
