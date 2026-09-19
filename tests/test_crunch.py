"""
Tests for Crunch decompression.

The expected digests for mouse.lbr come from running the original GEL Uncruncher
v2.4 (UNCR24.COM, itself a member of mouse.lbr) under the cpmemu CP/M emulator
and trimming the CP/M record padding off its output.  They are ground truth, not
a recording of what this decoder happens to produce.

mouse.lbr is the archive from https://github.com/avwohl/80un/issues/2 - it is the
regression case for two bugs:

  * RLE90 emitted one byte too many per run, which damaged every file from the
    first run marker onward.
  * The dictionary was frozen once it held 4096 entries instead of switching to
    CRUNCH's replacement mode, which corrupted everything after the table filled.
    MOUSE.MZC fills the table early; COCONUT.MZE only fills it 181 bytes before
    the end, which is why that file looked almost right.
"""

import hashlib

import pytest
from pathlib import Path

from un80.crunch import uncrunch, decode_rle, CrunchError
from un80.lbr import list_lbr

SAMPLES_DIR = Path(__file__).parent / "samples" / "crunch"
LBR_DIR = Path(__file__).parent / "samples" / "lbr"
MOUSE_LBR = LBR_DIR / "mouse.lbr"

# member name -> (uncompressed length, sha256) as produced by UNCR24.COM
MOUSE_MEMBERS = {
    'ASCII.MZE': (1664, '19d1e3e0304b3806c1caa4d50bda5d8f4970b39b7e4b8cdf0542869942d262bf'),
    'COCONUT.MZE': (9984, '93ba3445a4afedf6c5593e6af999680937114eab7acd839848c5a52b8aeb7fa9'),
    'FILES.MZE': (8192, '10c0584619a46732bbb176edeb3f48fc578a761e7e2adef69083d69a2fd31190'),
    'HELP.MZE': (5504, 'afc68f38aae224f45bacea5ffbc53645a51c2af2f899be7806e26ea118a8db98'),
    'MOUSE.AZT': (9216, 'fd8778c20661c11538301b777763fed360e39e320e518cfc7106abf656f8d979'),
    'MOUSE.MZC': (38784, '565fb87252ffbbdfa5188192136e57c603081bd662693670f4750f683f965265'),
    'NUMBERS.MZE': (4992, '59bf07c4f0ae81141b8bebe8bf7078547bcf30987418273399da6667d09299fa'),
    'ODD.MZE': (1536, 'baf8fcd39e7a21aef213543f017fec93f4219225eea9d7204a20352d0d9d080e'),
    'OLDMACDO.MZE': (896, '111807d4a819b0c39a2c237a0ec04352ee45ee96093892cf4d491e4f0fd60d90'),
    'SELFGEN.DZC': (8704, 'e636ac19eebf2d8b4003af0d913db4d078c584ef504a51c5e57b6ae4250f3144'),
    'SELFGEN.MZE': (640, 'ed3e3e5c63ff4a2d1b71a2dd5b727a83e2d5a16d977b9c8becc2119a02668066'),
    'SOLVE.MZE': (3456, 'd995b62e00a07ad820c55cf9b684a3c054f00af3e23014affc43f61520b4b3a4'),
    'TEST.MZE': (1792, '86d7b778fab2a56f334af5029a34c19ab4693f38e9b0793c78beef733b75222c'),
    'Z80.MZE': (2560, 'a56093321db71650d3f4f0781dc8ab59b6db2eb9bfb0bc531853cb4ffd086daf'),
}

# These two fill the 4096-entry dictionary, so they exercise replacement mode.
TABLE_FILLING = ('MOUSE.MZC', 'COCONUT.MZE')


def _mouse_member(name: str) -> bytes:
    """Return one raw (still crunched) member of mouse.lbr."""
    data = MOUSE_LBR.read_bytes()
    for entry in list_lbr(MOUSE_LBR):
        if entry.is_directory or entry.filename != name:
            continue
        start = entry.index * 128
        return data[start:start + entry.length * 128]
    raise AssertionError(f"{name} not found in mouse.lbr")


