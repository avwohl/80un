; heap.asm - Bridge HEAPBASE to linker's __END__ symbol
;
; The linker provides __END__ at the end of all code/data.
; PL/M code references HEAPBASE, so we define it here.

	.Z80
	PUBLIC	HEAPBASE
	EXTRN	__END__

HEAPBASE:
	DW	__END__

	END
