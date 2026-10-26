# Saved notebook execution evidence

`executions.json` records the 11 PMC notebook executions whose outputs are saved
in the repository. Six runtime notebooks each made a new 31-row SCU35 UART
capture and fresh Python measurements. Two boot notebooks verified the real
IPI image variants offline and checked programming/recovery on hardware.
The start, PDI and hardware-guide notebooks executed host checks, inspections
and Python measurements with their runtime hardware flags disabled.

Each fresh hardware session directory retains its actual session status,
programming/recovery logs and, for runtime, raw UART and comparison data.
`boot_images/` contains the public images tested by the boot notebooks and the
public verifier. Its AES root is explicitly public all-zero diagnostic data.
No private signing state, enrollment data, PUF keys or fuse writers are included.

The separate `ethernet/demo.ipynb` now includes a later fresh physical-Ethernet
execution: volatile programming, packet tests and benchmarks, fresh Python
timings and verified recovery. Its evidence is in `ethernet/evidence/run3/`.
Earlier dated Ethernet captures remain under their original run directories.

Execution notes are in UTC; these sessions occurred on October 25, 2026 in the
lab's America/Denver timezone. Restore success means the selected recovery PDI
had clean programming status, not proof of factory provisioning or policy.
