# 80UN - CP/M Archive Unpacker
# Makefile for split module build (single compilation)

# Tools
UPLM80 = uplm80
UM80 = um80
UL80 = ul80
CPMEMU = ~/src/cpmemu/src/cpmemu

# Source files (order matters - startup first, main last)
SRCS = startup.plm common.plm io.plm squeeze.plm crunch.plm lzh.plm arc.plm lbr.plm main.plm

# Target
TARGET = 80un.com

# Single file build (original monolithic version)
ORIG_SRC = 80un.plm
ORIG_TARGET = 80un_orig.com

.PHONY: all clean test orig

all: $(TARGET)

# Compile all PL/M files together, then assemble and link
$(TARGET): $(SRCS) heap.asm
	$(UPLM80) $(SRCS) -o 80un.mac
	$(UM80) 80un.mac -o 80un.rel
	$(UM80) heap.asm -o heap.rel
	$(UL80) -o $@ 80un.rel heap.rel

# Build original monolithic version for comparison
orig: $(ORIG_TARGET)

$(ORIG_TARGET): $(ORIG_SRC)
	$(UPLM80) $< -o 80un_orig.mac
	$(UM80) 80un_orig.mac -o 80un_orig.rel
	$(UL80) -o $@ 80un_orig.rel

# Test with LBR archive
test: $(TARGET)
	cd tests && $(CPMEMU) ../$(TARGET) test.lbr

# Test with ARC archive (if available)
test-arc: $(TARGET)
	cd tests && $(CPMEMU) ../$(TARGET) test.arc

clean:
	rm -f *.mac *.rel *.sym $(TARGET) $(ORIG_TARGET)
