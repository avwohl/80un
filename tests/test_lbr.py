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


class TestSafeFilenames:
    """Names taken from an archive must never name a path of their own."""

    def test_directory_separators_are_replaced(self):
        from un80.cpm import safe_filename

        assert safe_filename('CCP/M.COM') == 'CCP_M.COM'
        assert safe_filename('a\\b.txt') == 'a_b.txt'

    def test_traversal_is_defused(self):
        from un80.cpm import safe_filename

        for hostile in ('../../etc/passwd', '/etc/passwd', '..\\..\\win.ini'):
            cleaned = safe_filename(hostile)
            assert '/' not in cleaned and '\\' not in cleaned
            assert not cleaned.startswith('/')

    def test_dot_names_fall_back(self):
        from un80.cpm import safe_filename

        assert safe_filename('.') == 'UNNAMED'
        assert safe_filename('..') == 'UNNAMED'
        assert safe_filename('') == 'UNNAMED'
        assert safe_filename('   ', fallback='X.BIN') == 'X.BIN'

    def test_control_characters_are_replaced(self):
        from un80.cpm import safe_filename

        assert safe_filename('A\x00B\x1fC.TXT') == 'A_B_C.TXT'

    def test_ordinary_names_are_untouched(self):
        from un80.cpm import safe_filename

        assert safe_filename('README.1ST') == 'README.1ST'
        assert safe_filename('-SOURCE.NOT') == '-SOURCE.NOT'

    def test_fallback_is_also_sanitised(self):
        """The fallback is usually another archive-supplied name."""
        from un80.cpm import safe_filename

        assert safe_filename('', fallback='CCP/M.COM') == 'CCP_M.COM'
        assert safe_filename('..', fallback='../evil') == '.._evil'
        assert safe_filename('', fallback='..') == 'UNNAMED'


class TestSanitisingEdgeCases:
    """
    The cases that turn a sanitised name back into a lost member.

    Sanitising is not free: it maps distinct member names onto one, and an
    over-long or device-shaped name reaches the filesystem unless it is bounded.
    """

    def test_windows_device_names_are_defused(self):
        from un80.cpm import safe_filename

        for device in ('NUL', 'CON.DOC', 'PRN.TXT', 'AUX', 'COM1', 'LPT1.LST'):
            assert safe_filename(device) == '_' + device

        # Only an exact device stem, not any name that starts like one.
        assert safe_filename('AUXX.TXT') == 'AUXX.TXT'
        assert safe_filename('CONFIG.SYS') == 'CONFIG.SYS'

    def test_trailing_dots_and_spaces_go(self):
        from un80.cpm import safe_filename

        assert safe_filename('NAME.') == 'NAME'
        assert safe_filename('NAME. . ') == 'NAME'

    def test_over_long_names_are_capped_keeping_the_extension(self):
        from un80.cpm import safe_filename

        capped = safe_filename('A' * 400 + '.DOC')
        assert len(capped.encode()) == 255
        assert capped.endswith('.DOC')

    def test_unique_filename_keeps_every_member(self):
        from un80.cpm import unique_filename

        used: set[str] = set()
        assert unique_filename('CCP_M.COM', used) == 'CCP_M.COM'
        assert unique_filename('CCP_M.COM', used) == 'CCP_M_1.COM'
        assert unique_filename('CCP_M.COM', used) == 'CCP_M_2.COM'
        # CP/M names are case-insensitive, and so may the host filesystem be.
        assert unique_filename('ccp_m.com', used) == 'ccp_m_3.com'
        # A name with no extension still gets a distinct suffix.
        assert unique_filename('README', used) == 'README'
        assert unique_filename('README', used) == 'README_1'


class TestExtractionIsResilient:
    """One unusable member must not cost the caller the rest of the archive."""

    @staticmethod
    def _rename_member(raw: bytes, old: bytes, new: bytes) -> bytes:
        """Rewrite one 11-byte LBR directory name field."""
        assert len(old) == len(new) == 11
        at = raw.index(old)
        return raw[:at] + new + raw[at + 11:]

    def test_colliding_members_are_all_written(self):
        """
        mouse.lbr ships CCP/M.COM and CCP/M.LTR.  Rename the second so that both
        sanitise to CCP_M.COM, and neither may be lost.
        """
        sample = SAMPLES_DIR / "mouse.lbr"
        if not sample.exists():
            pytest.skip("mouse.lbr sample not available")

        raw = self._rename_member(sample.read_bytes(), b'CCP/M   LTR', b'CCP/M   COM')

        with tempfile.TemporaryDirectory() as d:
            collide = Path(d) / "collide.lbr"
            collide.write_bytes(raw)
            out = Path(d) / "out"
            results = extract_lbr(collide, out)

            assert len(results) == len(list(out.iterdir())), "a member was overwritten"
            names = [name for name, _ in results]
            assert 'CCP_M.COM' in names and 'CCP_M_1.COM' in names
            # The reported name is the name actually written.
            for name, data in results:
                assert (out / name).read_bytes() == data

    @staticmethod
    def _build_lbr(members: list[tuple[str, bytes]]) -> bytes:
        """Build a one-sector-directory LBR holding up to three members."""
        assert len(members) <= 3
        out = bytearray()
        index = 1  # the directory occupies record 0

        def entry(name: str, at: int, sectors: int) -> bytes:
            stem, _, ext = name.partition('.')
            field = f"{stem:<8.8}{ext:<3.3}".encode()
            return b'\x00' + field + at.to_bytes(2, 'little') \
                + sectors.to_bytes(2, 'little') + bytes(32 - 16)

        out += entry('', 0, 1)
        body = bytearray()
        for name, data in members:
            sectors = (len(data) + 127) // 128
            out += entry(name, index, sectors)
            body += data.ljust(sectors * 128, b'\x00')
            index += sectors
        out += b'\xff' * (128 - len(out))
        return bytes(out + body)

    def test_a_member_that_will_not_decompress_is_kept_raw(self):
        """
        A Crunch V1 member cannot be decompressed, and raising used to abort the
        whole extraction.  The member must come back as stored, under its
        directory name, and the members around it must survive.
        """
        v1_path = Path(__file__).parent / "samples" / "crunch" / "zex-sage.dzc"
        if not v1_path.exists():
            pytest.skip("zex-sage.dzc sample not available")

        from un80.crunch import CrunchError, uncrunch

        v1 = v1_path.read_bytes()
        with pytest.raises(CrunchError):
            uncrunch(v1)          # V1 is refused rather than yielding rubbish

        archive = self._build_lbr(
            [('BEFORE.TXT', b'first\r\n'), ('ZEXSAGE.DZC', v1), ('AFTER.TXT', b'last\r\n')]
        )

        with tempfile.TemporaryDirectory() as d:
            lbr = Path(d) / "withv1.lbr"
            lbr.write_bytes(archive)
            out = Path(d) / "out"
            results = dict(extract_lbr(lbr, out))

            assert set(results) == {'BEFORE.TXT', 'ZEXSAGE.DZC', 'AFTER.TXT'}
            assert results['BEFORE.TXT'].startswith(b'first')
            assert results['AFTER.TXT'].startswith(b'last')
            # Kept exactly as stored, magic header and all.
            assert results['ZEXSAGE.DZC'].startswith(v1[:16])
