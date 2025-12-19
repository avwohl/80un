"""Tests for CrLZH decompression."""

import pytest
from pathlib import Path

from un80.crlzh import uncrlzh, parse_header, CrLZHError

SAMPLES_DIR = Path(__file__).parent / "samples" / "crlzh"


class TestCrLZH:
    """Tests for CrLZH decompression."""

    def test_parse_header_test_myc(self):
        """Test header parsing for TEST.MYC."""
        sample = SAMPLES_DIR / "TEST.MYC"
        if not sample.exists():
            pytest.skip("TEST.MYC sample not available")

        data = sample.read_bytes()
        filename, offset = parse_header(data)

        assert filename == "LZHDEF.MAC"
        assert offset == 57

    def test_decompress_test_myc(self):
        """Test decompression of TEST.MYC."""
        sample = SAMPLES_DIR / "TEST.MYC"
        if not sample.exists():
            pytest.skip("TEST.MYC sample not available")

        data = sample.read_bytes()
        result = uncrlzh(data)

        # Strip trailing CP/M EOF markers
        result = result.rstrip(b'\x1a')

        # Verify decompressed size
        assert len(result) == 1550

        # Verify content starts correctly
        assert result.startswith(b";---")
        assert b"LZH coding" in result

    def test_decompress_crlzh20_cym(self):
        """Test decompression of CRLZH20.CYM."""
        sample = SAMPLES_DIR / "CRLZH20.CYM"
        if not sample.exists():
            pytest.skip("CRLZH20.CYM sample not available")

        data = sample.read_bytes()
        result = uncrlzh(data)

        # Strip trailing EOF markers
        result = result.rstrip(b'\x1a')

        # Should decompress to a COM file (starts with jump or ret)
        assert len(result) > 0
        # Verify it's a valid executable
        assert result[0] in (0xC3, 0xC9, 0x00, 0x31)  # JMP, RET, NOP, or LD SP

    def test_invalid_magic(self):
        """Test that invalid magic raises error."""
        data = b'\x00\x00Invalid data'
        with pytest.raises(CrLZHError):
            uncrlzh(data)

    def test_unsupported_version(self):
        """Test that unsupported version raises error."""
        # Create fake header with version 0x21 (unsupported)
        data = b'\x76\xfd' + b'TEST\x00' + b'\x21\x00\x00\x00'
        with pytest.raises(CrLZHError, match="Unsupported version"):
            uncrlzh(data)
