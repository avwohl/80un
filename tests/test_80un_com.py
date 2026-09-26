"""
80un.com, the CP/M program, against src/un80.

These build 80un.com from src/plm with the uplm80 on PATH (the Makefile's own
rule, in a scratch directory, so the committed binary is left alone), run it
under cpmemu in binary mode, and compare every file it writes with what
src/un80 extracts.  80un writes whole 128-byte records, so a file may carry ^Z
padding past src/un80's length, and nothing else.

They are skipped when make, uplm80, um80, ul80 or cpmemu is not there.  cpmemu
is looked for as $CPMEMU, on PATH, and where the Makefile has it.  $UPLM80, if
set, is the compiler command, passed to make as UPLM80.
"""

import os
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from un80.arc import extract_arc
from un80.crunch import uncrunch
from un80.lbr import extract_lbr
from un80.squeeze import unsqueeze

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"


def _cpmemu():
    for candidate in (os.environ.get("CPMEMU"), shutil.which("cpmemu"),
                      str(Path.home() / "src" / "cpmemu" / "src" / "cpmemu")):
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


CPMEMU = _cpmemu()
UPLM80 = os.environ.get("UPLM80")
MISSING = [tool for tool in ("make", "uplm80", "um80", "ul80")
           if not (tool == "uplm80" and UPLM80) and not shutil.which(tool)]
if CPMEMU is None:
    MISSING.append("cpmemu")

pytestmark = pytest.mark.skipif(bool(MISSING), reason=f"needs {', '.join(MISSING)}")


