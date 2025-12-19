"""
MBASIC tokenized BASIC file detokenizer.

This module converts tokenized MBASIC-80 programs (.BAS files starting with 0xFF)
back to ASCII text format. Also handles protected/encrypted files (0xFE magic).

Based on the MBASIC 5.21 token tables.
Protected file decryption based on w4jbm/MBASIC-Protect research.
"""

from io import StringIO
from typing import Dict

# Magic bytes for tokenized MBASIC files
MBASIC_MAGIC = 0xFF
MBASIC_PROTECTED_MAGIC = 0xFE

# SINCON and ATNCON tables from MBASIC ROM (used for protection XOR)
# These are the sine and arctangent coefficient tables reused as encryption keys
SINCON = [5, 251, 215, 30, 134, 101, 38, 153, 135, 88, 52, 35, 135, 225, 93, 165]
ATNCON = [9, 74, 215, 59, 120, 2, 110, 132, 123, 254, 193, 47, 124, 116, 49, 154]


def is_tokenized_basic(data: bytes) -> bool:
    """Check if data is a tokenized MBASIC file (protected or unprotected)."""
    return len(data) > 0 and data[0] in (MBASIC_MAGIC, MBASIC_PROTECTED_MAGIC)


def is_protected_basic(data: bytes) -> bool:
    """Check if data is a protected/encrypted MBASIC file."""
    return len(data) > 0 and data[0] == MBASIC_PROTECTED_MAGIC


def unprotect(data: bytes) -> bytes:
    """
    Decrypt a protected MBASIC file.

    MBASIC's SAVE "file",P command encrypts the program using a 143-byte
    repeating XOR pattern derived from the SINCON (13 values) and ATNCON
    (11 values) tables in the BASIC ROM.

    Args:
        data: Protected file data (starting with 0xFE)

    Returns:
        Decrypted data (with 0xFF magic byte)
    """
    if not is_protected_basic(data):
        return data  # Not protected, return as-is

    result = bytearray(len(data))
    result[0] = MBASIC_MAGIC  # Replace 0xFE with 0xFF

    # Counters cycle: A 13->1, B 11->1 (1-indexed as in original BASIC)
    # These are used both as counter values in arithmetic AND as array indices
    A = 13  # SINCON counter/index (cycles 13 down to 1, resets to 13)
    B = 11  # ATNCON counter/index (cycles 11 down to 1, resets to 11)

    for i in range(1, len(data)):
        x = data[i]

        # Decryption formula from UNPRO2.BAS:
        # H% = (X% - B% + 256) MOD 256
        # H% = H% XOR (SN%(A%) XOR AN%(B%))
        # H% = (H% + A%) MOD 256
        h = (x - B + 256) % 256
        h = h ^ (SINCON[A] ^ ATNCON[B])
        h = (h + A) % 256

        result[i] = h

        # Decrement counters with wraparound (13->1, 11->1)
        A -= 1
        if A == 0:
            A = 13
        B -= 1
        if B == 0:
            B = 11

    return bytes(result)


def two_neg_power32(exponent: int) -> float:
    """Calculate 2^(-exponent) for 32-bit floats."""
    value = 2.0
    f = 1.0
    if exponent == 0:
        return f
    while exponent > 0:
        f = value * f
        exponent -= 1
    return 1.0 / f


def two_neg_power64(exponent: int) -> float:
    """Calculate 2^(-exponent) for 64-bit floats."""
    value = 2.0
    f = 1.0
    if exponent == 0:
        return f
    while exponent > 0:
        f = value * f
        exponent -= 1
    return 1.0 / f


