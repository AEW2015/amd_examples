# Source and asset provenance

- AMD `embeddedsw` example/driver-derived code retains its original MIT notices. Public example source is pinned in `vendor_sources.json` to `xlnx_rel_v2026.1`, commit `b5cd5477bb44b9fadd98be10ea2f12705b9287f3`. `fw/bench.c` combines that public LMS/HSS vector example with the lab's runtime harness; `fw/vendor/hss.c` preserves the original example.
- The handwritten PMC BSP, independent firmware, host reference verifier, Tcl build flow, notebooks and presentation packaging are supplied under the parent repository MIT license. The Python verifier is educational, not a production cryptographic library.
- The SCU35 photograph is an AMD vendor product image, not a photograph of the tested loaner. Presenter captions and `docs/presenter/assets/board_source.json` (when present) identify the original source. AMD trademarks and tool/IP licensing are unchanged.
- Screenshots are renders of saved reports/executed notebook outputs. Block-design SVG/PDF exports originate from the real Vivado design. Conceptual diagrams are labeled separately.
- Reference PDI/ELF/XSA/DCP files are generated demonstration artifacts. No AMD installer, license, prebuilt SDK library archive or access-controlled documentation is included. Obtain the required installed AMD tools and device support through AMD under their applicable terms.
- Python dependencies are installed through `requirements.txt` and retain their upstream licenses. No third-party Python package code is vendored.