@pytest.fixture(scope="module")
def com(tmp_path_factory):
    """80un.com built from src/plm by the Makefile's rule, in a scratch copy."""
    build = tmp_path_factory.mktemp("build")
    shutil.copytree(ROOT / "src" / "plm", build / "src" / "plm")
    shutil.copy(ROOT / "Makefile", build / "Makefile")
    command = ["make", "-C", str(build), "80un.com"]
    if UPLM80:
        command.append(f"UPLM80={UPLM80}")
    done = subprocess.run(command, capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr
    return build / "80un.com"


def run_80un(com: Path, archive: Path, workdir: Path, name: str | None = None,
             timeout: int = 300, keep: dict | None = None):
    """Run 80un.com on a copy of ARCHIVE; return (console, {file: bytes}).
    The copy is left out of the files; if KEEP is a dict, KEEP["archive"] is
    what it holds after the run."""
    workdir.mkdir(parents=True, exist_ok=True)
    name = name or archive.name
    shutil.copy(archive, workdir / name)
    cfg = workdir.parent / (workdir.name + ".cfg")
    cfg.write_text(f"program = {com}\ncd = {workdir}\n"
                   "default_mode = binary\neol_convert = false\n")
    done = subprocess.run([CPMEMU, str(cfg), name.upper()], capture_output=True,
                          text=True, errors="replace", timeout=timeout,
                          stdin=subprocess.DEVNULL)
    if keep is not None:
        keep["archive"] = (workdir / name).read_bytes() if (workdir / name).exists() else None
    (workdir / name).unlink(missing_ok=True)
    files = {p.name: p.read_bytes() for p in workdir.iterdir()}
    return done.stdout + done.stderr, files


def assert_same(got: bytes, want: bytes, what: str):
    """GOT is WANT, padded with ^Z to a whole 128-byte record."""
    records = -(-len(want) // 128) * 128
    assert len(got) == records, f"{what}: {len(got)} bytes, want {records}"
    assert got[:len(want)] == want, f"{what}: contents differ"
    assert set(got[len(want):]) <= {0x1A}, f"{what}: padding is not ^Z"


def test_test_arc_all_members(com, tmp_path):
    """
    BYE520.ASM's compressed size, 75584, passes 64K: 80un kept the low 16 bits,
    wrote 19840 of its 162304 bytes and lost the five members after it.
    """
    archive = TESTS / "test.arc"
    console, files = run_80un(com, archive, tmp_path / "arc")
    want = extract_arc(archive)
    assert len(want) == 18
    assert "18 file(s) extracted" in console, console
    assert sorted(files) == sorted(name.lower() for name, _ in want), console
    for name, data in want:
        assert_same(files[name.lower()], data, name)
    assert len(files["bye520.asm"]) == 162304


def test_zex_sage_is_crunch_v1_with_a_slash(com, tmp_path):
    """
    ZEX/SAGE.DOC could not be created, and it is Crunch V1.  80un names it
    ZEX-SAGE.DOC and decodes it as src/un80 (and UNCR24) do.
    """
    archive = TESTS / "samples" / "crunch" / "zex-sage.dzc"
    console, files = run_80un(com, archive, tmp_path / "zex")
    assert "ZEX/SAGE.DOC -> ZEX-SAGE.DOC [Crunch V1] OK" in console, console
    assert list(files) == ["zex-sage.doc"], console
    want = uncrunch(archive.read_bytes())
    assert len(want) == 4992
    assert_same(files["zex-sage.doc"], want, "ZEX-SAGE.DOC")


def _crc16_arc(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _arc_member(method: int, name: bytes, stored: bytes, original: bytes) -> bytes:
    return (bytes([0x1A, method]) + name.ljust(13, b"\0")[:13]
            + struct.pack("<I", len(stored)) + bytes(4)
            + struct.pack("<H", _crc16_arc(original)) + struct.pack("<I", len(original))
            + stored)


def _rle90(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        c = data[i]
        n = 1
        while i + n < len(data) and data[i + n] == c and n < 255 and c != 0x90:
            n += 1
        if c == 0x90:
            out += b"\x90\x00"
        elif n >= 3:
            out += bytes([c, 0x90, n])
        else:
            out.append(c)
            n = 1
        i += n
    return bytes(out)


def test_members_past_64k(com, tmp_path):
    """A stored member of 100000 bytes and a packed one of over 64K, each
    followed by a member that must still be found."""
    import random

    rng = random.Random(3)
    stored = bytes(rng.randrange(256) for _ in range(100000))
    runs = bytearray()
    while len(runs) < 250000:
        runs += bytes([rng.randrange(256)]) * rng.choice([1] * 12 + [2, 5, 40])
    runs = bytes(runs)
    packed = _rle90(runs)
    assert len(packed) > 65536
    after = b"the member after the big one\r\n" * 5
    image = (_arc_member(2, b"BIG.BIN", stored, stored)
             + _arc_member(2, b"AFTER1.TXT", after, after)
             + _arc_member(3, b"RUNS.BIN", packed, runs)
             + _arc_member(2, b"AFTER2.TXT", after, after) + b"\x1a\x00")
    archive = tmp_path / "big.arc"
    archive.write_bytes(image)
    console, files = run_80un(com, archive, tmp_path / "big")
    assert "4 file(s) extracted" in console, console
    for name, data in extract_arc(archive):
        assert_same(files[name.lower()], data, name)


def test_names_cpm_cannot_take(com, tmp_path):
    """Stored names are made into CP/M names by the rule in names.plm."""
    names = [
        (b"zex/sage.doc", "ZEX-SAGE.DOC"),
        (b"my_file.txt", "MY-FILE.TXT"),
        (b"A.B.C", "A-B.C"),
        (b"LONGFILENAME", "LONGFILE"),
        (b"FILE.C", "FILE.C"),
        (b".PROFILE", "UNNAMED.PRO"),
        (b"CCP/M.COM", "CCP-M.COM"),
        (b"ccp_m.com", "CCP-M-1.COM"),
        (b"BYE520.ASM", "BYE520.ASM"),
    ]
    image = b""
    for i, (stored, _) in enumerate(names):
        body = f"member {i}\r\n".encode() * 3
        image += _arc_member(2, stored, body, body)
    archive = tmp_path / "names.arc"
    archive.write_bytes(image + b"\x1a\x00")
    console, files = run_80un(com, archive, tmp_path / "names")
    assert sorted(files) == sorted(cpm.lower() for _, cpm in names), console
    for i, (stored, cpm) in enumerate(names):
        assert_same(files[cpm.lower()], f"member {i}\r\n".encode() * 3, cpm)
    assert "zex/sage.doc -> ZEX-SAGE.DOC OK" in console, console
    assert "  BYE520.ASM OK" in console, console


# A decoder that never ends is killed here rather than at run_80un's 300 s.
HANG = 60


def _lbr(members, dsec=None):
    """An LBR image; MEMBERS is [(name, type, bytes)], b"" for no sectors.
    DSEC is the directory's length in sectors, by default the fewest that
    hold its entries."""
    count = len(members) + 1
    dsec = dsec or -(-count * 32 // 128)
    directory = b"\0" + b" " * 11 + struct.pack("<HH", 0, dsec) + bytes(16)
    body = b""
    index = dsec
    for name, ext, data in members:
        sectors = -(-len(data) // 128)
        directory += (b"\0" + name.ljust(8).encode() + ext.ljust(3).encode()
                      + struct.pack("<HH", index if sectors else 0, sectors) + bytes(16))
        body += data.ljust(sectors * 128, b"\x1a")
        index += sectors
    return directory.ljust(dsec * 128, b"\xff") + body


def _empty_squeezed(name: bytes) -> bytes:
    """What SQ writes for an empty file: a tree of no nodes, no code bits."""
    return b"\x76\xff\0\0" + name + b"\0" + b"\0\0"


def test_empty_squeezed_file(com, tmp_path):
    """
    A squeeze tree of no nodes, SQ's empty file, read no bit and went round for
    ever: alone, as an LBR member and as an ARC method 4 member, and the
    members after it were never reached.  So did a tree that loops back on
    itself.  src/un80 decodes each to nothing, and a tree whose child is past
    its end too.
    """
    alone = tmp_path / "empty.bqn"
    alone.write_bytes(_empty_squeezed(b"EMPTY.TXT").ljust(128, b"\x1a"))
    assert unsqueeze(alone.read_bytes()) == b""
    console, files = run_80un(com, alone, tmp_path / "alone", timeout=HANG)
    assert "Creating: EMPTY.TXT OK" in console, console
    assert files == {"empty.txt": b""}, console

    after = b"the member after the empty one\r\n" * 5
    padded = after.ljust(256, b"\x1a")
    lbr = tmp_path / "empty.lbr"
    lbr.write_bytes(_lbr([("EMPTY", "TQT", _empty_squeezed(b"EMPTY.TXT")),
                          ("AFTER", "TXT", after)]))
    want = extract_lbr(lbr)
    assert [data for _, data in want] == [b"", padded]
    console, files = run_80un(com, lbr, tmp_path / "lbr", timeout=HANG)
    assert "2 file(s) extracted" in console, console
    assert files == {"empty.tqt": b"", "after.txt": padded}, console

    loop = struct.pack("<HHH", 1, 0, 0)  # one node, both of its children itself
    past = struct.pack("<HHH", 1, 5, 5)  # one node, its children node 5
    arc = tmp_path / "empty.arc"
    arc.write_bytes(_arc_member(4, b"EMPTY.TXT", b"\0\0\0", b"")
                    + _arc_member(4, b"LOOP.TXT", loop + b"\x55" * 40, b"")
                    + _arc_member(4, b"PAST.TXT", past + b"\x55" * 40, b"")
                    + _arc_member(2, b"AFTER.TXT", after, after) + b"\x1a\0")
    want = extract_arc(arc)
    assert [data for _, data in want] == [b"", b"", b"", after]
    console, files = run_80un(com, arc, tmp_path / "arc", timeout=HANG)
    assert "4 file(s) extracted" in console, console
    assert sorted(files) == ["after.txt", "empty.txt", "loop.txt", "past.txt"], console
    assert files["empty.txt"] == files["loop.txt"] == files["past.txt"] == b""
    assert_same(files["after.txt"], after, "AFTER.TXT")


def test_arc_member_that_will_not_decode(com, tmp_path):
    """
    A member whose decoder fails ended the archive, although its data had been
    read through and the next header was where it should be.  src/un80 goes on.
    """
    body = b"a member after a bad one\r\n" * 6
    arc = tmp_path / "bad.arc"
    arc.write_bytes(_arc_member(4, b"BAD.TXT", struct.pack("<H", 300) + bytes(60), b"x")
                    + _arc_member(2, b"AFTER.TXT", body, body)
                    + _arc_member(2, b"LAST.TXT", body[:40], body[:40]) + b"\x1a\0")
    console, files = run_80un(com, arc, tmp_path / "bad", timeout=HANG)
    assert "Error" in console, console
    assert "2 file(s) extracted" in console, console
    want = dict(extract_arc(arc))
    assert_same(files["after.txt"], want["AFTER.TXT"], "AFTER.TXT")
    assert_same(files["last.txt"], want["LAST.TXT"], "LAST.TXT")


def test_lbr_member_of_no_sectors(com, tmp_path):
    """
    A member of no sectors made no file, but its name was taken all the same,
    so a later member of that name came out as DUP-1.TXT with no DUP.TXT.
    src/un80 writes an empty DUP.TXT and then DUP_1.TXT.
    """
    second = b"the second DUP.TXT\r\n".ljust(128, b"\x1a")
    lbr = tmp_path / "zero.lbr"
    lbr.write_bytes(_lbr([("DUP", "TXT", b""), ("DUP", "TXT", second), ("LAST", "TXT", b"")]))
    assert extract_lbr(lbr) == [("DUP.TXT", b""), ("DUP_1.TXT", second), ("LAST.TXT", b"")]
    console, files = run_80un(com, lbr, tmp_path / "zero")
    assert "DUP.TXT -> DUP-1.TXT OK" in console, console
    assert "3 file(s) extracted" in console, console
    assert files == {"dup.txt": b"", "dup-1.txt": second, "last.txt": b""}, console


def test_member_named_like_the_archive(com, tmp_path):
    """
    A member made under the archive's own name deleted the archive while it
    was being read, and wrote itself in its place.  The name is taken now.
    """
    body = b"I am not the archive\r\n" * 30
    other = b"the member after it\r\n" * 3
    arc = tmp_path / "self.arc"
    arc.write_bytes(_arc_member(2, b"SELF.ARC", body, body)
                    + _arc_member(2, b"OTHER.TXT", other, other) + b"\x1a\0")
    keep = {}
    console, files = run_80un(com, arc, tmp_path / "arc", keep=keep)
    assert keep["archive"] == arc.read_bytes(), console
    assert "SELF.ARC -> SELF-1.ARC OK" in console, console
    assert sorted(files) == ["other.txt", "self-1.arc"], console
    assert_same(files["self-1.arc"], body, "SELF-1.ARC")

    padded = body.ljust(768, b"\x1a")
    lbr = tmp_path / "self.lbr"
    lbr.write_bytes(_lbr([("SELF", "LBR", padded), ("OTHER", "TXT", other)]))
    keep = {}
    console, files = run_80un(com, lbr, tmp_path / "lbr", keep=keep)
    assert keep["archive"] == lbr.read_bytes(), console
    assert "SELF.LBR -> SELF-1.LBR OK" in console, console
    assert files == {"self-1.lbr": padded, "other.txt": other.ljust(128, b"\x1a")}, console


def _tpa(com: Path, entry: int, dest: Path) -> Path:
    """A copy of COM that finds the BDOS entry at ENTRY, as on a smaller system:
    its first instruction, LD HL,(6), jumps to a stub that puts JP 0FD00H,
    cpmemu's BDOS, at ENTRY and ENTRY at 0006H, and then does LD HL,(6)."""
    image = bytearray(com.read_bytes())
    if image[:3] != b"\x2a\x06\x00":
        pytest.skip("80un.com does not begin LD HL,(6)")
    stub = 0x100 + len(image)
    lo, hi, lo1, hi1 = entry & 0xFF, entry >> 8, (entry + 1) & 0xFF, (entry + 1) >> 8
    image[:3] = bytes([0xC3, stub & 0xFF, stub >> 8])
    image += bytes([0x3E, 0xC3, 0x32, lo, hi, 0x21, 0x00, 0xFD, 0x22, lo1, hi1,
                    0x21, lo, hi, 0x22, 0x06, 0x00, 0x2A, 0x06, 0x00, 0xC3, 0x03, 0x01])
    dest.write_bytes(bytes(image))
    return dest


def test_many_members_and_the_bdos(com, tmp_path):
    """
    The names made in a run are kept above the buffers, and nothing held them
    below the BDOS: in a 64K CP/M 2.2, BDOS entry EC06H, an ARC of more than
    about 150 members wrote them over it.  The count of files was a BYTE, so
    300 members were reported as 44.  A TPA the buffers do not fit is refused.
    """
    members = [(f"M{i:03d}.TXT".encode(), f"member {i:03d}\r\n".encode() * 2)
               for i in range(300)]
    arc = tmp_path / "many.arc"
    arc.write_bytes(b"".join(_arc_member(2, n, b, b) for n, b in members) + b"\x1a\0")
    want = {n.decode().lower(): b for n, b in members}
    for where, program in (("full", com), ("ec06", _tpa(com, 0xEC06, tmp_path / "ec06.com"))):
        console, files = run_80un(program, arc, tmp_path / where, timeout=HANG)
        assert "300 file(s) extracted" in console, (where, console)
        assert sorted(files) == sorted(want), where
        for name, data in want.items():
            assert_same(files[name], data, f"{where} {name}")

    console, files = run_80un(_tpa(com, 0xD006, tmp_path / "d006.com"), arc,
                              tmp_path / "d006", timeout=HANG)
    assert "Not enough memory" in console, console
    assert files == {}, console


def test_lbr_directory_length_is_16_bits(com, tmp_path):
    """
    The directory's length is 16 bits, and 80un read only its low byte: a
    directory of 260 (0104H) sectors was taken as 4, and 15 of its 20 members
    came out with nothing said.  src/un80 refuses it ("Invalid directory
    size"), and so does 80un now, whose buffer holds 32 sectors.  A file that
    ends inside its directory has only the entries it holds, where 80un made
    members called UNNAMED out of what its buffer held before.
    """
    members = [(f"F{i:02d}", "TXT", f"member {i:02d}\r\n".encode()) for i in range(20)]
    lbr = tmp_path / "long.lbr"
    lbr.write_bytes(_lbr(members, dsec=0x104))
    with pytest.raises(ValueError, match="Invalid directory size"):
        extract_lbr(lbr)
    console, files = run_80un(com, lbr, tmp_path / "long")
    assert "Invalid LBR file" in console, console
    assert "0 file(s) extracted" in console, console
    assert files == {}, console

    cut = tmp_path / "cut.lbr"
    cut.write_bytes(_lbr([("A", "TXT", b"a\r\n"), ("B", "TXT", b"b\r\n"),
                          ("C", "TXT", b"c\r\n")], dsec=2)[:128])
    assert extract_lbr(cut) == [("A.TXT", b""), ("B.TXT", b""), ("C.TXT", b"")]
    console, files = run_80un(com, cut, tmp_path / "cut")
    assert files == {"a.txt": b"", "b.txt": b"", "c.txt": b""}, console