def _needs_space_before(token: str, prev_token: str) -> bool:
    """Determine if we need a space before this token."""
    if not prev_token:
        return False

    # If previous token was a space, don't add another
    if prev_token == ' ':
        return False

    operators = {'+', '-', '*', '/', '^', '\\', '=', '<', '>', '(', ')', ',', ';', ':', '$', '%', '!', '#'}

    if token == "ARK" and prev_token == "REM":
        return False

    if token in operators:
        return False

    if token and token[0] in operators:
        return False

    if prev_token in operators and prev_token not in {')', '}'}:
        return False

    if prev_token and prev_token[-1] == '(':
        return False

    # If previous token was a digit/number, need space before keywords
    if prev_token and prev_token[-1].isdigit():
        keywords_after_number = {
            'TO', 'STEP', 'THEN', 'ELSE', 'AND', 'OR', 'XOR', 'MOD',
            'EQV', 'IMP', 'NOT', 'GOTO', 'GOSUB'
        }
        if token in keywords_after_number:
            return True

    # Keywords that already add space after themselves
    keywords_with_trailing_space = {
        'FOR', 'TO', 'STEP', 'IF', 'THEN', 'ELSE', 'WHILE', 'WEND',
        'GOTO', 'GOSUB', 'ON', 'LET', 'DIM', 'INPUT', 'READ', 'DATA',
        'PRINT', 'LPRINT', 'OPEN', 'CLOSE', 'FIELD', 'GET', 'PUT',
        'NEXT', 'RETURN', 'STOP', 'END', 'CONT', 'CLEAR', 'RUN',
        'NEW', 'LIST', 'LLIST', 'DELETE', 'AUTO', 'RENUM', 'SAVE',
        'LOAD', 'MERGE', 'FILES', 'KILL', 'NAME', 'CHAIN', 'COMMON',
        'OPTION', 'RANDOMIZE', 'ERASE', 'ERROR', 'RESUME', 'RESTORE',
        'SWAP', 'DEF', 'DEFSTR', 'DEFINT', 'DEFSNG', 'DEFDBL',
        'TRON', 'TROFF', 'WAIT', 'POKE', 'OUT', 'WIDTH', 'LINE',
        'WRITE', 'LSET', 'RSET', 'RESET', 'CALL', 'SYSTEM',
        'NOT', 'AND', 'OR', 'XOR', 'MOD', 'IMP', 'EQV',
        'AS', 'USING', 'BASE'
    }
    if prev_token in keywords_with_trailing_space:
        return False

    return True


def _needs_space_after(token: str, next_byte: int | None) -> bool:
    """Determine if we need a space after this token."""
    if next_byte is None or next_byte == 0x00:
        return False

    if next_byte == 0x20:  # Already a space
        return False

    keywords_needing_space = {
        'FOR', 'TO', 'STEP', 'IF', 'THEN', 'ELSE', 'WHILE', 'WEND',
        'GOTO', 'GOSUB', 'ON', 'LET', 'DIM', 'INPUT', 'READ', 'DATA',
        'PRINT', 'LPRINT', 'OPEN', 'CLOSE', 'FIELD', 'GET', 'PUT',
        'NEXT', 'RETURN', 'STOP', 'END', 'CONT', 'CLEAR', 'RUN',
        'NEW', 'LIST', 'LLIST', 'DELETE', 'AUTO', 'RENUM', 'SAVE',
        'LOAD', 'MERGE', 'FILES', 'KILL', 'NAME', 'CHAIN', 'COMMON',
        'OPTION', 'RANDOMIZE', 'ERASE', 'ERROR', 'RESUME', 'RESTORE',
        'SWAP', 'DEF', 'DEFSTR', 'DEFINT', 'DEFSNG', 'DEFDBL',
        'TRON', 'TROFF', 'WAIT', 'POKE', 'OUT', 'WIDTH', 'LINE',
        'WRITE', 'LSET', 'RSET', 'RESET', 'CALL', 'SYSTEM',
        'NOT', 'AND', 'OR', 'XOR', 'MOD', 'IMP', 'EQV',
        'AS', 'USING', 'BASE'
    }

    no_space_after = {
        ':', ',', ';', '(', ')',
        '+', '-', '*', '/', '\\', '^',
        '=', '<', '>',
        '$', '%', '!', '#',
        'TAB(', 'SPC(', 'FN'
    }

    if token in no_space_after:
        return False

    # Operators/delimiters: no space needed before them
    next_is_operator = next_byte in {
        0x3A, 0x2C, 0x3B, 0x28, 0x29, 0x3D, 0x3C, 0x3E,
        0x2B, 0x2D, 0x2A, 0x2F, 0x5C, 0x5E, 0x24, 0x25, 0x21, 0x23,
    }

    next_is_token_operator = next_byte in {
        0xEF, 0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6,
        0xF7, 0xF8, 0xF9, 0xFA,
    }

    if next_is_operator or next_is_token_operator:
        return False

    if token in keywords_needing_space:
        return True

    if token == 'REM' and next_byte == 0xDB:
        return False

    return False


