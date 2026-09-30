# Python API

## Extracting Archives

```python
from un80 import extract_lbr, extract_arc

# Extract LBR archive
# Returns list of (filename, data) tuples
files = extract_lbr("archive.lbr", "output_dir/")
for filename, data in files:
    print(f"Extracted {filename}: {len(data)} bytes")

# Extract without writing to disk
files = extract_lbr("archive.lbr")  # No output_dir
for filename, data in files:
    process(data)

# Extract with text conversion
files = extract_lbr("archive.lbr", "output/", convert_text=True)

# Extract ARC archive
files = extract_arc("archive.arc", "output_dir/")
```

## Decompressing Single Files

```python
from un80 import unsqueeze, uncrunch, uncrlzh

# Read compressed file
with open("document.tqt", "rb") as f:
    compressed = f.read()

# Decompress based on format
decompressed = unsqueeze(compressed)   # For .?q? files
decompressed = uncrunch(compressed)    # For .?z? files
decompressed = uncrlzh(compressed)     # For .?y? files

# Write decompressed data
with open("document.txt", "wb") as f:
    f.write(decompressed)
```

## Listing Archive Contents

```python
from un80.lbr import list_lbr
from un80.arc import list_arc

# List LBR contents
for entry in list_lbr("archive.lbr"):
    print(f"{entry.filename}: {entry.data_size} bytes")

# List ARC contents
for entry in list_arc("archive.arc"):
    print(f"{entry.filename}: {entry.original_size} bytes ({entry.method_name})")
```

## CP/M Text File Utilities

```python
from un80 import strip_cpm_eof, crlf_to_lf, is_text_file

# Strip ^Z EOF padding from CP/M text file
data = strip_cpm_eof(data)

# Convert CR/LF to Unix LF
data = crlf_to_lf(data)

# Check if file is likely text based on extension
if is_text_file("readme.txt"):
    data = strip_cpm_eof(data)
    data = crlf_to_lf(data)
```

## Format Detection

```python
from un80.cpm import detect_compression

with open("unknown.file", "rb") as f:
    data = f.read()

format_type = detect_compression(data)
# Returns: 'squeeze', 'crunch', 'crlzh', 'arc', 'lbr', or None
```

## Getting Original Filenames

Compressed files store the original filename in their header:

```python
from un80.squeeze import get_squeezed_filename
from un80.crunch import get_crunched_filename
from un80.crlzh import get_crlzh_filename

with open("file.tzt", "rb") as f:
    data = f.read()

original_name = get_crunched_filename(data)
print(f"Original filename: {original_name}")  # e.g., "FILE.TXT"
```
