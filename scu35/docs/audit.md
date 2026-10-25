# Audit each practice stage

| Stage | Check | Evidence / pass boundary |
|---|---|---|
| IPI | Correct SU35P part, 128 KiB BRAM, PMC Bridge, UART and AXI Timer; same address map as BSP | Save BD/XSA, validation output and IP versions. Importing an XSA does not prove hardware execution. |
| BSP / application | `mb` standalone domain; tmrctr and XTrngpsx; XilSecure/XilPuf libraries; loadable bytes in BRAM | Save ELF/map, generated headers and library build logs. Reserved PMC shared region is `0x0402b000..0x0402dfff`. A library build executes none of its examples. |
| Implementation | Original pins/clocks; no new unconstrained paths or critical DRC; timing meets constraints | Save routed DCP, timing, DRC, utilization and exact source bindings. Do not treat a zero process exit as equivalent to all these gates. |
| PDI | BIF points to the intended PLM and RCDO; inspect with Bootgen `-arch spartanup -read`; inspect ELF load segments | Save tool output, PDI/ELF/XSA hashes. ELF container bytes differ from bytes loaded into the PDI. Reading headers is not signature verification. |
| Runtime | 10 exact hash vectors, 5 AES cases including rejection, positive/negative LMS/HSS, RNG smoke, five PUF cycles | Save unedited UART and strict-parser result; 31 timing rows and `CMP_DONE,0`. RNG is not compared byte-for-byte; PUF secrets remain internal. |
| Native payload | Full capture, 66 bulk batches, 24 PQ batches, malformed guards, padding KATs, matching public vectors | Validate with `native/analyze.py`. `mcycle` is estimated against a nominal reference. Preserve real payload checks, not only speed numbers. |
| Boot | Signature and ciphertext integrity verified offline; correct image tested on the intended board | Save positive and negative status plus recovery. No owner-policy enforcement claim while unsigned images are accepted. Public-zero encryption is diagnostic only. |
| Recovery | Intended known-good PDI hash, clean DONE/error readback, session lock released | Recovery failure is a failed session even if the demo payload passed. Keep the lock/logs for diagnosis. |

Keep **inputs/hashes → tool version → checks → observed output → saved evidence → unresolved issues** together. The repository manifest describes delivered files; fresh build manifests describe only the new build. Neither alone authenticates a capture against intentional alteration or certifies cryptographic implementation security.
