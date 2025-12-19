"""Tests for Squeeze decompression.

Note: Squeeze sample files needed for full test coverage.
Squeeze files use magic 0x76 0xFF and have .?Q? extensions
(e.g., .TQT for squeezed .TXT, .CQM for squeezed .COM).
"""

import pytest
from pathlib import Path

from un80.squeeze import unsqueeze, SqueezeError

SAMPLES_DIR = Path(__file__).parent / "samples" / "squeeze"


class TestSqueeze:
    """Tests for Squeeze decompression."""

    @pytest.mark.skip(reason="No squeeze samples available yet")
    def test_decompress_sample(self):
        """Test decompression of a squeezed file."""
        # TODO: Add actual squeeze sample files
        pass

    def test_invalid_magic(self):
        """Test that invalid magic raises error."""
        data = b'\x00\x00Invalid data'
        with pytest.raises(SqueezeError):
            unsqueeze(data)

    def test_squeeze_magic_constant(self):
        """Verify squeeze magic constant."""
        from un80.squeeze import SQUEEZE_MAGIC
        assert SQUEEZE_MAGIC == 0x76FF
