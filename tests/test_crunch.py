"""Tests for Crunch decompression."""

import pytest
from pathlib import Path

from un80.crunch import uncrunch, CrunchError

SAMPLES_DIR = Path(__file__).parent / "samples" / "crunch"


class TestCrunch:
    """Tests for Crunch decompression."""

    def test_decompress_czm(self):
        """Test decompression of CRUNCH.CZM (crunched .COM)."""
        sample = SAMPLES_DIR / "CRUNCH.CZM"
        if not sample.exists():
            pytest.skip("CRUNCH.CZM sample not available")

        data = sample.read_bytes()

        # Verify magic
        assert data[:2] == b'\x76\xfe', "Not a crunched file"

        result = uncrunch(data)

        # Should decompress to a COM file
        assert len(result) > 0
        # COM file should start with valid Z80 opcode
        assert result[0] in (0xC3, 0xC9, 0x00, 0x31, 0x21, 0x3E, 0xF3)

    def test_decompress_nzt(self):
        """Test decompression of -SOURCE.NZT (crunched .NOT)."""
        sample = SAMPLES_DIR / "-SOURCE.NZT"
        if not sample.exists():
            pytest.skip("-SOURCE.NZT sample not available")

        data = sample.read_bytes()

        # Verify magic
        assert data[:2] == b'\x76\xfe', "Not a crunched file"

        result = uncrunch(data)

        # Should decompress to text
        assert len(result) > 0

    def test_invalid_magic(self):
        """Test that invalid magic raises error."""
        data = b'\x00\x00Invalid data'
        with pytest.raises(CrunchError):
            uncrunch(data)

    def test_crunch_magic_constant(self):
        """Verify crunch magic constant."""
        from un80.crunch import CRUNCH_MAGIC
        assert CRUNCH_MAGIC == 0x76FE
