"""Tests for Squeeze decompression."""

import pytest
from pathlib import Path

from un80.squeeze import unsqueeze, SqueezeError

SAMPLES_DIR = Path(__file__).parent / "samples" / "squeeze"


class TestSqueeze:
    """Tests for Squeeze decompression."""

    def test_decompress_tqt(self):
        """Test decompression of mbastip.tqt (squeezed .TXT)."""
        sample = SAMPLES_DIR / "mbastip.tqt"
        if not sample.exists():
            pytest.skip("mbastip.tqt sample not available")

        data = sample.read_bytes()

        # Verify magic
        assert data[:2] == b'\x76\xff', "Not a squeezed file"

        result = unsqueeze(data)

        # Should decompress to readable text
        assert len(result) > 0
        # TXT file should contain printable ASCII
        assert any(32 <= b < 127 for b in result[:100])

    def test_decompress_bqs(self):
        """Test decompression of 555-ic.bqs (squeezed .BAS)."""
        sample = SAMPLES_DIR / "555-ic.bqs"
        if not sample.exists():
            pytest.skip("555-ic.bqs sample not available")

        data = sample.read_bytes()

        # Verify magic
        assert data[:2] == b'\x76\xff', "Not a squeezed file"

        result = unsqueeze(data)

        # Should decompress to BASIC source
        assert len(result) > 0

    def test_invalid_magic(self):
        """Test that invalid magic raises error."""
        data = b'\x00\x00Invalid data'
        with pytest.raises(SqueezeError):
            unsqueeze(data)

    def test_squeeze_magic_constant(self):
        """Verify squeeze magic constant."""
        from un80.squeeze import SQUEEZE_MAGIC
        assert SQUEEZE_MAGIC == 0x76FF
