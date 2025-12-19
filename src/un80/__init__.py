"""
80un - Unpacker for CP/M compression and packing formats

Supports:
- .lbr - Library archives (like tar)
- .arc - ARC compressed archives
- .?q? - Squeezed files (Huffman + RLE)
- .?z? - Crunched files (LZW)
- .?y? - CrLZH files (LZH)
"""

__version__ = "0.2.2"

from .squeeze import unsqueeze
from .crunch import uncrunch
from .lbr import extract_lbr
from .arc import extract_arc
from .crlzh import uncrlzh
from .cpm import strip_cpm_eof, crlf_to_lf, is_text_file

__all__ = [
    "unsqueeze",
    "uncrunch",
    "uncrlzh",
    "extract_lbr",
    "extract_arc",
    "strip_cpm_eof",
    "crlf_to_lf",
    "is_text_file",
]
