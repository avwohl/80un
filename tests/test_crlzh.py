"""Tests for CrLZH decompression."""

import pytest
from pathlib import Path

from un80.crlzh import uncrlzh, parse_header, CrLZHError
from un80.cpm import strip_cpm_eof, crlf_to_lf

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

        # Verify decompressed size (with CR+LF line endings)
        assert len(result) == 1550

        # Verify content starts correctly
        assert result.startswith(b";---")
        assert b"LZH coding" in result

    def test_decompress_has_crlf(self):
        """Test that raw decompression preserves CP/M CR+LF line endings.

        This is important for verifying the decompressor is not doing any
        line-ending conversion. The raw output should match what CP/M would
        produce. When testing the PL/M version via cpmemu, use binary mode
        to avoid the emulator's automatic CR+LF -> LF conversion.
        """
        sample = SAMPLES_DIR / "TEST.MYC"
        if not sample.exists():
            pytest.skip("TEST.MYC sample not available")

        data = sample.read_bytes()
        result = uncrlzh(data)

        # Raw output should contain CR+LF pairs (CP/M format)
        crlf_count = result.count(b'\r\n')
        assert crlf_count > 0, "Raw output should contain CR+LF line endings"

        # There should be no lone LF (all LF should be preceded by CR)
        lf_count = result.count(b'\n')
        assert lf_count == crlf_count, "All LF should be part of CR+LF pairs"

    def test_decompress_matches_reference(self):
        """Test that text-converted output matches Unix reference file.

        The reference file (lzhdef.mac) has Unix LF line endings. This test
        verifies that applying text conversion (strip EOF, convert CR+LF to LF)
        produces output matching the reference.

        Note: When testing PL/M output via cpmemu in default (text) mode, the
        emulator automatically performs this conversion for .MAC files.
        """
        sample = SAMPLES_DIR / "TEST.MYC"
        reference = SAMPLES_DIR / "lzhdef.mac"
        if not sample.exists():
            pytest.skip("TEST.MYC sample not available")
        if not reference.exists():
            pytest.skip("lzhdef.mac reference not available")

        data = sample.read_bytes()
        result = uncrlzh(data)

        # Apply text conversion (same as --text flag)
        result = strip_cpm_eof(result)
        result = crlf_to_lf(result)

        expected = reference.read_bytes()
        assert result == expected, "Text-converted output should match reference"

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

    def test_decompress_v1_format(self):
        """Test decompression of CrLZH V1.x format (version < 0x20).

        V1.x uses 6-bit lower position encoding (vs 5-bit for V2.0).
        This tests the decode_position_v1 code path.
        """
        sample = SAMPLES_DIR / "qto-zb12.aym"
        if not sample.exists():
            pytest.skip("qto-zb12.aym sample not available")

        # Verify it's actually V1
        from un80.crlzh import get_crlzh_info
        info = get_crlzh_info(sample.read_bytes())
        assert info is not None
        assert info['version'] < 0x20, f"Expected V1.x, got version 0x{info['version']:02X}"

        # Decompress and verify
        data = sample.read_bytes()
        result = uncrlzh(data)

        # Should decompress to assembly source
        assert len(result) > 1000
        assert b"QTERM" in result or b"qterm" in result.lower()
