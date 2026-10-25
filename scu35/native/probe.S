.section .text,"ax",@progbits
.option push
.option norvc
.balign 4
.globl probe_read
probe_read:
    mv t1,a0
    li t0,0
    li a0,0
    /* The trap advances exactly this 32-bit load instruction. */
    lw a0,0(t1)
    sw t0,0(a1)
    ret
.balign 4
.globl probe_csr
probe_csr:
    mv t1,a0
    li t0,0
    li a0,0
    li t2,0
    beq t1,t2,csr_cycle
    li t2,1
    beq t1,t2,csr_cycleh
    li t2,2
    beq t1,t2,csr_instret
    li t2,3
    beq t1,t2,csr_instreth
    li t2,4
    beq t1,t2,csr_misa
    li t2,5
    beq t1,t2,csr_vendor
    li t2,6
    beq t1,t2,csr_arch
    li t2,7
    beq t1,t2,csr_impl
    li t2,8
    beq t1,t2,csr_countinhibit
    li t2,9
    beq t1,t2,csr_time
    li t2,10
    beq t1,t2,csr_timeh
    li t2,11
    beq t1,t2,csr_mip
    li t2,12
    beq t1,t2,csr_mtvec
    li t0,-1
    j csr_return
csr_cycle: csrr a0,mcycle
    j csr_return
csr_cycleh: csrr a0,mcycleh
    j csr_return
csr_instret: csrr a0,minstret
    j csr_return
csr_instreth: csrr a0,minstreth
    j csr_return
csr_misa: csrr a0,misa
    j csr_return
csr_vendor: csrr a0,mvendorid
    j csr_return
csr_arch: csrr a0,marchid
    j csr_return
csr_impl: csrr a0,mimpid
    j csr_return
csr_countinhibit: csrr a0,mcountinhibit
    j csr_return
csr_time: csrr a0,time
    j csr_return
csr_timeh: csrr a0,timeh
    j csr_return
csr_mip: csrr a0,mip
    j csr_return
csr_mtvec: csrr a0,mtvec
csr_return:
    sw t0,0(a1)
    ret
.balign 4
.globl probe_execute
probe_execute:
    addi sp,sp,-16
    sw ra,12(sp)
    mv t3,a0
    li t0,0
    li a0,0
    jalr ra,0(t3)
execute_resume:
    sw t0,0(a1)
    lw ra,12(sp)
    addi sp,sp,16
    ret
.balign 4
.globl execute_trap
execute_trap:
    csrr t0,mcause
    la t2,execute_resume
    csrw mepc,t2
    mret
.balign 4
.globl probe_trap
probe_trap:
    csrr t0,mcause
    csrr t2,mepc
    addi t2,t2,4
    csrw mepc,t2
    mret
.option pop
