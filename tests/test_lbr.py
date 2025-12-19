"""Tests for LBR archive handling."""

import pytest
from pathlib import Path
import tempfile
import os

from un80.lbr import list_lbr, extract_lbr

SAMPLES_DIR = Path(__file__).parent / "samples" / "lbr"


class TestLBR:
    """Tests for LBR archive handling."""

    def test_list_crlzh20_lbr(self):
        """Test listing contents of crlzh20.lbr."""
        sample = SAMPLES_DIR / "crlzh20.lbr"
        if not sample.exists():
            pytest.skip("crlzh20.lbr sample not available")

        entries = list_lbr(sample)

        # Should have multiple entries
        assert len(entries) > 10

        # Check for known files
        names = [e.filename for e in entries]
        assert "UCRLZH20.COM" in names
        assert "CRLZH20.FOR" in names

    def test_extract_crlzh20_lbr(self):
        """Test extracting files from crlzh20.lbr."""
        sample = SAMPLES_DIR / "crlzh20.lbr"
        if not sample.exists():
            pytest.skip("crlzh20.lbr sample not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            results = extract_lbr(sample, tmpdir)

            # Should extract multiple files
            assert len(results) > 10

            # Check that COM file was extracted and decompressed
            com_path = Path(tmpdir) / "UCRLZH20.COM"
            assert com_path.exists()
            assert com_path.stat().st_size > 0

            # COM file should start with valid Z80 opcode
            with open(com_path, 'rb') as f:
                first_byte = f.read(1)[0]
            assert first_byte in (0xC3, 0xC9, 0x00, 0x31, 0x21, 0x3E)

    def test_extract_preserves_content(self):
        """Test that extraction preserves file content correctly."""
        sample = SAMPLES_DIR / "crlzh20.lbr"
        if not sample.exists():
            pytest.skip("crlzh20.lbr sample not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            results = extract_lbr(sample, tmpdir)

            # Find a text file
            txt_files = [r for r in results if r[0].endswith('.TXT') or r[0].endswith('.FOR')]
            assert len(txt_files) > 0

            # Check it contains readable text
            txt_path = Path(tmpdir) / txt_files[0][0]
            content = txt_path.read_bytes()
            # Should contain printable ASCII
            assert any(32 <= b < 127 for b in content[:100])
