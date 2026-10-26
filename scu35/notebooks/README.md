# Repeatable notebook runs

Use a Python environment with `../requirements.txt` installed. Select that exact
interpreter in the notebook kernel picker. Configuration is read from the lab's
local, ignored `config.json` or `SCU35_CONFIG`.

1. Build the shared IPI image using notebook 10 or `python lab.py build`.
   The design is `hw/sys.bd`; its `bench.elf` is embedded in `demo.pdi`.
2. Configure the exact SCU35 cable/UART, matching hardware client/server, and
   known-good recovery PDI/hash. Close other UART terminals and debug sessions.
3. In a runtime notebook, set `LIVE=True` and run the cells. No separate manual
   PDI programming or ELF download is needed.
4. Watch provisional UART timing rows arrive. Only the final strict validation
   and successful recovery establish a passing session.
5. Inspect the inline Python/hardware table and plots. Rerun the measurement
   cell for a fresh capture and fresh Python measurements; increase `REPEATS`
   for independent sessions. Do not confuse those with firmware batch repeats.

| Notebook | Live operation and result |
|---|---|
| 00_start | Overview and optional full IPI runtime comparison |
| 01_sha | Exact SHA3/SHAKE outputs, latency and payload throughput |
| 02_aes | Ciphertext/tag equality, decrypt, bad-tag rejection, latency/throughput |
| 03_pq | Valid and invalid LMS/HSS vectors; latency and operations/s |
| 04_puf | Registration, clear/regeneration and PUF-key AES lifecycle timing |
| 05_rng | Setup and 32-byte generation timings; fresh OS RNG baseline |
| 06_boot | Fresh Python PDI signature verification; optional real signed-image boot |
| 07_efuse_rolling | Fresh Python rolling-chain verification/decryption; optional combo boot |
| 08_highspeed | All supported shared-IPI runtime sizes and methods; same BD |
| 09_pdi | Current-build Bootgen/readelf inspection and optional runtime comparison |
| 10_hardware | Build phases, inspect, program and full inline comparison |

Runtime notebook hardware cells execute the full 31-row suite and filter its
results for the current topic. This keeps one BD and one firmware contract.
No special hardware image per algorithm is needed. Each notebook kernel may
run independently; no hidden result from another notebook is required.

`LIVE=False` always means **recorded hardware plus fresh Python**. Boot notebooks
also have explicit `BUILD_BOOT` and `BOOT_DIR` controls. They never create or
reuse signing state silently. Secure boot and rolling keys require the separate
image-packaging experiment, using the same IPI design as its PL payload.

Device operation timing uses the AXI Timer at nominal 100 MHz. Python uses
`perf_counter`; programming, UART/JTAG and recovery are excluded from device
latency. Decimal MB/s is payload bytes divided by processing microseconds.
This is effective processing throughput, not measured physical bus bandwidth.
The report retains setup/API/full timing boundaries, sample counts, source
hashes, capture timestamps and negative cases. The ordinary PL MicroBlaze V
driver path differs from the separate experimental native PMC benchmark.

PUF has no physical Python counterpart. RNG compares different services;
output bytes should not match. No on-chip boot latency counter is instrumented:
boot session wall time includes tools, programming and recovery and must not be
called boot authentication latency. eFUSE is a documentation-only walkthrough;
no fuse writer, flash write, permanent enrollment or provisioning is run.

Fresh runtime evidence lives under `<build_dir>/runs/<timestamp>/`, including
`uart.txt`, `program.log`, `restore.log`, `session.json`, `comparison.html`,
`comparison.json` and `notebook_report.json`. Replay reports are stored separately
under `<build_dir>/notebook_replay/`. Generated reports are not delivery evidence
until inspected. A failed live run raises an error and preserves its logs.
