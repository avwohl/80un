"""Tests for tokenized BASIC file handling."""

import pytest
from un80.bas import is_tokenized_basic, detokenize, detokenize_bytes, MBASIC_MAGIC


class TestBAS:
    """Tests for MBASIC detokenizer."""

    def test_is_tokenized_basic_true(self):
        """Test detection of tokenized BASIC file."""
        # Starts with 0xFF
        data = bytes([0xFF, 0x00, 0x00])
        assert is_tokenized_basic(data) is True

    def test_is_tokenized_basic_false(self):
        """Test detection of ASCII BASIC file."""
        # Starts with '1' (0x31) - ASCII
        data = b'10 PRINT "HELLO"'
        assert is_tokenized_basic(data) is False

    def test_is_tokenized_basic_empty(self):
        """Test detection of empty file."""
        assert is_tokenized_basic(b'') is False

    def test_mbasic_magic_constant(self):
        """Verify MBASIC magic constant."""
        assert MBASIC_MAGIC == 0xFF

    def test_detokenize_simple_program(self):
        """Test detokenizing a simple PRINT statement."""
        # Manually constructed tokenized file:
        # Line 10: PRINT "HELLO"
        # Line 20: END
        import struct

        # Build a minimal tokenized program
        # Magic byte
        result = bytes([0xFF])

        # Line 10: PRINT "HELLO"
        # PRINT = 0x91, END = 0x81
        line1_tokens = bytes([0x91, 0x20]) + b'"HELLO"' + bytes([0x00])
        line1_num = struct.pack('<H', 10)  # Line number 10

        # Line 20: END
        line2_tokens = bytes([0x81, 0x00])
        line2_num = struct.pack('<H', 20)  # Line number 20

        # Calculate addresses (base = 0x101)
        base = 0x101
        line1_len = 2 + 2 + len(line1_tokens)  # link + linenum + tokens
        line2_len = 2 + 2 + len(line2_tokens)

        line1_link = struct.pack('<H', base + line1_len)
        line2_link = struct.pack('<H', base + line1_len + line2_len)

        result += line1_link + line1_num + line1_tokens
        result += line2_link + line2_num + line2_tokens
        result += bytes([0x00, 0x00])  # End marker

        output = detokenize(result)
        lines = output.strip().split('\n')

        assert len(lines) == 2
        assert '10' in lines[0] and 'PRINT' in lines[0] and 'HELLO' in lines[0]
        assert '20' in lines[1] and 'END' in lines[1]

    def test_detokenize_for_loop(self):
        """Test detokenizing a FOR loop with proper spacing."""
        import struct

        # FOR = 0x82, TO = 0xCE, NEXT = 0x83, END = 0x81
        # Build: FOR I=1 TO 10 / NEXT I / END

        result = bytes([0xFF])

        # Line 10: FOR I=1 TO 10
        # 0x12 = 1 (encoded as 0x11 + 1), 0x1B = 10 (0x11 + 10)
        line1_tokens = bytes([0x82, 0x49, 0xF0, 0x12, 0xCE, 0x1B, 0x00])
        line1_num = struct.pack('<H', 10)

        # Line 20: NEXT I
        line2_tokens = bytes([0x83, 0x49, 0x00])
        line2_num = struct.pack('<H', 20)

        # Line 30: END
        line3_tokens = bytes([0x81, 0x00])
        line3_num = struct.pack('<H', 30)

        base = 0x101
        l1_len = 2 + 2 + len(line1_tokens)
        l2_len = 2 + 2 + len(line2_tokens)
        l3_len = 2 + 2 + len(line3_tokens)

        l1_link = struct.pack('<H', base + l1_len)
        l2_link = struct.pack('<H', base + l1_len + l2_len)
        l3_link = struct.pack('<H', base + l1_len + l2_len + l3_len)

        result += l1_link + line1_num + line1_tokens
        result += l2_link + line2_num + line2_tokens
        result += l3_link + line3_num + line3_tokens
        result += bytes([0x00, 0x00])

        output = detokenize(result)

        # Check proper spacing: "1 TO 10" not "1TO 10" or "1  TO 10"
        assert '1 TO 10' in output
        assert '1TO' not in output
        assert '1  TO' not in output

    def test_detokenize_bytes(self):
        """Test that detokenize_bytes returns bytes."""
        import struct

        result = bytes([0xFF])
        line_tokens = bytes([0x81, 0x00])  # END
        line_num = struct.pack('<H', 10)
        line_link = struct.pack('<H', 0x101 + 2 + 2 + len(line_tokens))

        result += line_link + line_num + line_tokens
        result += bytes([0x00, 0x00])

        output = detokenize_bytes(result)
        assert isinstance(output, bytes)
        assert b'10' in output
        assert b'END' in output

    def test_detokenize_ascii_passthrough(self):
        """Test that ASCII BASIC files pass through unchanged."""
        data = b'10 PRINT "HELLO"\n20 END\n'
        output = detokenize(data)
        assert output == data.decode('latin-1')
