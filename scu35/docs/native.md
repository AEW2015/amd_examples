# High-speed native PMC path

`native/fast.c` and `native/native_pq.c` process resident buffers through the hardened crypto engines and PMC DMA. `native/monitor.c` exposes the fixed benchmark RPC operations. `hw/native_test.tcl` uploads public LMS/HSS vectors, verifies readback, requests batches, reads results and restores the selected recovery image. No JTAG transaction is inside a firmware operation's timed interval.

Run `python lab.py native` to rebuild the original independent PMC BSP archive from `native/bsp/pmc_bsp.c`, compile the native firmware using the configured 2026.1 RISC-V compiler, generate a PDI using the retained fixture RCDO, and verify its ELF load bytes and SHA3 chains. This reproduced the exact retained PDI hash on the tested Windows installation. No precompiled BSP library is required.

The full PL fixture source is in `native/fixture/`: JTAG AXI, SmartConnect, PMC Bridge and a clock-reference writer. `build_fixture.tcl` creates a fresh short project using the same installed Vivado release. It is optional: the native firmware build defaults to the **recorded, hash-bound RCDO** to preserve the clock/transport fixture. A newly implemented RCDO can differ; it must be packaged and requalified rather than being silently labeled the old fixture. The provided fixture packaging helper is described below.

```text
# Invoke installed Vivado, supplying source directory and a fresh short output:
vivado -mode batch -source native/fixture/build_fixture.tcl -tclargs /absolute/path/to/scu35/native/fixture /short/f35
```

The fixture exports its RCDO, stock PLM and XSA. To use a new fixture with the independent loader, run `python lab.py native --fixture /short/f35/design.rcdo --stock-plm /short/f35/plm.elf`; this derives a new CDO specification from an unsigned seed PDI before compiling. This is a new build, not a new hardware validation. It must retain the same PMC address map, owned RAM ABI and nominal reference clock.

Bulk hash/AES input is preloaded at `0x04027000..0x04028fff`; output is `0x0402c000..0x0402dfff`. Public AES key bytes are `00..1f`; they are loaded into volatile user key storage and cleared. Full-message AES ENC/DEC up to 8 KiB is checked byte-for-byte, with modified-tag rejection. For 64 KiB/1 MiB streaming encryption, only the final 8 KiB ciphertext is read back, plus the full-message tag; readback of every intermediate output byte and streamed decryption are not claimed.

The demonstration's payload generator accepts seeded repeated resident data. It is not a general host file-transfer application or an external-memory/HyperRAM benchmark. To try another payload or sequence, modify the explicit input-generation code and firmware/RPC contract, rebuild and update the Python expected-data calculation. Do not send arbitrary addresses or buffers into reserved PMC RAM. The included public-vector upload is a separate concrete post-configuration data-ingress example.

The native LMS/HSS verifier is an independent fixed-vector benchmark port, not AMD's production boot verifier. It uses hardened SHAKE and software tree/encoding logic. Positive and three modified-input cases, six malformed-input guards and ten SHAKE padding lengths are retained. The broader vendor runtime application still supplies RNG/PUF lifecycle demos; there is no claim that every PMC peripheral has a native high-speed data API.
