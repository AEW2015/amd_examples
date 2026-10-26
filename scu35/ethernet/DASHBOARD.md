# Live crypto dashboard

## Launch from the lab configuration

Configure the parent `config.json` as for the PMC notebooks, then run from the
`scu35` directory:

```text
python ethernet/launch.py test
python ethernet/launch.py dashboard
```

The first command programs the Ethernet image, runs the physical packet suite,
and verifies recovery. The second programs it again and keeps the live HTML
dashboard and board reservation active. Open the localhost URL it prints.
Use `--port 8045` if the default dashboard port is already occupied.

The launcher uses `hardware_vivado`, `server`, `cable`, `serial_port`,
`build_dir`, and the recovery image/hash from the shared lab configuration.
The supplied `ethernet/reference/ethernet.pdi` is the default demo image;
`ethernet_pdi` can select your fresh build. Optional configuration keys are
`ethernet_bind`, `ethernet_board`, `ethernet_dashboard_port`,
`ethernet_restore_pdi`, `ethernet_restore_sha256`, and
`ethernet_restore_completion_marker` for the automated test's documented
cleanup/retry procedure. Dashboard recovery recognizes the timer baseline's
`CMP_DONE,0` marker. No host network settings are changed automatically.

The [Ethernet notebook](demo.ipynb) can run the same program/test/recovery flow
with `LIVE=True`, and contains saved live packet and fresh Python outputs.
Restore/stop the dashboard before running that cell: the dashboard is the
exclusive Ethernet client and owns the board while it is active.

Run `dashboard.py` with the lab Python environment (`requirements.txt`, including pyserial and cryptography). It serves a self-contained page at **http://127.0.0.1:8035/**. No CDN, browser extension or JavaScript package installation is needed.

The server **programs the selected volatile PDI and retains the hardware reservation while running**. Start it only for an authorized, exclusively available SCU35. Use a Vivado client matching your running hardware server. All tool, cable, UART, PDI, recovery and output paths are explicit:

```text
python ethernet/dashboard.py --vivado <matching-vivado> --pdi <ethernet.pdi> --restore <known-good.pdi> --restore-sha256 <sha256> --cable <exact-serial> --serial <UART> --out <new-output-directory> --server localhost:3121 --bind 192.168.10.1 --board 192.168.10.2 --port 8035
```

Keep that process running and open the printed URL. With a foreground process, Ctrl+C requests recovery before shutdown. In the browser, **Restore board & stop traffic** restores the supplied known-good PDI, requires clean DONE/error status and releases the reservation; the HTTP page remains available. A forced process kill or power loss cannot execute cleanup: inspect the retained lock/logs and recover explicitly before reuse. The supplied timer reference is a lab runtime image, not the owner's original factory image.

Live controls:

The LMS-SHAKE256 and HSS-SHAKE256 buttons now run **actual Ethernet signature verification** with the v2 image. The host uploads 4608 aligned bytes containing the message, public key and signature in five AES-GCM protected chunks. The board stages them in PMC shared RAM. MicroBlaze V runs the AMD XilSecure verifier; hardened PMC DMA/SHAKE supplies the hash operations. The authenticated encrypted response includes the actual accept/reject result and AXI Timer verification interval. Python independently checks the same inputs on every displayed verification.

The four case buttons send a valid vector, changed signature, changed message or changed public key. Only public AMD n=32/H5/W2 vectors and one-level HSS are supported. The public key comes from the host for this algorithm demonstration; it is not an owner-pinned trust root. No signing occurs and no stateful signing key is stored on the board. Public AES transport keys do not provide production secrecy.

The full-width Host / SCU35 / PL / PMC diagram highlights the blocks used by the selected method. Click a block for its role. Highlights and arrows explain the operation path and update on actual verified replies; they are not cycle-sampled internal bus traces. TRNG is used at initialization, while PUF/eFUSE and PLM are outside the repeated payload path. Live completed-work curves sum actual device and Python verification intervals; dots are sampled completion checkpoints. Upload, AES transport, RTT and Python comparison are outside the device verification API interval. For normal hash/AES modes the existing aligned device-operation interval remains in use.

