# 80un

Unpacker for CP/M compression and packing formats used on the 8080/Z80.

## Installation

```bash
pip install 80un
```

## Supported Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| LBR | .lbr | Library archive (like tar) |
| ARC | .arc | Compressed archive with multiple methods |
| Squeeze | .?q? | Huffman + RLE compression |
| Crunch | .?z? | LZW compression |
| CrLZH | .?y? | LZH compression |

### File Naming Conventions

CP/M used a convention where the middle letter of the extension indicated compression:
- `Q` = Squeezed (e.g., `.tqt` for a squeezed `.txt`)
- `Z` = Crunched (e.g., `.tzt` for a crunched `.txt`)
- `Y` = CrLZH (e.g., `.tyt` for an LZH-compressed `.txt`)

Files with no original extension use `.qqq`, `.zzz`, or `.yyy`.

## Usage

### Command Line

```bash
# Extract a single file
80un file.lbr

# Extract to specific directory
80un file.arc -o output_dir/

# List contents without extracting
80un file.lbr --list

# Convert text files to Unix line endings
80un file.lbr --text
```

### Python API

```python
from un80 import extract_lbr, unsqueeze, uncrunch

# Extract LBR archive
extract_lbr("archive.lbr", "output_dir/")

# Decompress a squeezed file
data = unsqueeze(compressed_bytes)

# Decompress a crunched file
data = uncrunch(compressed_bytes)
```

## CP/M File Handling

CP/M files have some quirks that 80un handles:

- **128-byte records**: CP/M measured files in 128-byte sectors
- **^Z EOF marker**: Text files ended with Ctrl-Z (0x1A) if they didn't fill the last sector
- **CR/LF line endings**: Text files used DOS-style line endings

Use `--text` to automatically strip ^Z padding and convert to Unix line endings.

## License

MIT
