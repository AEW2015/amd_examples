# SCU35 PMC security and user-payload lab

One SCU35 design, one Python entry point, and replay-first notebooks for the security livestream. **SCU35 / XCSU35P-SBVB625-2-E only.** No eFUSE or flash programming is part of this lab.

Start with the **[hosted self-paced lesson](https://aew2015.github.io/amd_examples/)** or the **[hosted presenter](https://aew2015.github.io/amd_examples/presenter.html)**. The lesson provides browser-local chapter progress and direct access to the diagrams, examples and recorded evidence. No installation or hardware is needed to read it. The [offline presenter](docs/scu35_presenter.html) also works after downloading/cloning the repository. The [notebooks](notebooks/) contain executable Python checks and recorded hardware results. The default commands never access a board.

## Physical Ethernet payload demo

The [IPI Ethernet/PMC application](ethernet/README.md) sends real host payloads through hardened AES-GCM and SHA over the onboard 100 Mb/s MII link. It includes a catalog-IP-only design, MicroBlaze V software, a notebook, reference PDI/ELF/XSA, and physical hardware evidence. No HyperRAM or eFUSE/flash programming is required.

Follow [Chapter 18: Complete example—Ethernet crypto](https://aew2015.github.io/amd_examples/#ethernet) for the full build, hardware test, local dashboard and audit walkthrough.

## Quick start: no AMD installation or hardware required

From this `scu35` directory, using Python 3.11:

```text
python -m venv .venv
# Activate .venv using your shell, then:
python -m pip install -r requirements.txt
python lab.py verify
python lab.py replay --out out/comparison.html
python -m ipykernel install --user --name scu35-pmc --display-name "Python (SCU35 PMC)"
jupyter lab notebooks
```

Windows PowerShell activation: `.venv\Scripts\Activate.ps1`. Linux bash activation: `source .venv/bin/activate`. Select **Python (SCU35 PMC)** in the notebook. If activation is restricted, invoke `.venv/Scripts/python.exe` on Windows or `.venv/bin/python` on Linux directly. `verify` checks the delivered hashes, exact hardware digests/AES tags, negative signature tests and public HSS boot signatures. `replay` makes fresh Python timing measurements against the saved board capture; it does **not** make a new hardware measurement.

## Build the shared platform

### Repeat hardware and Python measurements inside the notebooks

Open [00_start.ipynb](notebooks/00_start.ipynb) for an overview or
[10_hardware.ipynb](notebooks/10_hardware.ipynb) for the build/program workflow.
After configuring `config.json`, set `LIVE = True` in a runtime notebook and run
its cells. It programs the repository-generated IPI `demo.pdi`, streams UART
timing rows into the notebook, checks the complete capture, measures Python
again, and displays fresh comparison tables and plots. `bench.elf` is embedded
in BRAM during image generation; no separate Vitis ELF download is needed.

Each feature notebook can independently repeat the full suite and display its
own feature group. `REPEATS` selects independent hardware/host runs. Session
logs, raw UART, HTML/JSON reports and hashes are saved under
`<build_dir>/runs/`. The configured recovery PDI is reloaded afterward.
`LIVE = False` explicitly shows recorded hardware plus freshly measured Python;
a failed live run never falls back to recorded results. See the
[notebook guide](notebooks/README.md) for timing limits and special cases.

Install **Vivado and Vitis 2026.1** with Spartan UltraScale+ / SU35P device support. Use an OS supported by **both** tools: see [AMD Vitis requirements](https://docs.amd.com/r/en-US/ug1742-vitis-release-notes/Installation-Requirements), [Vivado installation guide](https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license), and [Linux prerequisite installation](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Installing-the-Vitis-Software-Platform). AMD licensing, packages and cable drivers are installed through AMD's normal installer. The target board runs bare-metal firmware; no Linux OS is installed on the SCU35.

Copy `config.example.json` to **`config.json`** and set `tools` to the directory containing `Vivado/` and `Vitis/` and `build_dir` to a **fresh, short local directory**, such as `C:/s35` or `/tmp/s35`. The checkout location is discovered automatically. Paths can also be supplied through `AMD_TOOLS`, `SCU35_BUILD` and `SCU35_CONFIG`; there is no requirement for `C:/aiup` or a particular username/drive. For nonstandard installations, exact `vivado`, `vitis`, `bootgen`, `gcc`, `ar`, `readelf` and `objdump` paths or a `riscv_bin` directory may be set in the same JSON.

```text
python lab.py doctor
python lab.py build
```

The build is deliberately ordered **IPI → XSA → Vitis platform/BSP → application ELF → implemented PDI**. It imports the source BD, validates it, creates standard AMD IP, rebuilds `xilsecure`, `xilpuf` and `xilnvm`, embeds the application in BRAM, and generates the PDI with the stock tool-provided `plm.elf`. No old Vivado project, prebuilt BSP library, board-store installation, or local AI/MCP service is required. The explicit top-level pins/clocks are in `hw/sec_top.xdc`.

For manual practice, the same stages can be run separately:

When importing AMD SHA or LMS/HSS examples into a manually built Vitis
platform, follow the [shared-memory checks](docs/hardware.md#vendor-sha-and-lmshss-shared-memory).
Both the application inputs and DMA-read library scratch must be accessible to
the PMC; CPU-local BRAM alone does not satisfy that requirement.

```text
python lab.py build --phase hardware
python lab.py build --phase platform
python lab.py build --phase firmware
python lab.py build --phase image
```

Use a fresh build directory when restarting a completed or failed hardware/platform creation. Existing results are preserved. Outputs include `ipi/sec.xpr`, `hw.xsa`, `sys.tcl`, `vsw/plat/export/plat/plat.xpfm`, `bench.elf`, `plm.elf`, `design.rcdo`, `demo.pdi`, routed checkpoint, reports, source bindings and `build_manifest.json`. Building `xilnvm` does not run any eFUSE example.

The source checkout may live outside the short build directory, including another drive. Vendor tools have path-length/character and filesystem restrictions: the build directory must be short ASCII without spaces, on a local filesystem supported by the selected OS/tools. No promise is made for arbitrary network shares, synchronized folders, WSL-mounted Windows toolchains, or unsupported OS/filesystem combinations. Windows 2026.1 builds were exercised here; Linux launch paths are provided, with host replay tested separately. A Linux Vivado/hardware run is **not** claimed without evidence.

## High-speed post-configuration user payloads

| Method / block | Working path | What is compared or demonstrated |
|---|---|---|
| SHA3-256 / SHAKE-256 | PL application + hardened PMC; native PMC resident-buffer path | Exact digest, latency and payload throughput. Native logical sizes 16 B through 1 MiB. |
| AES-GCM encryption/decryption | Both paths; native streaming encryption | Exact ciphertext/tag, recovered plaintext, bad-tag rejection. Full ENC/DEC 16 B–8 KiB; streamed ENC 64 KiB/1 MiB validates final chunk plus full-message tag. |
| LMS-SHAKE256 / HSS-SHAKE256 verification | PL XilSecure example and native PMC port | Valid/modified signatures, messages and keys. Native benchmark uses H5/W2 public vectors; HSS has one level. |
| PUF registration / regeneration / PUF-key AES | PL application through PMC Bridge | Volatile helper lifecycle, key clear, same-helper regeneration and AES round trip. Lifecycle timings; no exported secrets. |
| TRNG HRNG / DRNG / PTRNG | PL application, XTrngpsx driver | Setup/self-tests and generation timings. Smoke checks, not entropy certification or Python byte equality. |
| PMC DMA / secure stream routing | Native bulk payload path | Included in measured setup/control/transfer work. Not a host USB/JTAG or HyperRAM bandwidth measurement. |
| eFUSE | Read-only source walkthrough | Register documentation and data-flow explanation. No writer application is built or called. |
| CCU, slave boot, TAP, GLOBAL, OSPI, RV support / RAM ECC | Documented in presenter chapter 3 | Address map and architecture; no completed general-purpose payload, OSPI or ECC-injection qualification is claimed. |

Build the high-speed native firmware separately:

```text
python lab.py native
```

It produces `<build_dir>/native/build/pmc_independent.pdi` and `plm.elf`. It uses the included, hash-checked JTAG/clock PL fixture, whose full RTL/XDC/build source is in `native/fixture/`. This is an **experimental independent PMC loader and benchmark**, separate from the stock AMD secure-boot path. It is retained because it is the fastest measured payload path, not because it replaces the shared vendor-tutorial IPI platform. See [the high-speed notebook](notebooks/08_highspeed.ipynb) and [native details](docs/native.md).

The native timing excludes JTAG upload/readout and preload. Its `mcycle` frequency is estimated against a nominal PL clock; the shared PL application uses **AXI Timer**. Larger messages repeat a resident chunk; these are actual logical messages, not measured external-memory bandwidth. Signature verification is partly software and may be slower than desktop Python. No energy-efficiency or universal hardware speedup claim is made.

## Sign and encrypt a real PDI

After `build`:

```text
python lab.py boot
```

This creates a **new directory and fresh HSS signing state** for each invocation, signs the real stock-PLM/PL PDI using `hss-shake256`, packages AES-GCM rolling-key and combined signed/encrypted images, and independently checks signatures and decryption. Default signing trees are two-level H15/W2. `--height 5` is a faster **packaging exercise**, not a replacement for the demonstrated H15 boot configuration. Never duplicate, restore or reuse old private HSS signing state. Copying/replaying a finished PDI does not consume another signature.

The rolling-key example uses a **public all-zero diagnostic AES root**, selecting the existing eFUSE key source without writing it. It proves no secrecy, no ability to read out an AES key, and no factory/default key value on another board. Acceptance depends on existing provisioning and device settings. The retained SCU35 captures show signed/combo acceptance and negative rejection, while unsigned images were also accepted; production owner-root policy enforcement is not established. Bootgen's HSS `-verify` is unsupported in the recorded installation, so the functional Python verifier is used. The signing script keeps a documented Windows Ctrl-Z key-file workaround by generating fresh independent key sets; it never edits or rewinds a key.

## Explicit hardware runs

Configure your **exact** cable serial, UART port, matching Vivado hardware client/server, known-good recovery PDI and its SHA-256. See [hardware setup](docs/hardware.md). The repository never restarts an existing hardware server. A local reservation prevents overlapping local sessions; coordinate ownership separately for shared/remote servers.

```text
python lab.py hardware --pdi /path/to/build/demo.pdi
python lab.py hardware --mode native --pdi /path/to/build/native/build/pmc_independent.pdi
python lab.py hardware --mode boot --pdi /path/to/build/boot_TIMESTAMP/signed.pdi
```

Use `--mode reject` only for a known intentionally invalid specimen. Every mode attempts recovery in `finally`, verifies DONE/error status, and preserves session logs. A runtime pass additionally requires the strict complete 31-row functional capture; a boot-mode status pass alone does **not** prove payload application success. If recovery fails, the lock is retained and the tool reports failure. Recovery can only be guaranteed as an attempted operation: USB loss, power loss, process termination or a bad recovery image can prevent it. The framework provides no eFUSE/flash programming command.

Compare a fresh capture with new Python measurements:

```text
python lab.py compare --capture /path/to/runtime/run/uart.txt --out out/runtime.html
python lab.py compare --native --capture /path/to/native/run/results.txt --out out/native.html
python lab.py inspect --pdi /path/to/build/demo.pdi --elf /path/to/build/plm.elf
```

Use the complete native session directory, including matching `test.pdi`, `plm.elf`, public vectors and metadata, so the analyzer can bind the capture to the exact image. The runtime parser binds the firmware ID and validates every retained correctness record; fresh build manifests provide the additional ELF/PDI source binding.

## Files and practice route

1. [Shared IPI, addresses and platform](docs/scu35_presenter.html): inspect BD → export XSA → inspect BSP.
2. [Notebooks](notebooks/): Python and retained hardware correctness/timing, then explicit fresh hardware runs.
3. [PDI notebook](notebooks/09_pdi.ipynb): inspect PLM ELF, CDO/RCDO and PDI manually with installed Bootgen/readelf.
4. [Audit checkpoints](docs/audit.md): save tool versions, hashes, full logs, correctness, timing and recovery separately.

`reference/` holds the exact demonstrated PDI/ELF/XSA/DCP artifacts. `reference/rebuilt/` is the clean reproduction build produced for this branch: it passes implementation checks but has **not** been run on hardware. Use `reference/timer/` and `reference/native/` when replaying the recorded benchmark results. `evidence/` holds dated raw captures, reports and original metadata. Historical files can mention their original machine paths; **new code does not depend on those paths**. New build outputs are separate, never silently labeled hardware-tested. Public demonstration values and signatures are included; private HSS state and `.nky` files are excluded. Do not substitute the older protected boot PDIs for the new AXI Timer runtime image when describing timer provenance.

[Handoff checks](handoff.json) record build, correctness, file-integrity and portability gates separately. Windows/Linux host replay is covered by [GitHub Actions](https://github.com/AEW2015/amd_examples/actions/workflows/scu35.yml). Full AMD implementation was exercised on Windows 2026.1; a Linux Vivado implementation and a new hardware run are not claimed.

`skills/scu35-pmc/SKILL.md` is the portable AI entry point. Two small Vivado workflow skills are included as supporting guidance. They are plain Markdown, optional, and installable in an agent's skill directory; no specific AI provider is required. [AGENTS.md](AGENTS.md) captures the board scope and loaner rules.

To edit/rebuild the teaching material, edit the HTML/CSS/JS under `docs/presenter/` or the notebook source in `scripts/make_notebooks.py`, then run:

```text
python scripts/make_notebooks.py
python scripts/execute_notebooks.py
python scripts/refresh_presenter.py
python scripts/check_links.py
python scripts/make_manifest.py
python lab.py verify
```

These commands regenerate teaching material and replay saved data; they do not run hardware. Optional browser QA is `scripts/check_presenter.py`, requiring Playwright and a browser supplied through `SCU35_BROWSER` or Playwright's installed Chromium.

Source licensing follows the repository MIT license, with AMD MIT notices preserved in vendor example/driver-derived source. Installed AMD tools/IP and generated vendor firmware remain subject to their own applicable licenses; no AMD installer, license key, prebuilt SDK library or restricted security-register manual is distributed. [Vendor source pins](vendor_sources.json), [register links](docs/presenter/register_links.json), and [third-party notices](THIRD_PARTY.md) identify provenance.
