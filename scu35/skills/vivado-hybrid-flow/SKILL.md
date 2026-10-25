---
name: vivado-hybrid-flow
description: Choose between direct Tcl and AMD MCP for Vivado builds, IPI/IP operations and design inspection when the vivado-hybrid-c server is available. Use for the hybrid C workflow, not unrelated FPGA tools or benchmark result analysis.
---

Use the user's requirements and acceptance criteria to choose the execution path. C permits both paths; neither has a mandatory invocation count. It combines guidance with economical execution, not weaker verification.

- Query `c_environment` once to establish configured tools. This checks paths, not tool/version or license usability. Verify the required Vivado version and target part with a small saved Tcl query when needed.
- Prefer a saved direct Tcl entrypoint for reproducible synthesis, implementation, reports and image generation. Launch through `c_start_batch`; use `c_job_status` with a meaningful wait instead of rapid polling. Keep the entrypoint and its dependencies unchanged during execution.
- Use AMD delegation when persistent project/IPI context, IP discovery/configuration or an existing AMD helper changes the decision. Request the concise `c_upstream_tools` catalog, then load the schema for just the chosen tool. `c_upstream_call` starts the AMD backend on demand. Preserve session IDs and stop only sessions you own.
- If an applicable AMD skill is present, read that skill and only relevant references. Do not preload every skill/manual. If it is absent, use public/installed documentation and preserve the source/version of any material decision.
- Keep full logs on disk. Read a pointed excerpt when a compact preview is insufficient; truncated output is not evidence that warnings disappeared. Batch independent reports into one Tcl script rather than issuing many model-mediated calls.
- Use the first meaningful failure to choose a repair. A failed backend may justify switching paths; record the reason, failed attempt and recovery rather than hiding the substitution. Do not assume a different backend cures a design defect.
- Apply the user's resource/job and hardware scope to both paths. The server's direct-job cap does not cap Vivado `launch_runs -jobs`, upstream jobs or shell processes; the agent must honor the overall cap.

Apply `vivado-windows-sim` for Windows simulation launch problems and `vivado-evidence-handoff` before delivering. Neither handoff readiness nor client/tool exit status is independent design acceptance.
