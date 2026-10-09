# AC02 local MAIN integration and rollback plan
> **For agentic workers:** Use superpowers:executing-plans for this approved inline integration.
**Goal:** Integrate the reviewed AC02 source locally while preserving the exact pre-merge MAIN and its tracked runtime for other-PC recovery.
**Architecture:** Preserve Git branch/tag plus a standalone offline bundle and ZIP of previous MAIN. Keep previous and candidate environments in separate directories; prepare recovery without reset, clean, CAD commands or overwrites.
**Tech Stack:** Git, Windows PowerShell 5.1/7, ZIP, existing frozen runtime.
**Spec:** User instruction dated 2026-10-07: local MAIN merge approved; failures on another PC must be recoverable to existing MAIN materials/code.

## Constraints
- Baseline MAIN: 30d6f23996035784154f3c306641488bcd2879bf.
- Reviewed product: ca11b14c6123fa952f999c0d4bf2b0f444f4c70b.
- Preserve all user work and failure evidence. No CAD process changes.
- No GitHub push, official release or installed-runtime replacement in this local merge.
- Existing right-bottom text overlap accepted/ignored. Historical E203 root cause remains unconfirmed.

## Tasks
- [x] Preserve baseline branch codex/backup-main-before-ac02-20261007 and tag rollback-main-before-ac02-20261007.
- [x] Add rollback guide, current-PC validation handoff and native-command offline preparation.
- [x] Exercise recovery via PowerShell5.1 console commands, Unicode/space paths, hashes and intentional failures. Ruling: script execution is policy-blocked; keep policy unchanged and ship console commands instead.
- [ ] Commit docs/console commands on isolated AC02 worktree; retain reviewed product bytes.
- [ ] Merge locally with --no-ff; tag integration for reversible git revert -m1.
- [ ] Run full offline regression on merged MAIN; preserve CAD43 and GUI evidence for identical product.
- [ ] Build portable previous-MAIN source ZIP/runtime ZIP/Git bundle and manifests outside the repository.
- [ ] Verify isolated previous-MAIN HEAD, runtime self-check and negative cases. Record all results.
