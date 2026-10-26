# SCU35 Ethernet payload encryption

This is a separate MicroBlaze V application and IPI design for the onboard **100 Mb/s MII Ethernet** port. Every functional hardware block is AMD catalog IP. There is no custom HDL module; Vivado generates the top-level wrapper and its MDIO I/O buffer.

The design extends the shared tutorial BD with Clocking Wizard and AXI Ethernet Lite. It retains MicroBlaze V, MDM, 128 KiB local BRAM, SmartConnect, PMC Bridge, AXI UART Lite, AXI Timer, Processor System Reset, and constants. Ethernet Lite has independent transmit and receive ping-pong buffers, adding approximately 8 KiB of packet BRAM beyond the 128 KiB processor memory. Final device usage is in the implementation report.

The validated implementation uses **36 of 48 BRAM tiles** (32 RAMB36 and 8 RAMB18) and 2,952 LUTs. Firmware reserves **76,968 bytes locally**, leaving 54,104 bytes in the 128 KiB local address space, plus 12,060 bytes in the 12,288-byte owned PMC shared region. Logical packet-buffer capacity and physical BRAM primitive allocation are different quantities.

PMC DMA is the hardened DMA used by XilSecure, not an AXI DMA IP instance. Ethernet Lite exposes AXI-Lite packet RAM; an AXI DMA streaming connection is not available on this MAC. Firmware copies received data into the owned PMC shared region, where PMC DMA transfers it through the hardened AES/SHA engines. This first implementation prioritizes reproducibility with the free AMD MAC; it does not claim Ethernet line rate.

## Build

Install Vivado/Vitis 2026.1 with SU35P support and Python dependencies from the parent lab. From this directory, choosing a fresh short build directory:

```text
python build.py --tools D:/AMDDesignTools/2026.1 --out C:/aiup/e35
```

`--phase hardware|platform|firmware|image` selects one stage. Outputs include the Vivado project `prj/eth.xpr`, editable `sys.bd`, exported `sys.tcl`, `hw.xsa`, `eth.elf`, `ethernet.pdi`, stock `plm.elf`, routed checkpoint, and timing/DRC/CDC/utilization reports. The software is compiled into the PDI's initialized BRAM; a separate debugger download is unnecessary.

## Physical setup and payload test

For a configured lab, use `python ethernet/launch.py test` from the parent
`scu35` directory, or open [demo.ipynb](demo.ipynb) and enable `LIVE=True`.
Both paths program the matching Ethernet PDI, run actual payload tests, capture
results and verify recovery. To retain the design and open the live HTML
dashboard instead, run `python ethernet/launch.py dashboard`; see
[dashboard setup](DASHBOARD.md). No separate ELF download is required.

- Direct Ethernet cable between the SCU35 RJ45 and host adapter.
- Host adapter: `192.168.10.1/24`; SCU35: `192.168.10.2/24`, UDP port 6000.
- Connect the SCU35 JTAG and USB UART; select the exact cable and matching hardware-server client.
- No eFUSE, flash, persistent PHY configuration, revocation or provisioning writes occur.

After explicitly programming the PDI through the lab's exact-target runner:

```text
python host.py --bind 192.168.10.1 --board 192.168.10.2 --out out/live
```

`run_hardware.py` automates volatile programming, serial capture, ping, the host tests and a verified recovery image in a `finally` path. It requires explicit `--vivado`, `--pdi`, `--restore`, `--restore-sha256`, `--cable`, `--serial` and a fresh `--out`. It never restarts shared hardware services. Reserve exclusive cable use; the local lease cannot arbitrate another computer.

For the included `reference/timer/compare.pdi` recovery application, supply `--restore-completion-marker CMP_DONE,0`. The first transition from the active Ethernet crypto service was observed to load and run that baseline with latched `SSS_CFG_ERR` (`0x200000`). The runner preserves that failure, waits for the named baseline to complete its volatile crypto cleanup, and permits **one** reprogramming retry for exactly that status bit. Recovery passes only with `DONE=1` and zero error status afterward. No hardware error-status bits are cleared or masked. For other errors, an absent completion marker, or a failed retry, the lease remains held for diagnosis. Do not assume arbitrary recovery firmware provides this marker or cleanup.