def _build_tables() -> tuple[Dict[int, str], Dict[int, str]]:
    """Build the MBASIC token tables."""
    table: Dict[int, str] = {}

    table[0x81] = "END"
    table[0x82] = "FOR"
    table[0x83] = "NEXT"
    table[0x84] = "DATA"
    table[0x85] = "INPUT"
    table[0x86] = "DIM"
    table[0x87] = "READ"
    table[0x88] = "LET"
    table[0x89] = "GOTO"
    table[0x8A] = "RUN"
    table[0x8B] = "IF"
    table[0x8C] = "RESTORE"
    table[0x8D] = "GOSUB"
    table[0x8E] = "RETURN"
    table[0x8F] = "REM"
    table[0x90] = "STOP"
    table[0x91] = "PRINT"
    table[0x92] = "CLEAR"
    table[0x93] = "LIST"
    table[0x94] = "NEW"
    table[0x95] = "ON"
    table[0x96] = "NULL"
    table[0x97] = "WAIT"
    table[0x98] = "DEF"
    table[0x99] = "POKE"
    table[0x9A] = "CONT"
    table[0x9B] = "LPRINT"
    table[0x9D] = "OUT"
    table[0x9F] = "LLIST"
    table[0xA0] = "NOTRACE"
    table[0xA1] = "WIDTH"
    table[0xA2] = "ELSE"
    table[0xA3] = "TRON"
    table[0xA4] = "TROFF"
    table[0xA5] = "SWAP"
    table[0xA6] = "ERASE"
    table[0xA7] = "EDIT"
    table[0xA8] = "ERROR"
    table[0xA9] = "RESUME"
    table[0xAA] = "DELETE"
    table[0xAB] = "AUTO"
    table[0xAC] = "RENUM"
    table[0xAD] = "DEFSTR"
    table[0xAE] = "DEFINT"
    table[0xAF] = "DEFSNG"
    table[0xB0] = "DEFDBL"
    table[0xB1] = "LINE"
    table[0xB2] = "WRITE"
    table[0xB3] = "COMMON"
    table[0xB4] = "WHILE"
    table[0xB5] = "WEND"
    table[0xB6] = "CALL"
    table[0xB7] = "WRITE"
    table[0xB8] = "COMMON"
    table[0xB9] = "CHAIN"
    table[0xBA] = "OPTION"
    table[0xBB] = "RANDOMIZE"
    table[0xBD] = "SYSTEM"
    table[0xBE] = "MERGE"
    table[0xBF] = "OPEN"
    table[0xC0] = "FIELD"
    table[0xC1] = "GET"
    table[0xC2] = "PUT"
    table[0xC3] = "CLOSE"
    table[0xC4] = "LOAD"
    table[0xC5] = "MERGE"
    table[0xC6] = "FILES"
    table[0xC7] = "NAME"
    table[0xC8] = "KILL"
    table[0xC9] = "LSET"
    table[0xCA] = "RSET"
    table[0xCB] = "SAVE"
    table[0xCC] = "RESET"
    table[0xCE] = "TO"
    table[0xCF] = "THEN"
    table[0xD0] = "TAB("
    table[0xD1] = "STEP"
    table[0xD2] = "USR"
    table[0xD3] = "FN"
    table[0xD4] = "SPC("
    table[0xD5] = "NOT"
    table[0xD6] = "ERL"
    table[0xD7] = "ERR"
    table[0xD8] = "STRING$"
    table[0xD9] = "USING"
    table[0xDA] = "INSTR"
    table[0xDB] = "ARK"
    table[0xDC] = "VARPTR"
    table[0xDD] = "INKEY$"
    table[0xEF] = ">"
    table[0xF0] = "="
    table[0xF1] = "<"
    table[0xF2] = "+"
    table[0xF3] = "-"
    table[0xF4] = "*"
    table[0xF5] = "/"
    table[0xF6] = "^"
    table[0xF7] = "AND"
    table[0xF8] = "OR"
    table[0xF9] = "XOR"
    table[0xFA] = "EQV"
    table[0xFB] = "IMP"
    table[0xFC] = "\\"
    table[0xFD] = "MOD"

    table2: Dict[int, str] = {}

    table2[0x81] = "LEFT$"
    table2[0x82] = "RIGHT$"
    table2[0x83] = "MID$"
    table2[0x84] = "SGN"
    table2[0x85] = "INT"
    table2[0x86] = "ABS"
    table2[0x87] = "SQR"
    table2[0x88] = "RND"
    table2[0x89] = "SIN"
    table2[0x8A] = "LOG"
    table2[0x8B] = "EXP"
    table2[0x8C] = "COS"
    table2[0x8D] = "TAN"
    table2[0x8E] = "ATN"
    table2[0x8F] = "FRE"
    table2[0x90] = "INP"
    table2[0x91] = "POS"
    table2[0x92] = "LEN"
    table2[0x93] = "STR$"
    table2[0x94] = "VAL"
    table2[0x95] = "ASC"
    table2[0x96] = "CHR$"
    table2[0x97] = "PEEK"
    table2[0x98] = "SPACE$"
    table2[0x99] = "OCT$"
    table2[0x9A] = "HEX$"
    table2[0x9B] = "LPOS"
    table2[0x9C] = "CINT"
    table2[0x9D] = "CSNG"
    table2[0x9E] = "CDBL"
    table2[0x9F] = "FIX"
    table2[0xAB] = "CVI"
    table2[0xAC] = "CVS"
    table2[0xAD] = "CVD"
    table2[0xAE] = "EOF"
    table2[0xB0] = "LOC"
    table2[0xB1] = "LOF"
    table2[0xB2] = "MKI$"
    table2[0xB3] = "MKS$"
    table2[0xB4] = "MKD$"

    return table, table2


