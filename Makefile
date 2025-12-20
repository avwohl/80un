# 80UN - CP/M Archive Unpacker
# Makefile for split module build (single compilation)

# Tools
UPLM80 = uplm80
UM80 = um80
UL80 = ul80
CPMEMU = ~/src/cpmemu/src/cpmemu

# Directories
PLMDIR = src/plm

# Source files for 80un (order matters - startup first, main last)
SRCS = $(PLMDIR)/startup.plm $(PLMDIR)/common.plm $(PLMDIR)/io.plm \
       $(PLMDIR)/squeeze.plm $(PLMDIR)/crunch.plm $(PLMDIR)/lzh.plm \
       $(PLMDIR)/arc.plm $(PLMDIR)/lbr.plm $(PLMDIR)/main.plm

# Source files for 80unbas (BASIC detokenizer only)
BAS_SRCS = $(PLMDIR)/startup.plm $(PLMDIR)/common.plm $(PLMDIR)/io.plm \
           $(PLMDIR)/bas.plm $(PLMDIR)/basmain.plm

# Targets
TARGET = 80un.com
BAS_TARGET = 80unbas.com

.PHONY: all clean test test-arc

all: $(TARGET) $(BAS_TARGET)

# Compile all PL/M files together, then assemble and link
$(TARGET): $(SRCS) $(PLMDIR)/heap.asm
	$(UPLM80) $(SRCS) -o 80un.mac
	$(UM80) 80un.mac -o 80un.rel
	$(UM80) $(PLMDIR)/heap.asm -o heap.rel
	$(UL80) -o $@ 80un.rel heap.rel

# Build 80unbas (BASIC detokenizer)
$(BAS_TARGET): $(BAS_SRCS) $(PLMDIR)/heap.asm
	$(UPLM80) $(BAS_SRCS) -o 80unbas.mac
	$(UM80) 80unbas.mac -o 80unbas.rel
	$(UM80) $(PLMDIR)/heap.asm -o heap.rel
	$(UL80) -o $@ 80unbas.rel heap.rel

# Test with LBR archive
test: $(TARGET)
	cd tests && $(CPMEMU) ../$(TARGET) test.lbr

# Test with ARC archive
test-arc: $(TARGET)
	cd tests && $(CPMEMU) ../$(TARGET) test.arc

# Test BASIC detokenizer (use config file for binary mode)
test-bas: $(BAS_TARGET)
	cd tests && $(CPMEMU) 80unbas.cfg PALLOPS.BAS

clean:
	rm -f *.mac *.rel *.sym 80unbas.com