The host sends **actual payload bytes over Ethernet**, rather than selecting a resident pattern. Tests cover 16, 64, 256 and 1024 bytes; AES encrypt-to-host, authenticated encrypted echo, exact SHA3/SHAKE results delivered in encrypted responses, and fresh arbitrary 1024-byte round trips. Invalid tags and replayed authenticated requests must be rejected. A plaintext echo provides a transport baseline. IPv4 ARP/ICMP/UDP is a small bare-metal implementation, not a full IP stack; no fragmentation, routing, DHCP, TCP, TLS, IPsec or MACsec is provided.

## Protocol and limits

All integers are network-endian. Request header: `!4sBBHII` (16 bytes): magic `E35Q`, version 1, operation, plaintext length, sequence, peer session. Operations: 1 encrypt supplied plaintext, 2 authenticate/decrypt and re-encrypt echo, 3 plaintext echo, 4 diagnostic stats, 5 SHA3-256, 6 SHAKE-256. Input sizes are 16..1024 bytes in multiples of 16. Operation 2 appends a 12-byte nonce, ciphertext and 16-byte tag; its header is GCM AAD. Other requests append plaintext.

Response header: `!4sBBHIIIIII` (32 bytes): magic `E35R`, version, operation, output length, request sequence, session, status, **previous operation's** timer ticks, received-request count, and transmitted-frame count before this response. Then follow a 12-byte nonce, output bytes and 16-byte tag. For encrypted responses the full header is AAD. Status 2 means bad tag, 3 replay/session rejection, 4 crypto failure; error responses contain no payload and are unauthenticated diagnostics. Operations 3 and 4 return public plaintext diagnostics. A rejected request never publishes decrypted data.

The AES-256 key is the **public diagnostic value 00..1f**, loaded into volatile USER_KEY_0. It proves interoperability, not production secrecy or authenticated identity. The device generates a random 64-bit boot nonce prefix with HRNG, then appends a strictly increasing 32-bit response counter; it stops before wrapping. The host uses a separate random nonce prefix. For operation 2 the board pins one authenticated peer session per boot and rejects non-increasing sequences. Host `peer_state.json` reserves sequence ranges before use to support repeated runs. To intentionally change peer session, restart/reprogram the board; do not silently delete host state mid-session.

Host timings measure sequential UDP request/response latency, including host/network/device scheduling and device processing. Host request preparation and response AES verification are outside that interval. The reported sequential payload rate is not a saturated-link bandwidth result. AXI Timer runs at nominal 100 MHz. Authenticated response construction requires its header before encryption, so the timer field reports the **previous** operation; operation 4 retrieves the most recent completed processing interval.