def _detokenize_line(data: bytes, table: Dict[int, str], table2: Dict[int, str]) -> tuple[str, int]:
    """
    Detokenize a single line of BASIC code.

    Args:
        data: The line data (after line number bytes)
        table: 1-byte token table
        table2: 2-byte token table

    Returns:
        Tuple of (line_text, bytes_consumed)
    """
    output = StringIO()
    count = 0
    done = False
    prev_token = ""

    while not done:
        if count >= len(data):
            break
        b = data[count]
        b16 = int(b)

        handled = False

        # 0x0F - 1-byte integer as decimal
        if b == 0x0F:
            i = int(data[count + 1])
            output.write(f"{i}")
            prev_token = "0"
            count += 1
            handled = True

        # 0x0E - 2-byte integer as decimal
        if b == 0x0E:
            i = int(data[count + 2]) * 256 + int(data[count + 1])
            output.write(f"{i}")
            prev_token = "0"
            count += 2
            handled = True

        # 0x0C - 2-byte integer as hexadecimal
        if b == 0x0C:
            i = int(data[count + 2]) * 256 + int(data[count + 1])
            output.write(f"&H{i:02X}")
            prev_token = "0"
            count += 2
            handled = True

        # 0x0B - 2-byte integer as octal
        if b == 0x0B:
            i = int(data[count + 2]) * 256 + int(data[count + 1])
            output.write(f"&O{i:03o}")
            prev_token = "0"
            count += 2
            handled = True

        # 0x1C - 2-byte integer as decimal
        if b == 0x1C:
            i = int(data[count + 2]) * 256 + int(data[count + 1])
            output.write(f"{i}")
            prev_token = "0"
            count += 2
            handled = True

        # 0x1D - 4-byte float as decimal
        if b == 0x1D:
            bt1 = int(data[count + 1])
            bt2 = int(data[count + 2])
            bt3 = int(data[count + 3])
            bt4 = int(data[count + 4])

            f1a = float(bt1) * two_neg_power32(23)
            f1b = float(bt2) * two_neg_power32(15)
            f1c = float(bt3) * two_neg_power32(7)
            f1 = f1a + f1b + f1c + 1.0
            f2 = two_neg_power32(129 - bt4)
            f = f1 * f2

            output.write(f"{f:g}")
            prev_token = "0"
            count += 4
            handled = True

        # 0x1F - 8-byte float as decimal
        if b == 0x1F:
            bt1 = int(data[count + 1])
            bt2 = int(data[count + 2])
            bt3 = int(data[count + 3])
            bt4 = int(data[count + 4])
            bt5 = int(data[count + 5])
            bt6 = int(data[count + 6])
            bt7 = int(data[count + 7])
            bt8 = int(data[count + 8])

            f1a = float(bt1) * two_neg_power64(55)
            f1b = float(bt2) * two_neg_power64(47)
            f1c = float(bt3) * two_neg_power64(39)
            f1d = float(bt4) * two_neg_power64(31)
            f1e = float(bt5) * two_neg_power64(23)
            f1f = float(bt6) * two_neg_power64(15)
            f1g = float(bt7) * two_neg_power64(7)
            f1 = f1a + f1b + f1c + f1d + f1e + f1f + f1g + 1.0
            f2 = two_neg_power64(129 - bt8)
            f = f1 * f2

            output.write(f"{f:g}")
            prev_token = "0"
            count += 8
            handled = True

        # 0xFF - 2-byte token
        if b == 0xFF:
            code = int(data[count + 1])
            s = table2.get(code)
            if s is not None:
                if _needs_space_before(s, prev_token):
                    output.write(" ")
                output.write(s)
                next_byte = data[count + 2] if count + 2 < len(data) else None
                if next_byte is not None and _needs_space_after(s, next_byte):
                    output.write(" ")
                prev_token = s
            else:
                output.write(f"[0xFF][{code:02X}]")
                prev_token = ""
            count += 1
            handled = True

        # 0x80 to 0xFE - 1-byte token
        if 0x80 <= b16 <= 0xFE and not handled:
            s = table.get(b16)
            if s is not None:
                if _needs_space_before(s, prev_token):
                    output.write(" ")
                output.write(s)
                next_byte = data[count + 1] if count + 1 < len(data) else None
                if next_byte is not None and _needs_space_after(s, next_byte):
                    output.write(" ")
                prev_token = s
            else:
                output.write(f"[{b16:02X}]")
                prev_token = ""
            handled = True

        # 0x20 to 0x7F - plain character
        if 0x20 <= b <= 0x7F and not handled:
            ch = chr(b16)
            output.write(ch)
            prev_token = ch
            handled = True

        # byte of zero is end of line
        if b16 == 0:
            done = True
            handled = True

        # Control characters
        if b == 0x07 and not handled:
            output.write("\\a")
            handled = True

        if b == 0x08 and not handled:
            output.write("\\b")
            handled = True

        if b == 0x09 and not handled:
            output.write(" ")
            handled = True

        if b == 0x0A and not handled:
            output.write("\n")
            handled = True

        if b == 0x0D and not handled:
            handled = True

        if not handled:
            if b16 >= 0x11:
                n = b16 - 0x11
                output.write(f"{n}")
                prev_token = "0"
            else:
                output.write(f"0x{b16:02X}")

        count += 1

    return output.getvalue(), count


