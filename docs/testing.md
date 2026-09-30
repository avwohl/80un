# Test Files and Coverage

Sample archives for testing can be found at:

- [Zimmers.net CP/M Archivers](https://www.zimmers.net/anonftp/pub/cpm/archivers/) - ARK, LBR, CrLZH tools and archives
- [Chaos Cottage BBS CP/M Files](https://www.chiark.greenend.org.uk/~jacobn/cpm/cpmfiles.html) - Various CP/M archives including ARK and LZH samples

## Test Coverage Gaps

The test suite needs additional sample files to achieve complete coverage:

| Format | What's Tested | What's Missing |
|--------|---------------|----------------|
| **Squeeze** | ✅ Complete, checked against the header checksum | - |
| **Crunch** | ✅ V2.x (siglevel ≥ 0x20) and V1.x (siglevel up to 0x10), byte for byte against UNCR24.COM | V1.x siglevel 0x11-0x1F, which UNCR24 refuses too |
| **CrLZH** | ✅ V1.x and V2.0 | - |
| **ARC** | ✅ Methods 2, 3, 8, 9, checked against each member's CRC-16: all 48 members of the five sample archives pass | Methods 1, 4-7 (stored old, squeezed, old crunched) have no sample archive |
| **LBR** | ✅ Archive with nested compression | - |
| **MBASIC** | ✅ Standard (0xFF) and Protected (0xFE) | - |

`tests/test_80un_com.py` runs the CP/M program itself: it builds `80un.com`
with the uplm80 on PATH (or `$UPLM80`) in a scratch directory, runs it under
cpmemu, and compares what it writes with `src/un80`. It is skipped when the
toolchain or cpmemu (`$CPMEMU`, PATH, or `~/src/cpmemu/src/cpmemu`) is missing.

Crunch expectations are ground truth rather than recorded behaviour:
`tests/samples/lbr/mouse.lbr` carries `UNCR24.COM`, the original CP/M
uncruncher, so the expected output is what that program produces when run under
cpmemu. ARC and squeeze are checked against the CRC-16 and the 16-bit checksum
those formats already store. The one Crunch V1 sample, `zex-sage.dzc`, is checked
against UNCR24's output too, and against the byte sum crunch stores after its
end code.

Use `-v` with `-l` to check file versions: `80un file.czm -l -v`

Contributions of test files with missing versions/methods are welcome.
