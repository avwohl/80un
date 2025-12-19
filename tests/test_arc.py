"""Tests for ARC archive handling.

Note: ARC sample files needed for full test coverage.
ARC files start with 0x1A marker byte followed by method byte.
"""

import pytest
from pathlib import Path

from un80.arc import list_arc, extract_arc, ArcError, ARC_MARKER

SAMPLES_DIR = Path(__file__).parent / "samples" / "arc"


class TestARC:
    """Tests for ARC archive handling."""

    @pytest.mark.skip(reason="No ARC samples available yet")
    def test_list_sample(self):
        """Test listing contents of an ARC file."""
        # TODO: Add actual ARC sample files
        pass

    @pytest.mark.skip(reason="No ARC samples available yet")
    def test_extract_sample(self):
        """Test extracting files from an ARC archive."""
        # TODO: Add actual ARC sample files
        pass

    def test_arc_marker_constant(self):
        """Verify ARC marker constant."""
        assert ARC_MARKER == 0x1A
