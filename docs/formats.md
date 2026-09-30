# Supported Formats

80un reads the archive and compression formats below. The same formats work in the Python version and in `80un.com`.

## Archive Formats (contain multiple files)

| Format | Extensions | Description |
|--------|------------|-------------|
| **LBR** | `.lbr`, `.lqr`, `.lzr` | Library archive, similar to tar. Files inside may be compressed individually. |
| **ARC** | `.arc`, `.ark` | Compressed archive supporting multiple compression methods (stored, packed, squeezed, crunched, squashed). |

## Compression Formats (single file)

| Format | Extensions | Magic Bytes | Description |
|--------|------------|-------------|-------------|
| **Squeeze** | `.?q?` | `76 FF` | Huffman coding with run-length encoding. Devised by Richard Greenlaw, 1981. |
| **Crunch** | `.?z?` | `76 FE` | LZW compression similar to Unix compress. More efficient than squeeze. |
| **CrLZH** | `.?y?` | `76 FD` | LZH compression (Lempel-Ziv + Huffman). Most efficient CP/M compression. |

## CP/M File Naming Convention

CP/M used 8.3 filenames. Compressed files indicated their compression by replacing the **middle letter** of the extension:

| Original | Squeezed | Crunched | CrLZH |
|----------|----------|----------|-------|
| `FILE.TXT` | `FILE.TQT` | `FILE.TZT` | `FILE.TYT` |
| `FILE.COM` | `FILE.CQM` | `FILE.CZM` | `FILE.CYM` |
| `FILE.ASM` | `FILE.AQM` | `FILE.AZM` | `FILE.AYM` |
| `FILE.DOC` | `FILE.DQC` | `FILE.DZC` | `FILE.DYC` |

Files with no extension used `.QQQ`, `.ZZZ`, or `.YYY`.

## ARC Compression Methods

ARC archives can contain files compressed with different methods:

| Method | Name | Description |
|--------|------|-------------|
| 1 | Stored (old) | No compression (obsolete) |
| 2 | Stored | No compression |
| 3 | Packed | Run-length encoding only |
| 4 | Squeezed | Huffman coding after RLE |
| 5 | Crunched (old) | 12-bit LZW (obsolete) |
| 6 | Crunched+RLE | 12-bit LZW with RLE (obsolete) |
| 7 | Crunched | LZW with faster hash |
| 8 | Crunched | 9-12 bit LZW (most common) |
| 9 | Squashed | 13-bit LZW (Phil Katz) |

## CP/M File Handling

CP/M files have characteristics that differ from modern systems:

### 128-Byte Records

CP/M measured file sizes in 128-byte records (sectors), not bytes. A file's actual byte length wasn't stored; only the record count. This means:

- Files are always multiples of 128 bytes
- The last record may contain padding

### ^Z End-of-File Marker

Text files that didn't fill their last 128-byte record were padded. The convention was to mark the end of actual content with a Ctrl-Z character (0x1A), with the remainder filled with more ^Z characters or garbage.

Use `--text` or `strip_cpm_eof()` to remove this padding.

### CR/LF Line Endings

CP/M text files used CR/LF (carriage return + line feed, 0x0D 0x0A) line endings, like DOS/Windows. Use `--text` or `crlf_to_lf()` to convert to Unix-style LF endings.

## History

These compression formats were developed in the early 1980s for CP/M systems:

- **1981**: Squeeze (SQ/USQ) by Richard Greenlaw - first widely-used CP/M compression
- **1984**: LBR format by Gary P. Novosielski - library/archive format
- **1985**: ARC by System Enhancement Associates - compressed archives
- **1985**: Crunch - LZW compression, more efficient than squeeze
- **1986**: Crunch v2.0 - improved with "metastatic code reassignment"
- **Late 1980s**: CrLZH - LZH compression, most efficient