def detokenize(data: bytes) -> str:
    """
    Detokenize a complete MBASIC program.

    Automatically handles protected files (0xFE magic) by decrypting first.

    Args:
        data: The tokenized BASIC file data (including 0xFF or 0xFE header)

    Returns:
        The ASCII text of the BASIC program
    """
    if not is_tokenized_basic(data):
        # Not a tokenized file, return as-is
        return data.decode('latin-1')

    # Decrypt protected files first
    if is_protected_basic(data):
        data = unprotect(data)

    table, table2 = _build_tables()

    # Skip the magic byte
    contents = data[1:]
    output = StringIO()

    while True:
        if len(contents) < 5:
            break

        # 2 bytes for link pointer (little endian)
        link = int(contents[1]) * 256 + int(contents[0])
        if link == 0:
            break

        # 2 bytes for line number (little endian)
        line_number = int(contents[3]) * 256 + int(contents[2])

        if line_number == 0:
            break

        payload = contents[4:]
        line_text, count = _detokenize_line(payload, table, table2)

        output.write(f"{line_number} {line_text}\n")

        contents = payload[count:]
        if len(contents) < 5:
            break

    return output.getvalue()


def detokenize_bytes(data: bytes) -> bytes:
    """
    Detokenize a MBASIC program and return as bytes.

    Args:
        data: The tokenized BASIC file data

    Returns:
        The ASCII text as bytes (UTF-8 encoded)
    """
    return detokenize(data).encode('utf-8')
