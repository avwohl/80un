#!/usr/bin/env python3
"""
Command-line interface for 80un.

Usage:
    80un file.lbr                 # Extract archive
    80un file.arc -o output/      # Extract to directory
    80un file.lbr --list          # List contents
    80un file.tqt                 # Decompress single file
    80un file.txt --text          # Convert text file endings
"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .cpm import detect_compression, strip_cpm_eof, crlf_to_lf
from .lbr import list_lbr, extract_lbr
from .arc import list_arc, extract_arc
from .squeeze import unsqueeze, get_squeezed_filename
from .crunch import uncrunch, get_crunched_filename
from .crlzh import uncrlzh, get_crlzh_filename


def detect_format(path: Path) -> str | None:
    """Detect file format from content and extension."""
    with open(path, 'rb') as f:
        header = f.read(32)

    compression = detect_compression(header)
    if compression:
        return compression

    # Fall back to extension
    ext = path.suffix.lower()
    if ext == '.lbr' or ext == '.lqr' or ext == '.lzr':
        return 'lbr'
    if ext == '.arc' or ext == '.ark':
        return 'arc'

    # Check for squeezed/crunched by middle letter
    if len(ext) == 4:
        mid = ext[2].lower()
        if mid == 'q':
            return 'squeeze'
        if mid == 'z':
            return 'crunch'
        if mid == 'y':
            return 'crlzh'

    return None


def get_output_filename(path: Path, compression: str) -> str:
    """Get the decompressed output filename."""
    # Try to get embedded filename
    with open(path, 'rb') as f:
        data = f.read()

    if compression == 'squeeze':
        name = get_squeezed_filename(data)
        if name:
            return name
    elif compression == 'crunch':
        name = get_crunched_filename(data)
        if name:
            return name
    elif compression == 'crlzh':
        name = get_crlzh_filename(data)
        if name:
            return name

    # Reconstruct from extension
    stem = path.stem
    ext = path.suffix.lower()

    if len(ext) == 4 and ext[2] in 'qzy':
        # .tqt -> .txt, etc.
        new_ext = ext[1] + ext[1] + ext[3]
        if ext == '.qqq' or ext == '.zzz' or ext == '.yyy':
            return stem  # No extension
        return stem + '.' + new_ext

    return stem + '.out'


def cmd_list(path: Path, format_type: str) -> int:
    """List archive contents."""
    if format_type == 'lbr':
        entries = list_lbr(path)
        print(f"{'Filename':<16} {'Size':>8} {'Sectors':>8}")
        print('-' * 36)
        for entry in entries:
            size = entry.data_size
            print(f"{entry.filename:<16} {size:>8} {entry.length:>8}")
        print(f"\n{len(entries)} file(s)")

    elif format_type == 'arc':
        entries = list_arc(path)
        print(f"{'Filename':<16} {'Original':>10} {'Compressed':>12} {'Method':<12}")
        print('-' * 54)
        for entry in entries:
            print(f"{entry.filename:<16} {entry.original_size:>10} "
                  f"{entry.compressed_size:>12} {entry.method_name:<12}")
        print(f"\n{len(entries)} file(s)")

    else:
        print(f"Cannot list contents of {format_type} files", file=sys.stderr)
        return 1

    return 0


def cmd_extract(
    path: Path,
    output_dir: Path | None,
    format_type: str,
    convert_text: bool,
) -> int:
    """Extract archive or decompress file."""
    if format_type == 'lbr':
        results = extract_lbr(path, output_dir, convert_text=convert_text)
        for filename, _ in results:
            print(f"  {filename}")
        print(f"\nExtracted {len(results)} file(s)")

    elif format_type == 'arc':
        results = extract_arc(path, output_dir, convert_text=convert_text)
        for filename, _ in results:
            print(f"  {filename}")
        print(f"\nExtracted {len(results)} file(s)")

    elif format_type in ('squeeze', 'crunch', 'crlzh'):
        with open(path, 'rb') as f:
            data = f.read()

        if format_type == 'squeeze':
            result = unsqueeze(data)
        elif format_type == 'crunch':
            result = uncrunch(data)
        else:
            result = uncrlzh(data)

        if convert_text:
            result = strip_cpm_eof(result)
            result = crlf_to_lf(result)

        out_name = get_output_filename(path, format_type)
        if output_dir:
            out_path = output_dir / out_name
        else:
            out_path = path.parent / out_name

        out_path.write_bytes(result)
        print(f"  {out_name} ({len(result)} bytes)")

    else:
        print(f"Unknown format: {format_type}", file=sys.stderr)
        return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog='80un',
        description='Unpacker for CP/M compression and packing formats',
    )
    parser.add_argument(
        '--version', action='version', version=f'%(prog)s {__version__}'
    )
    parser.add_argument(
        'file',
        type=Path,
        help='File to extract or decompress',
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        metavar='DIR',
        help='Output directory',
    )
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List contents without extracting',
    )
    parser.add_argument(
        '-t', '--text',
        action='store_true',
        help='Convert text files (strip ^Z, CR/LF to LF)',
    )
    parser.add_argument(
        '-f', '--format',
        choices=['lbr', 'arc', 'squeeze', 'crunch', 'crlzh'],
        help='Force file format (auto-detected by default)',
    )

    args = parser.parse_args(argv)

    if not args.file.exists():
        print(f"File not found: {args.file}", file=sys.stderr)
        return 1

    # Detect format
    format_type = args.format or detect_format(args.file)
    if not format_type:
        print(f"Cannot determine format of: {args.file}", file=sys.stderr)
        print("Use --format to specify the format", file=sys.stderr)
        return 1

    # Create output directory if needed
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)

    try:
        if args.list:
            return cmd_list(args.file, format_type)
        else:
            return cmd_extract(args.file, args.output, format_type, args.text)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
