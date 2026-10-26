# Hardware setup

Use an SCU35 with `xcsu35p-sbvb625-2-e` / IDCODE `04e80093`. The scripts refuse other devices. Confirm the evaluation-board revision and pinout against the included XDC before building; the recorded board used a 100 MHz differential reference on F23/E23, reset on F3 and FTDI UART on AC6/AB6 at 115200 8N1.

1. Install AMD cable drivers. On Linux, follow AMD installer instructions and grant access through the supported udev/serial groups rather than running the notebook as root. Identify the UART using its stable `/dev/serial/by-id/...` path; Windows uses the appropriate `COM` port. Do not guess another cable's port.
2. Start a dedicated hardware server through AMD tools, or use an existing authorized one. Record its release and endpoint. `hardware_vivado` must be the matching-release Vivado executable. The original shared lab used **2025.2 client/server on localhost:3121** while building with 2026.1. That release/endpoint is historical evidence, not a universal requirement for other setups.
3. Put your exact cable serial in `config.json`. No cable serial is compiled into the portable runner. Match the `...A` JTAG channel with the correct UART channel for your board.
4. Set `restore_pdi` and `restore_sha256` to a known-good **SU35P** recovery image appropriate for the owner/board. The included `reference/timer/compare.pdi` is a functional runtime example, not an owner's original factory image. Do not assume a power cycle or a supplied sample reproduces an owner's provisioning.
5. Run `python lab.py doctor`, complete offline `verify`, and inspect the selected test image and expected mode. The notebook does not start a hardware test automatically.
6. Run one explicit `hardware` command. The runner logs selected server/cable, test and recovery hashes, programming status, UART/RPC results, recovery and exception outcomes. If recovery fails, retain the reservation and investigate. A local lock cannot arbitrate a second computer on a shared server; arrange exclusive use.

For the native benchmark, the selected PDI must have a matching `plm.elf` beside it. The repository supplies that pair under `reference/native/`; `lab.py native` produces another pair under `<build_dir>/native/build/`. Native fixtures expose exactly one JTAG AXI interface, required for the monitor RPC and public signature-vector upload. Host transfer is outside the timed interval.

## Local memory audit

The shared tutorial and Ethernet reference designs provide **128 KiB of MicroBlaze V local memory**. Check a manually built IPI/platform at each stage; importing a different or older XSA can preserve a smaller application memory map.

| Stage | Expected local memory at base zero |
|---|---|
| Vivado Address Editor | Both instruction and data local-memory segments: range `128K`, high address `0x0001FFFF` |
| Exported XSA / regenerated BSP | Local BRAM base `0x0`, high address `0x1FFFF` in generated `xparameters.h` |
| Application `src/lscript.ld` | The local-memory region has `ORIGIN = 0x0, LENGTH = 0x20000` |

`LENGTH = 0x2000` and high address `0x1FFF` describe **8 KiB**, not 128 KiB. This mismatch was observed in a manually created SHA-example platform; both its BD and generated BSP advertised only 8 KiB. A `.text` overflow is a linker-capacity failure, not evidence that the SHA hardware failed. Check the memory map before treating `-O0` as the main cause.

If the BD is too small, configure the required local memory and both address segments in Vivado, validate/regenerate the design, and export an updated XSA. Update/rebuild the Vitis platform and regenerate the application linker script. Confirm all three stages agree before rebuilding the example. A newly generated PDI/bitstream must contain that updated hardware before testing the application on the board. Do not expand only the linker script beyond the actual hardware address range, or hand-edit generated BSP headers to conceal a stale platform.

## Vendor SHA and LMS/HSS shared memory

The 128 KiB local BRAM is CPU memory. It does not make those addresses readable
by hardened PMC DMA. Audit the final ELF, including buffers inside libraries,
when adapting AMD's examples to a manually created platform.

### SHA: replace the address placeholder

AMD's example header uses `ORIGIN = SHARED_MEM` as a placeholder. The normal
linker script is not preprocessed as C: a C `#define` does not define this
linker symbol. An unresolved origin causes `invalid origin for memory region
shared_mem`, followed by overlapping sections near address zero.

For the manually tested 2026.1 platform, this region worked:

```ld
shared_mem : ORIGIN = 0x0402C000, LENGTH = 0x2000
```

Its PLM load region ended at `0x04026BF0` and stack at `0x0402AE00`.
These addresses are **image-specific**, not a universal allocation recipe.
Inspect your own PLM program headers, stack, mailboxes and other reservations
before selecting a shared region. The example's `.data.*` rules must collect
the input and SHA instance; the latter contains DMA-read padding storage.
The SHA application was rebuilt and its ELF placement checked after this fix;
that particular manual SHA rebuild was not hardware-tested in this session.

### LMS/HSS: include the library's scratch buffers

Moving only the example's `.data` inputs is insufficient with the tested
2026.1 XilSecure library. `xsecure_lms_core.c.obj` also contains zero-initialized
scratch in `.bss` / `.sbss`, including `LmsOtsSignVerifBuff`,
`TmpHashPerDigitBuff`, `LmsPubKeyTmpBuff` and `DigestPrefixFields`. Some scratch
is subsequently supplied to hardened SHA/DMA. In the failed ELF these buffers
were in local BRAM, even though the public vectors were correctly shared.

For that platform we expanded the owned region to 16 KiB:

```ld
shared_mem : ORIGIN = 0x0402C000, LENGTH = 0x4000
```

Inside the existing output `.data` section, **before** the generic output
`.bss` / `.sbss` sections, add:

```ld
*(.data)
*(.data.*)
/* Shared, zero-initialized XilSecure LMS core scratch. */
*xsecure_lms_core.c.obj(.bss .bss.* .sbss .sbss.*)
*(.gnu.linkonce.d.*)
```

Keep that output section mapped to `> shared_mem`. This collects the scratch
into the initialized ELF data segment; the ELF downloader initializes it.
The archive member name is from the tested toolchain: inspect `ar t` and the
final symbols if another release uses different names. Do not place all code,
stack or heap in PMC RAM to work around a single DMA buffer.

Use the matching toolchain's `readelf -l`, `readelf -S` and `nm -n` on the final
ELF. In the fixed manual LMS/HSS build, shared data ended at `0x0402FA34`;
`LmsOtsSignVerifBuff` was at `0x0402E810` and `DigestPrefixFields` at
`0x0402F9C4`. Both LMS and HSS passed on physical hardware over UART, followed
by clean recovery. [The capture and linker snapshot](../evidence/vendor_memory/)
record this **separate manually created platform**, not a rebuild of the
repository's reference PDI. No BSP library or vendor C source was patched.

No script creates an eFUSE writer, calls flash programming, changes device clock dividers, restarts shared services, or installs a permanent boot image. PUF registration is adapted to volatile helper data and key-clear/regeneration cycles. The unmodified AMD XilNvm example is **not read-only** and must not be run as a shortcut: its main calls the fuse writer before readout.
