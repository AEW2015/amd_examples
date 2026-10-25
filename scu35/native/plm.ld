OUTPUT_ARCH(riscv)
ENTRY(_start)
/* Readable RAM/config aperture measured as 64 KiB. Upper RAM remains
   reserved for BootROM handoff, PMC configuration records, and buffering.
   BootROM's PLM load limit is separately 40.5 KiB, not the RAM capacity. */
MEMORY {
  CODE (rx) : ORIGIN = 0x04020000, LENGTH = 0x6000
  DATA (rw) : ORIGIN = 0x04026000, LENGTH = 0x2000
  MAILBOX (rw) : ORIGIN = 0x04029000, LENGTH = 56
  CONTROL (rw) : ORIGIN = 0x04029100, LENGTH = 0x400
  STACK (rw) : ORIGIN = 0x0402a200, LENGTH = 0xc00
  CHUNK (rw) : ORIGIN = 0x0402c000, LENGTH = 0x2000
}
PHDRS { code PT_LOAD FLAGS(5); data PT_LOAD FLAGS(6); }
SECTIONS {
  .text : { KEEP(*(.text.boot)) *(.text .text.*) } > CODE :code
  .rodata : { *(.rodata .rodata.* .srodata .srodata.*) } > CODE :code
  .data : { *(.data .data.* .sdata .sdata.*) } > DATA :data
  .bss (NOLOAD) : {
    . = ALIGN(4); __bss_start = .;
    *(.bss .bss.* .sbss .sbss.*) *(COMMON)
    . = ALIGN(4); __bss_end = .;
  } > DATA :data
  .mailbox : { KEEP(*(.mailbox)) } > MAILBOX :data
  .control (NOLOAD) : { KEEP(*(.control)) } > CONTROL :data
  __global_pointer$ = ORIGIN(DATA) + 0x800;
  __stack_top = ORIGIN(STACK) + LENGTH(STACK);
  __chunk_buffer = ORIGIN(CHUNK);
  /DISCARD/ : { *(.comment) *(.eh_frame*) }
}
ASSERT(SIZEOF(.mailbox)==56, "Mailbox ABI changed")
ASSERT(SIZEOF(.control)<=0x400, "Control overflow")
ASSERT(__bss_end<=0x04027000, "Data overlaps DMA self-test scratch")
