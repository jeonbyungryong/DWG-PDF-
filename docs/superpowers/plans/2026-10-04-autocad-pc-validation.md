# AutoCAD 2021 PC validation fixes

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Follow superpowers:test-driven-development.

**Goal:** Correct the failures observed at a546c4f on the second PC and rerun supported validation gates.

**Architecture:** Keep existing ownership proof, temporary documents and common conversion logic. Add an AutoCAD readiness hook, remove the premature PaperUnits assignment, and preflight the bundled unsigned LISP against the existing AutoCAD trust policy, using the existing COM fallback when unavailable.

**Tech Stack:** Windows x64, Python 3.12, pywin32, pytest, installed AutoCAD 2021.

**Spec:** ../specs/2026-10-02-autocad-support-design.md

## Execution ledger (2026-10-04, second PC)

- Tasks 1–3 implemented with failing reproduction tests followed by passing focused checks.
- Live driver evidence required two additional bounded corrections: AutoCAD 2021 emits duplicate catalogue `/PageMode` entries; its default PDF driver opens Adobe Reader, which locks the temporary file even after owned CAD exit.
- Catalogue compatibility is opt-in for AutoCAD and operates on an in-memory copy only. Other duplicate dictionary keys remain strict failures. Zero-rotation PDF bytes remain intact; the separately measured rotation path below rewrites only the owned temporary PDF.
- Added optional AutoCAD-only `plot.autocad_pc3_path`, an existing absolute `DWG To PDF.pc3` path, forwarded through the documented `PlotToFile` optional configuration argument. No product PC3 editing or viewer termination. The local validation fixture disables only `View_New_File`; installed PC3 bytes/mtime are preserved.
- Basic live preservation/failure-isolation tests: 2 PASS, 33.71 sec.
- Final offline suite: 809 PASS, 13 SKIP, 33.77 sec.
- Independent review: no actionable findings; reviewer ran 86 PASS/1 SKIP for the initial fixes, then 77 PASS for PC3/configuration/service checks.
- Approved-template-derived variants: 5 scales × (shift, rotate90/180/270, blank, N/A) = 30; source identities/user CAD preserved and owned generator CAD exited.
- Final live suite: 3 PASS, 1696.80 sec. The 13+30 OFF/ON matrix produced 86 PDFs; an independent read-only audit verified all 86 expected scale/rotation/window decisions, A4 landscape dimensions, Rotate=0, monochrome and nonblank rendering. Source hashes/mtime and existing user CAD were preserved; owned CAD exited. ON uses read-only trust preflight and COM fallback under this PC's SECURELOAD=1/untrusted bundled script policy; no native LISP execution success is claimed.
- G3 and G5 remain NOT_RUN; no main merge or release.
- First matrix reproduced E420 on the 180-degree variant. Four-angle probes showed that direct AutoCAD PlotRotation plus removal of expected inverse PDF Rotate metadata renders upright A4 landscape. Blindly clearing metadata under the old inverse mapping rendered quarter-turn content upside down and was rejected.
- Rotation correction is restricted to the measured COM version `24.0s (LMS Tech)`, A4 landscape MediaBox, one unencrypted page and expected inverse metadata. It clones the PDF document and checks vector content preservation; other patterns fail closed. Final output still requires Rotate=0 and A4 landscape.
- Real template color audit found 40 RGB objects bypassing monochrome CTB. AutoCAD-only preparation bounds layers, block definitions and attached/constant attributes before changing nonwhite RGB to CTB index 7 on the authorized temporary drawing. White masks, geometry, lineweight and original source are preserved. External block definitions are rejected.
- Four-angle product-path verification: 4 PASS, expected 1:1 scale/angles, A4 landscape/Rotate=0, rendered maximum RGB channel difference=0, source identities/user CAD preserved.
- Independent review found one P2 in attached-attribute color traversal. Regression reproduced failure; bounded attached/constant traversal fixed it. Reviewer independently reran 23 PASS and found no further actionable issue.
- The pre-attribute-fix matrix was ended through a controlled test-output directory conflict (2 PASS / 1 injected failure), allowing normal CAD/session cleanup. It is excluded from final success evidence. The fresh matrix above passed on the reviewed final code.

## Global constraints

- Only ownership-proven APP CAD processes and temporary drawing copies.
- Preserve existing 13 profiles, source hashes/mtime and user CAD processes.
- Do not change SECURELOAD or TRUSTEDPATHS; do not merge main or publish a release.
- GstarCAD is absent on this PC: G3 remains NOT_RUN. No claim of complete G5 without its prerequisites.

## Review focus

- Busy startup and permanent COM failures must have distinct outcomes and bounded readiness waiting.
- Failure during readiness must release owned handles/process/mutexes.
- Driver information must be refreshed before plot unit assignments.
- Untrusted or unreadable LISP security policy must not trigger a blocking load prompt.
- Multiple A4 media must remain an explicit selection; the local test chooses measured ISO_A4_(297.00_x_210.00_MM).

### Task 1: Plot environment ordering

Files: src/dwg_to_pdf/autocad/plotting.py; tests/unit/test_autocad_plotting.py.

- [x] Add a layout boundary rejecting PaperUnits until device information is refreshed; confirm existing plot_pdf fails.
- [x] Remove the early PaperUnits write. require_plot_environment refreshes the selected device; apply_plot_settings sets millimeters afterward. ActiveX paper dimensions are millimeters regardless of display units.
- [x] Run plotting tests and live COM conversion with the explicit measured A4 medium.

### Task 2: AutoCAD readiness

Files: src/dwg_to_pdf/cad/com_session.py; src/dwg_to_pdf/autocad/com_session.py; tests/unit/test_autocad_session.py.

- [x] Test startup call rejection, non-quiescent state, timeout, permanent error and ownership-preserving cleanup.
- [x] Add a no-op base readiness hook, invoked only after ownership proof. AutoCAD waits for quiescence/Documents availability using bounded monotonic polling and pumping messages. Never retry drawing mutations.
- [x] Run session tests and live startup/COM conversion.

### Task 3: Native trust preflight and validation

Files: src/dwg_to_pdf/autocad/native_extract.py; tests/unit/test_autocad_native.py; docs/autocad/VALIDATION.md.

- [x] Test untrusted, trusted, recursive trusted, disabled and unreadable security policy.
- [x] Read existing security policy before LISP load. If bundled script is not explicitly trusted under secure loading, raise NativeExtractionUnavailable so the established COM extraction path runs. Do not change the policy or retry SendCommand.
- [x] Run focused/full offline tests; run live template and failure isolation cases with preserved source/user PIDs.
- [x] Prepare variants only from approved temporary template copies, run 13+30 comparison where environment permits, and record blocked gates and actual native fallback.
- [x] Review final diff and record evidence, limitations and next steps.