MII constraints use [TI DP83867IR SNLS484J](https://www.ti.com/lit/ds/symlink/dp83867ir.pdf), sections 6.12/6.13, with a stated 1 ns relative PCB skew allowance. Trace skew has not been independently measured. Slow management/reset/UART paths are explicit exceptions. Preserve the full timing and CDC reports, including vendor core waivers, when evaluating the result.

## Validated hardware result — October 25, 2026

The repeat physical-Ethernet run completed **24 functional checks**, **450 timed benchmark exchanges**, and **475 total application responses**. Python independently checks 20 captured payload/hash vectors using the public key, the modified-tag rejection record, and acceptance followed by rejection of a replayed authenticated request. The known-good runtime PDI was restored with DONE=1 and zero error status. The first run's failed immediate recovery and successful follow-up are preserved separately; the repeat run's recovery passed directly.

| 1 KiB operation | Median network request/response time | Sequential payload rate |
|---|---:|---:|
| Plain UDP echo | 986.55 µs | 1.029 MB/s |
| PMC encrypted response | 1,051.55 µs | 0.966 MB/s |
| PMC decrypt + encrypt echo | 1,124.00 µs | 0.905 MB/s |

These are sequential network exchanges through the actual MII link, not saturated Ethernet throughput or native-PMC resident-buffer rates. One initial ICMP ping was lost during initial address resolution; the timed UDP exchanges all returned the expected responses.

Routed setup slack is **3.867 ns**, hold slack **0.012 ns**, and DRC has no errors. Four **CDC-11 critical reset-fanout warnings remain unwaived** inside the vendor Ethernet MAC, at parallel reset synchronizers. Missing-ASYNC_REG warnings on the vendor MDIO/carrier-sense synchronizers and XPM FIFO/debug enable warnings are also retained. The review supports a laboratory demonstration; production CDC/reset-stress/MTBF qualification is not claimed.

Recheck a fresh build using `python check_build.py --out /path/to/build`. A build without new hardware evidence or an image-bound CDC review is correctly reported INCOMPLETE. For detailed CDC inspection, run Vivado with `-source review_cdc.tcl -tclargs /path/to/build`. Do not reuse a review record for a different PDI or report hash.

Saved packet bytes can be verified offline with `python verify_capture.py evidence/run2/ethernet/results.json`. The replay check validates both the accepted response and the rejected repeat; error responses themselves are unauthenticated diagnostics. Recorded captures are evidence of the recorded session, not a new hardware run.

The root cause of the first latched SSS status is not established; the repeat session did not reproduce it. The guarded automatic retry implements the separately observed manual recovery sequence; the repeat session passed without needing that branch.

`reference/sys_built.bd` is a snapshot of the implemented design and retains its historical ELF association for inspection. Use `build.py` for a fresh portable build, rather than importing that snapshot as a new platform. `reference/sys.tcl` is the pre-ELF BD export.
## Live dashboard

The [live crypto dashboard](DASHBOARD.md) provides on-the-fly mode and payload-size controls, real Ethernet measurements, packet inspection, and tag-tamper/replay checks. It retains the volatile demo and hardware reservation while running; use its restore control when finished.


For the proposed streaming MAC and DMA upgrade, see [DMA architecture and evidence boundaries](DMA.md). The current reference PDI remains Ethernet Lite.

## Live LMS/HSS payload verification (v2)

The v2 firmware adds operations 7/8 for LMS/HSS. Requests use the same AES-GCM
AAD/nonce/tag envelope as authenticated echo. A 16-byte `PQU1` command header
(`!4sIHHHH`: magic, transfer ID, offset, chunk length, total, reserved) precedes
up to 1008 chunk bytes. Five requests upload a fixed 4608-byte workspace:
signature at offset 0, 56-byte message at 4480, public key at 4544. Replies
`PQA1` acknowledge the ID, received count and total. A 16-byte `PQV1` command
triggers verification after the complete ordered upload. Encrypted `PQR1`
results contain transfer ID, accepted flag, vendor status, verify ticks,
verification counter, received bytes and a software path mask (not a hardware
trace). Only the bounded AMD n=32/H5/W2 and one-level HSS profile is supported.

`run_hardware.py --pq` checks valid/changed signatures/messages/keys and
incomplete/wrong-ID/overrun guards. The configuration launcher enables PQ tests by default for the v2 reference image; set `ethernet_pq: false` only when intentionally testing a legacy v1 image. The dashboard repeats real verification and Python checks
without another upload until method/case changes. It separates upload time,
UDP RTT and the AXI Timer verification API interval. No signing state, PUF,
eFUSE or persistent writes are involved.

The fresh v2 run in `evidence/run4/` passed the original payload suite, 40 LMS/HSS
verifications (both algorithms, four cases, five repetitions), six malformed /
tag / replay guards, and recovery. The earlier failed timer-baseline restoration
is retained in `evidence/pq_restore_attempt1/`; the successful repeat used an
explicitly selected quiet known-good image. The transition's root cause remains
unresolved. No status bits were cleared or masked. Legacy v1 captures remain
historical; `reference/ethernet_v1.pdi` preserves their original image.
