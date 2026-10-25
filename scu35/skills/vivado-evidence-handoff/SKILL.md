---
name: vivado-evidence-handoff
description: Deliver a reproducible Vivado design with source bindings, required images, hashes and honest gate evidence. Use before handing off a Vivado build, including hybrid C; does not replace independent functional verification or program hardware.
---

Map the user's deliverables and acceptance gates before the final handoff. Avoid imposing a universal image or test type: require PDI/BIT/ELF/XSA, RTL/IP constraints and hardware evidence only where the task needs them.

- Bind simulation and implementation to the delivered source and constraints. Keep exact compile/source lists and content hashes. If a repaired alternate source was implemented, make the standalone rebuild use it and say which file is canonical; testing another same-interface module does not certify the built design.
- Preserve reproducible scripts, required routed checkpoint/programming image, reports and executable tests. Generate the requested native image rather than assuming a routed checkpoint is interchangeable with it. Hash final files after the last modification; include the actual image and any packaging inputs.
- Separate correctness, routed timing/coverage/DRC/resources, licensing, reproducibility, hardware and handoff gates. Preserve original required clocks, pins, delays and interfaces. Changing constraints or disabling checks is not an equivalent timing repair.
- Ready/valid and reset tests must cover the specified behaviors. Preserve failed attempts. Tool success, positive WNS and a client-authored PASS declaration are evidence about different gates.
- Write a manifest with `overall`, `artifacts` and `checks` using the [schema and example](references/manifest.md). Use `c_check_handoff` with task-derived required roles/checks. Repair missing/empty files and hash mismatches. Its readiness verdict validates evidence presence and integrity only; inspect the reports/tests to judge their content.
- Deliver PASS only if every required gate has supporting execution evidence; otherwise label FAIL or INCOMPLETE and identify remaining work. Report tool/skill usage and recovery choices accurately. A compact summary should point to full evidence rather than dumping it into the conversation.
