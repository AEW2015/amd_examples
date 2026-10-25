# SCU35 lab rules for AI assistants

- Target only XCSU35P-SBVB625-2-E / SCU35. Read `skills/scu35-pmc/SKILL.md` first.
- Preserve the shared AXI Timer design for vendor runtime tutorials; native PMC throughput is a separate advanced fixture/firmware path.
- No eFUSE, flash, persistent enrollment, revocation or lockdown writes. Never run the stock XilNvm main as a read-only example.
- Build/replay is not hardware authorization. For an authorized hardware session use exact cable selection, matching hardware-server client, reservation, timeouts and verified recovery.
- Do not restart another user's hardware server or other clients. Keep hardware actions explicit.
- Use short local build paths and short project names (12 characters or fewer preferred). Keep generated files out of Git.
- Discover repository/tool paths from configuration; do not add usernames, drive letters, cable serials or COM numbers to executable defaults.
- Never commit private HSS state, `.prv`, `.aux`, `.nky`, credentials, vendor installers, license files or restricted manuals. Never roll back or clone used HSS signing state.
- Keep hardware success, payload correctness, timing, recovery, offline verification and cross-OS portability as separate evidence gates. Do not relabel old `mcycle` or custom-counter results as AXI Timer results.