class TestRle90:
    """RLE90 is shared by crunch, squeeze and ARC, so it gets its own tests."""

    def test_count_is_a_total_not_an_addition(self):
        """0x90 N means N occurrences in total, so N-1 further copies."""
        assert decode_rle(b'A\x90\x05') == b'AAAAA'
        assert decode_rle(b'A\x90\x02') == b'AA'

    def test_count_of_one_adds_nothing(self):
        """
        A deliberate difference from UNCR24.

        UNCR24 decrements the count into B and then runs a do-while loop, so
        `90 01` underflows to 256 copies - running the real UNCR24.COM on
        `A 90 01` under cpmemu produces 257 'A's.  No encoder emits `90 01`,
        and reproducing the underflow would turn three bytes into 257.
        """
        assert decode_rle(b'A\x90\x01') == b'A'

    def test_zero_count_is_a_literal_marker(self):
        assert decode_rle(b'\x90\x00') == b'\x90'

    def test_literal_marker_does_not_become_the_previous_byte(self):
        """After 0x90 0x00 the previous byte is still 'A', not 0x90."""
        assert decode_rle(b'A\x90\x00\x90\x03') == b'A\x90AA'

    def test_trailing_marker_is_dropped(self):
        """
        A marker with no count byte after it carries no data.

        UNCR24 only arms its escape flag and then runs out of input, so it
        writes nothing; running it on `A 90` under cpmemu produces just 'A'.
        """
        assert decode_rle(b'AB\x90') == b'AB'

    def test_data_without_markers_is_unchanged(self):
        assert decode_rle(b'hello world') == b'hello world'


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

    def test_decompress_lzb_fills_the_dictionary(self):
        """COMMON.LZB is large enough to fill the table and recycle 7177 entries."""
        sample = SAMPLES_DIR / "COMMON.LZB"
        if not sample.exists():
            pytest.skip("COMMON.LZB sample not available")

        result = uncrunch(sample.read_bytes())

        # UNCR24.COM produces 64768 bytes including the CP/M record padding.
        assert len(result) == 64768
        assert hashlib.sha256(result).hexdigest() == (
            '5b57c7ed00e5f27b5761f2fef773459d8027670b5babb722915b80d1a62a5e5c'
        )

    def test_invalid_magic(self):
        """Test that invalid magic raises error."""
        data = b'\x00\x00Invalid data'
        with pytest.raises(CrunchError):
            uncrunch(data)

    def test_crunch_magic_constant(self):
        """Verify crunch magic constant."""
        from un80.crunch import CRUNCH_MAGIC
        assert CRUNCH_MAGIC == 0x76FE


class TestMouseLbr:
    """Regression tests for issue #2, using the archive from the report."""

    @pytest.mark.parametrize("name", sorted(MOUSE_MEMBERS))
    def test_member_matches_uncr24(self, name):
        """Every crunched member decodes exactly as UNCR24.COM decodes it."""
        if not MOUSE_LBR.exists():
            pytest.skip("mouse.lbr sample not available")

        expected_len, expected_sha = MOUSE_MEMBERS[name]
        result = uncrunch(_mouse_member(name))

        assert len(result) == expected_len
        assert hashlib.sha256(result).hexdigest() == expected_sha

    @pytest.mark.parametrize("name", TABLE_FILLING)
    def test_table_filling_member_is_not_truncated(self, name):
        """
        MOUSE.MZC and COCONUT.MZE are the members that fill the dictionary.

        Freezing the table instead of recycling entries used to leave these two
        badly corrupted while every other member merely had spurious bytes.
        """
        if not MOUSE_LBR.exists():
            pytest.skip("mouse.lbr sample not available")

        result = uncrunch(_mouse_member(name))
        assert len(result) == MOUSE_MEMBERS[name][0]

    def test_archive_contains_its_own_uncruncher(self):
        """UNCR24.COM ships inside mouse.lbr; it is where the expectations come from."""
        if not MOUSE_LBR.exists():
            pytest.skip("mouse.lbr sample not available")

        names = {e.filename for e in list_lbr(MOUSE_LBR) if not e.is_directory}
        assert 'UNCR24.COM' in names
        assert MOUSE_MEMBERS.keys() <= names


class TestHeaderNote:
    """CRUNCH may append a bracketed note to the embedded filename."""

    def test_note_is_split_off_the_filename(self):
        if not MOUSE_LBR.exists():
            pytest.skip("mouse.lbr sample not available")

        from un80.crunch import parse_header

        header = parse_header(_mouse_member('ASCII.MZE'))
        assert header.filename == 'ASCII.MSE'
        assert header.note == '[02/04/88]'

    def test_note_may_be_free_text(self):
        sample = SAMPLES_DIR / "COMMON.LZB"
        if not sample.exists():
            pytest.skip("COMMON.LZB sample not available")

        from un80.crunch import parse_header

        header = parse_header(sample.read_bytes())
        assert header.filename == 'COMMON.LIB'
        assert header.note == '[ V2.4 INCLUDE FILE]'

    def test_filename_without_a_note(self):
        from un80.crunch import parse_header

        data = b'\x76\xfePLAIN.TXT\x00\x24\x20\x00\x00'
        header = parse_header(data)
        assert header.filename == 'PLAIN.TXT'
        assert header.note == ''


