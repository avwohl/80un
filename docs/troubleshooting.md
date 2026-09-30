# Troubleshooting

## "Cannot determine format"

The file doesn't have a recognized magic number or extension. Try specifying the format manually:

```bash
80un mystery.dat -f crunch
```

## Garbled output from text files

The file may still have CP/M formatting. Use the `--text` option:

```bash
80un archive.lbr -t
```

## "Invalid magic" or decompression errors

The file may be corrupted, truncated, or not actually in the detected format. Try:

1. Verify the file is complete
2. Try a different format with `-f`
3. Check if it's a different vintage format not yet supported

## CrLZH decompression produces partial or garbled output

CrLZH uses a complex LZSS algorithm with adaptive Huffman coding. If decompression fails, verify the file isn't corrupted or truncated. Both V1.x and V2.0 versions are supported.

## Files extract with wrong names

Some very old archives don't store original filenames. The tool will use the archive member name with the compression indicator removed.

A crunched file may store a note after its name, as in `MOUSE.MAC[04/01/87]` or
`COMMON.LIB[ V2.4 INCLUDE FILE]`. The note is not part of the name and is
dropped; read it with `get_crunch_info()` or `CrunchHeader.note`.

A CP/M filename may contain characters that a host filesystem treats as special,
`/` in particular, which is an ordinary filename character under CP/M.  Those
characters are replaced with `_`, so a member called `CCP/M.COM` extracts as
`CCP_M.COM`.  On CP/M, `80un.com` has a stricter rule of its own, with `-` in
place of `_` (see [Member names on CP/M](cpm_version.md#member-names-on-cpm)).

## Duplicate filenames in archive

Some archives contain multiple files with the same name (e.g., from different directories that CP/M flattened). When this happens, 80un automatically renames duplicates by appending `_1`, `_2`, etc.:

```bash
$ 80un archive_with_dupes.lbr
  README.TXT
  README.TXT -> README_1.TXT
  DATA.DAT

3 file(s): 3 extracted
```
