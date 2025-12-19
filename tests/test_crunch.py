"""Tests for Crunch decompression.

Note: Crunch sample files needed for full test coverage.
Crunch files use magic 0x76 0xFE and have .?Z? extensions
(e.g., .TZT for crunched .TXT, .CZM for crunched .COM).
"""

import pytest
from pathlib import Path

from un80.crunch import uncrunch, CrunchError

SAMPLES_DIR = Path(__file__).parent / "samples" / "crunch"


class TestCrunch:
    """Tests for Crunch decompression."""

    @pytest.mark.skip(reason="No crunch samples available yet")
    def test_decompress_sample(self):
        """Test decompression of a crunched file."""
        # TODO: Add actual crunch sample files
        pass

    def test_invalid_magic(self):
        """Test that invalid magic raises error."""
        data = b'\x00\x00Invalid data'
        with pytest.raises(CrunchError):
            uncrunch(data)

    def test_crunch_magic_constant(self):
        """Verify crunch magic constant."""
        from un80.crunch import CRUNCH_MAGIC
        assert CRUNCH_MAGIC == 0x76FE
