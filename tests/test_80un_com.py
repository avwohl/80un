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


def run_80un(com: Path, archive: Path, workdir: Path, name: str | None = None):
    """Run 80un.com on a copy of ARCHIVE; return (console, {file: bytes})."""
    workdir.mkdir(parents=True, exist_ok=True)
    name = name or archive.name
    shutil.copy(archive, workdir / name)
    cfg = workdir.parent / (workdir.name + ".cfg")
    cfg.write_text(f"program = {com}\ncd = {workdir}\n"
                   "default_mode = binary\neol_convert = false\n")
    done = subprocess.run([CPMEMU, str(cfg), name.upper()], capture_output=True,
                          text=True, errors="replace", timeout=300,
                          stdin=subprocess.DEVNULL)
    (workdir / name).unlink()
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
