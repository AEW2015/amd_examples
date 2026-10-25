.section .text.boot,"ax",@progbits
.option push
.option norvc
.option norelax
.globl _start
_start:
    csrci mstatus,8
    csrw mie,zero
    la sp,__stack_top
    la gp,__global_pointer$
    la t0,fatal_trap
    csrw mtvec,t0
    la t0,__bss_start
    la t1,__bss_end
1:  bgeu t0,t1,2f
    sw zero,0(t0)
    addi t0,t0,4
    j 1b
2:  call independent_main
3:  j 3b
.balign 4
fatal_trap:
    csrr t0,mcause
    lui t1,0x40a0
    andi t0,t0,31
    ori t0,t0,0xc0
    sw t0,0x158(t1)
4:  j 4b
.option pop
