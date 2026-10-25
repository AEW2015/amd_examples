# Handoff manifest

Paths are relative to the C server's selected workspace. Each artifact is a nonempty file with its final SHA-256. One file may satisfy multiple roles through separate entries if appropriate. Use task-specific roles; names are not hard-coded by the server.

```json
{
  "overall": "INCOMPLETE",
  "artifacts": [
    {"role": "rtl", "path": "deliverables/math_core.sv", "sha256": "actual-final-64-hex-digest"},
    {"role": "rebuild", "path": "scripts/rebuild.tcl", "sha256": "actual-final-64-hex-digest"},
    {"role": "programming_image", "path": "deliverables/design.pdi", "sha256": "actual-final-64-hex-digest"}
  ],
  "checks": {
    "rtl": {"status": "pass", "evidence": "logs/rtl.log"},
    "routed_timing": {"status": "incomplete", "evidence": "reports/timing.rpt"}
  }
}
```

Replace example paths/digests with real values. Gate status is `pass`, `fail` or `incomplete`; overall is `PASS`, `FAIL` or `INCOMPLETE`.

Example tool arguments: `manifest="result.json"`, `required_roles=["rtl","constraints","rebuild","routed_checkpoint","programming_image"]`, `required_checks=["rtl","routed_timing","drc"]`. Derive the list from the actual task rather than copying these example requirements blindly.

The checker does not parse simulation/timing content, verify a checkpoint's source binding, prove a programming image matches a checkpoint, or independently certify a client-authored pass. Those checks remain separate. Files referenced as check evidence need not be artifacts, but their hashes should be included as artifacts when integrity is part of the requested handoff.
