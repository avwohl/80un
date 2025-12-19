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
