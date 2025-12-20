#!/usr/bin/env python3
"""
Command-line interface for 80un.

Usage:
    80un file.lbr                 # Extract archive
    80un file.arc -o output/      # Extract to directory
    80un file.lbr --list          # List contents
    80un file.tqt                 # Decompress single file
    80un file.bas                 # Detokenize MBASIC file
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
from .crunch import uncrunch, get_crunched_filename, get_crunch_info
from .crlzh import uncrlzh, get_crlzh_filename, get_crlzh_info
from .bas import is_tokenized_basic, is_protected_basic, detokenize_bytes


def detect_format(path: Path) -> str | None:
    """Detect file format from content and extension."""
    with open(path, 'rb') as f:
        header = f.read(32)

    compression = detect_compression(header)
    if compression:
        return compression

    # Check for tokenized BASIC (0xFF magic byte with .bas extension)
    ext = path.suffix.lower()
    if ext == '.bas' and is_tokenized_basic(header):
        return 'bas'

    # Fall back to extension
    if ext in ('.lbr', '.lqr', '.lzr'):
        return 'lbr'
    if ext in ('.arc', '.ark'):
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
        if ext in ('.qqq', '.zzz', '.yyy'):
            return stem  # No extension
        return stem + '.' + new_ext

    return stem + '.out'


def cmd_list(path: Path, format_type: str, verbose: bool = False) -> int:
    """List archive contents."""
    if format_type == 'lbr':
        entries = list_lbr(path)
        if verbose:
            print(f"{'Filename':<16} {'Size':>8} {'Sectors':>8} {'Compression':<16}")
            print('-' * 52)
        else:
            print(f"{'Filename':<16} {'Size':>8} {'Sectors':>8}")
            print('-' * 36)
        for entry in entries:
            size = entry.data_size
            if verbose:
                # Detect compression type of member
                member_data = entry.get_data(path) if hasattr(entry, 'get_data') else None
                if member_data:
                    comp = detect_compression(member_data)
                    comp_str = comp if comp else 'stored'
                else:
                    comp_str = '?'
                print(f"{entry.filename:<16} {size:>8} {entry.length:>8} {comp_str:<16}")
            else:
                print(f"{entry.filename:<16} {size:>8} {entry.length:>8}")
        print(f"\n{len(entries)} file(s)")

    elif format_type == 'arc':
        entries = list_arc(path)
        if verbose:
            print(f"{'Filename':<16} {'Original':>10} {'Compressed':>12} {'Method':<16}")
            print('-' * 58)
            for entry in entries:
                method_detail = f"{entry.method}: {entry.method_name}"
                print(f"{entry.filename:<16} {entry.original_size:>10} "
                      f"{entry.compressed_size:>12} {method_detail:<16}")
        else:
            print(f"{'Filename':<16} {'Original':>10} {'Compressed':>12} {'Method':<12}")
            print('-' * 54)
            for entry in entries:
                print(f"{entry.filename:<16} {entry.original_size:>10} "
                      f"{entry.compressed_size:>12} {entry.method_name:<12}")
        print(f"\n{len(entries)} file(s)")

    elif format_type in ('squeeze', 'crunch', 'crlzh'):
        # Show info for single compressed file
        with open(path, 'rb') as f:
            data = f.read()

        if format_type == 'squeeze':
            name = get_squeezed_filename(data)
            print(f"Format: Squeeze (Huffman + RLE)")
            print(f"Original filename: {name or 'unknown'}")

        elif format_type == 'crunch':
            info = get_crunch_info(data)
            if info:
                print(f"Format: Crunch {info['description']}")
                print(f"Original filename: {info['filename']}")
                if verbose:
                    print(f"Siglevel: 0x{info['siglevel']:02X}")
                    print(f"Code bits: {info['bits']}")
            else:
                print(f"Format: Crunch (cannot parse header)")

        elif format_type == 'crlzh':
            info = get_crlzh_info(data)
            if info:
                print(f"Format: CrLZH {info['description']}")
                print(f"Original filename: {info['filename']}")
                if verbose:
                    print(f"Version byte: 0x{info['version']:02X}")
                    print(f"Position bits: {info['position_bits']}")
            else:
                print(f"Format: CrLZH (cannot parse header)")

    elif format_type == 'bas':
        with open(path, 'rb') as f:
            data = f.read()

        if is_protected_basic(data):
            print(f"Format: MBASIC Protected (0xFE)")
            print(f"Status: Encrypted with 143-byte XOR cycle")
        elif is_tokenized_basic(data):
            print(f"Format: MBASIC Tokenized (0xFF)")
            print(f"Status: Binary tokenized")
        else:
            print(f"Format: MBASIC ASCII")
            print(f"Status: Plain text source")

    else:
        print(f"Cannot list contents of {format_type} files", file=sys.stderr)
        return 1

    return 0


def safe_write(out_path: Path, data: bytes, no_clobber: bool) -> tuple[Path, str]:
    """
    Safely write data to a file, handling overwrites.

    Returns (actual_path, status) where status is 'wrote', 'skipped', or 'overwrote'.
    """
    if not out_path.exists():
        out_path.write_bytes(data)
        return out_path, 'wrote'

    if no_clobber:
        return out_path, 'skipped'

    # File exists and we're allowed to overwrite
    out_path.write_bytes(data)
    return out_path, 'overwrote'


def get_unique_path_for_archive(out_path: Path, used_names: set[str]) -> Path:
    """
    Get a unique filename, avoiding conflicts with names already used in this extraction.

    This handles duplicate filenames WITHIN an archive (e.g., two files named README.TXT).
    Appends _1, _2, etc. to the stem until a unique name is found.

    Note: This only checks used_names, not existing files on disk (that's handled by safe_write).
    """
    original = out_path
    counter = 1

    while str(out_path) in used_names:
        stem = original.stem
        suffix = original.suffix
        out_path = original.parent / f"{stem}_{counter}{suffix}"
        counter += 1

    return out_path


def cmd_extract(
    path: Path,
    output_dir: Path | None,
    format_type: str,
    convert_text: bool,
    no_clobber: bool = False,
) -> int:
    """Extract archive or decompress file."""
    extracted = 0
    skipped = 0
    overwrote = 0

    if format_type == 'lbr':
        results = extract_lbr(path, None, convert_text=convert_text)  # Extract to memory first
        used_names: set[str] = set()

        for filename, data in results:
            if output_dir:
                out_path = output_dir / filename
            else:
                out_path = path.parent / filename

            # Handle duplicate names within archive
            out_path = get_unique_path_for_archive(out_path, used_names)
            used_names.add(str(out_path))

            actual_path, status = safe_write(out_path, data, no_clobber)

            if status == 'skipped':
                print(f"  {filename} (skipped, already exists)")
                skipped += 1
            elif status == 'overwrote':
                print(f"  {filename} (overwrote)")
                overwrote += 1
            else:
                if actual_path.name != filename:
                    print(f"  {filename} -> {actual_path.name}")
                else:
                    print(f"  {filename}")
                extracted += 1

        _print_extract_summary(extracted, skipped, overwrote)

    elif format_type == 'arc':
        results = extract_arc(path, None, convert_text=convert_text)
        used_names = set()

        for filename, data in results:
            if output_dir:
                out_path = output_dir / filename
            else:
                out_path = path.parent / filename

            out_path = get_unique_path_for_archive(out_path, used_names)
            used_names.add(str(out_path))

            actual_path, status = safe_write(out_path, data, no_clobber)

            if status == 'skipped':
                print(f"  {filename} (skipped, already exists)")
                skipped += 1
            elif status == 'overwrote':
                print(f"  {filename} (overwrote)")
                overwrote += 1
            else:
                if actual_path.name != filename:
                    print(f"  {filename} -> {actual_path.name}")
                else:
                    print(f"  {filename}")
                extracted += 1

        _print_extract_summary(extracted, skipped, overwrote)

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

        actual_path, status = safe_write(out_path, result, no_clobber)

        if status == 'skipped':
            print(f"  {out_name} (skipped, already exists)")
        elif status == 'overwrote':
            print(f"  {out_name} ({len(result)} bytes, overwrote)")
        else:
            print(f"  {out_name} ({len(result)} bytes)")

    elif format_type == 'bas':
        # Detokenize MBASIC file
        with open(path, 'rb') as f:
            data = f.read()

        result = detokenize_bytes(data)

        # Output keeps same name (still .bas, but now ASCII)
        out_name = path.name
        if output_dir:
            out_path = output_dir / out_name
        else:
            out_path = path.parent / out_name

        actual_path, status = safe_write(out_path, result, no_clobber)

        if status == 'skipped':
            print(f"  {out_name} (skipped, already exists)")
        elif status == 'overwrote':
            print(f"  {out_name} (detokenized, {len(result)} bytes, overwrote)")
        else:
            print(f"  {out_name} (detokenized, {len(result)} bytes)")

    else:
        print(f"Unknown format: {format_type}", file=sys.stderr)
        return 1

    return 0


def _print_extract_summary(extracted: int, skipped: int, overwrote: int) -> None:
    """Print extraction summary."""
    parts = []
    if extracted:
        parts.append(f"{extracted} extracted")
    if skipped:
        parts.append(f"{skipped} skipped")
    if overwrote:
        parts.append(f"{overwrote} overwrote")

    total = extracted + skipped + overwrote
    if parts:
        print(f"\n{total} file(s): {', '.join(parts)}")
    else:
        print(f"\n{total} file(s)")


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
        choices=['lbr', 'arc', 'squeeze', 'crunch', 'crlzh', 'bas'],
        help='Force file format (auto-detected by default)',
    )
    parser.add_argument(
        '-n', '--no-clobber',
        action='store_true',
        help='Do not overwrite existing files',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed version/method info',
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
            return cmd_list(args.file, format_type, args.verbose)
        else:
            return cmd_extract(args.file, args.output, format_type, args.text, args.no_clobber)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