The dashboard detects the v2 UART capability marker and disables PQ controls for older images. Upload buffers are bounded, ordered and bound to the authenticated peer. Incomplete uploads, wrong transfer IDs and overruns are rejected. The existing native-PMC benchmark remains a different, faster resident-buffer path; its historical numbers are not substituted into the live Ethernet panel.

| Control | Actual device operation |
|---|---|
| Plain UDP | Plain packet echo, bypassing crypto |
| AES-GCM encrypted response | Plain request, authenticated encrypted response |
| AES-GCM authenticated round trip | Authenticate and decrypt request, replay check, encrypt response |
| SHA3-256 / SHAKE-256 | Hash actual input, return encrypted 32-byte digest, compare with Python |
| LMS-SHAKE256 / HSS-SHAKE256 | Upload real public vectors, verify on MicroBlaze V + hardened SHAKE, return authenticated decision and measured API time |
| Payload size | 16, 64, 256, 512 or 1,024 bytes |
| Traffic mode | Unpaced: 64-packet batches, one request in flight; presentation: at most 20 primary requests/s |
| Test tamper + replay | Accept a valid request, reject its replay, reject a fresh request with a corrupted tag |
| Pause / resume | Stop / resume the paced request stream without reconfiguring hardware |

The AES key is public diagnostic material. These buttons do not select boot authentication algorithms, provision keys, register a PUF or write eFUSE/flash. HSS/LMS secure boot uses the separate signed-image demo; these live buttons perform post-configuration payload verification.

Every successful payload/digest is compared with the expected host result. AES-GCM replies verify their tags; negative-test error replies are unauthenticated diagnostics. The device nonce check requires a fixed boot prefix and strictly increasing response counter, with bounded memory. Sequence reservations renew before exhaustion while retaining the same authenticated peer session. One worker serializes all requests; do not run another host client against this firmware concurrently.

Host RTT covers UDP send to receive, excluding preparation of that request and verification of that response. Unpaced mode does not insert presentation delays; each request still waits for its own response. A following stats probe aligns the AXI Timer interval to the last completed operation in each batch; that interval includes copies, crypto and response assembly. The probe is outside primary RTT.

**Observed payload Mb/s is wall-clock input payload rate, including validation, amortized probes, logging and inter-batch overhead.** It excludes link framing and does not sum full-duplex directions. The meter divides this payload rate by 100 Mb/s; it is not physical wire utilization. Pauses lower the rate; changing mode, size or traffic pace resets the rolling window. Device time uses the nominal 100 MHz timer clock. Throughput mode reuses a fresh random payload within each 64-packet batch; every AES encryption uses a fresh nonce, and every response is checked. Logs contain batch summaries rather than one record per packet. RTT P50/P95 use the recent individual response times, while device time is sampled once per batch.

The experimental first 300-packet transport probe measured 15.5 Mb/s plain echo and 13.5 Mb/s encrypted replies with two in-flight requests, compared with 7.8 and 7.5 Mb/s with one in flight. The integrated dashboard's wall-clock rate is lower and variable; use its measured value rather than treating the probe as a sustained dashboard rate. A subsequent continuous two-request run timed out after 56,192 verified dashboard packets; the cause of the missing response is not established. The runner restored the known-good image with clean status. Consequently the delivered continuous dashboard uses one in-flight request, not the short-probe two-request setting. This optimization does not change the PDI, MAC, firmware or BRAM size. Near-line-rate throughput remains unproven; the current software copies and PMC service path remain in each packet's critical path.

`measurements.jsonl`, `uart.txt` and programming/recovery logs are saved under `--out`. Preserve failed logs and any reservation if recovery fails. The build still has four reviewed, unwaived CDC-11 critical warnings; functional success is not production CDC or network-security qualification.

Validated locally on Windows with the real SCU35 Ethernet link: all five mode buttons, payload changes, four-second pause/resume, actual bad-tag/replay rejection, desktop/mobile layouts and a complete restore/restart cycle. Cross-OS server portability has not been hardware-tested.