class TestExtractMouseLbr:
    """The whole archive has to come out, which is what the issue reported."""

    def test_every_member_extracts(self, tmp_path):
        if not MOUSE_LBR.exists():
            pytest.skip("mouse.lbr sample not available")

        from un80.lbr import extract_lbr

        results = extract_lbr(MOUSE_LBR, tmp_path)
        names = {name for name, _ in results}

        assert len(results) == 21
        # The bracketed note used to end up in the name, and its slashes made
        # extraction fail outright.
        assert 'ASCII.MSE' in names
        assert not any('[' in name for name in names)
        # A CP/M name may contain '/', which is not a directory separator there.
        assert 'CCP_M.COM' in names
        assert all((tmp_path / name).exists() for name in names)


def _pack_codes(codes, width=9):
    """Pack LZW codes MSB-first, the way a crunch stream stores them."""
    acc = bits = 0
    out = bytearray()
    for code in codes:
        acc = (acc << width) | code
        bits += width
        while bits >= 8:
            out.append((acc >> (bits - 8)) & 0xFF)
            bits -= 8
    if bits:
        out.append((acc << (8 - bits)) & 0xFF)
    return bytes(out)


HEADER = b'\x76\xfeFUZZ.TXT\x00\x24\x20\x00\x00'


class TestStreamControlCodes:
    """The four reserved codes, 256-259."""

    def test_eof_code_ends_the_stream(self):
        assert uncrunch(HEADER + _pack_codes([65, 66, 0x100, 67])) == b'AB'

    def test_reset_code_rebuilds_the_dictionary(self):
        assert uncrunch(HEADER + _pack_codes([65, 66, 0x101, 67, 68, 0x100])) == b'ABCD'

    def test_reset_code_restarts_the_dictionary_numbering(self):
        """
        A reset must actually rebuild the table, not merely be skipped.

        The plain round-trip above passes with the whole RESET_CODE handler
        replaced by `continue`, so it proves nothing.  This one does not: code
        260 is the first entry a stream creates, and after a reset it must name
        the entry built since the reset, not the one built before it.
        """
        # A B <reset> C D 260 : the last code is "CD", created after the reset.
        assert uncrunch(
            HEADER + _pack_codes([65, 66, 0x101, 67, 68, 260, 0x100])
        ) == b'ABCDCD'

        # Without the reset, 260 is still "AB" from the start of the stream.
        assert uncrunch(
            HEADER + _pack_codes([65, 66, 67, 68, 260, 0x100])
        ) == b'ABCDAB'

    def test_filler_codes_are_skipped(self):
        assert uncrunch(HEADER + _pack_codes([65, 0x102, 66, 0x103, 67, 0x100])) == b'ABC'


class TestMalformedInput:
    """
    Corrupt input must fail, not hang.

    The dictionary hash probe and the prefix-chain walk are both bounded; before
    that, a stream that filled the hash table or closed a prefix cycle could spin
    forever.
    """

    @pytest.mark.parametrize("name", ['MOUSE.MZC', 'COCONUT.MZE'])
    def test_truncation_terminates(self, name):
        if not MOUSE_LBR.exists():
            pytest.skip("mouse.lbr sample not available")

        data = _mouse_member(name)
        for numerator in range(1, 16):
            chunk = data[:len(data) * numerator // 16]
            try:
                result = uncrunch(chunk)
            except CrunchError:
                continue
            assert isinstance(result, bytes)

    @pytest.mark.parametrize("data,message", [
        (b'', 'Data too short'),
        (b'\x76\xfe', 'Data too short'),
        (b'\x76\xfe' + b'A' * 50, 'Unterminated filename'),
        (b'\x00\x00abc', 'Invalid magic'),
    ])
    def test_degenerate_headers_raise(self, data, message):
        with pytest.raises(CrunchError, match=message):
            uncrunch(data)

    def test_header_with_no_payload(self):
        assert uncrunch(HEADER) == b''

    def test_random_payloads_terminate(self):
        import random

        rng = random.Random(1234)
        for _ in range(200):
            body = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 400)))
            try:
                result = uncrunch(HEADER + body)
            except CrunchError:
                continue
            assert isinstance(result, bytes)
