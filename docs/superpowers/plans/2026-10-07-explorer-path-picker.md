# GUI-01 Explorer Path Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Codex implements inline; model/effort changes require prior user notice.

**Goal:** DWG 파일·입력 폴더·출력 폴더 선택을 주소 표시줄이 있는 Windows 공통 선택창으로 통일한다.

**Architecture:** `windows_picker.py` owns native COM calls and resource cleanup. DesktopUI keeps its existing contract and delegates only the three path selectors to this adapter. CAD/provider selection and conversion remain unchanged.

**Tech Stack:** Existing Python runtime, standard-library ctypes, Windows Common Item Dialog; no additional package.

**Spec:** `docs/superpowers/specs/2026-10-07-explorer-path-picker-design.md` REV01. Implementation starts after document review approval.

## Global Constraints

- Existing13 templates,scale/rotation/plot policies,original protection,singleAPP-ownedCAD,userCAD protection and failure isolation unchanged.
- Keep requested6.1 SOL/Medium; notify user before needed changes.
- Only file/input-folder/output-folder selection changes; CAD install list and result UI remain unchanged.
- Keep imports safe for `--help`/`--self-check`; initialize native UI lazily.
- Cancellation returns empty values; non-cancellation errors must not be swallowed.
- Preserve prior validation bundle before building; no Desktop replacement,MAIN integration or official publication.

## Review Focus

- Unicode/space paths must be preserved exactly without shell quoting/encoding round-trips.
- Folder mode must not inherit conflicting file-only/multiselect restrictions.
- Partial native failures must release interfaces and strings and balance only successful COM initialization.
- Cancellation at any path step must not create CAD sessions or call conversion.
- Frozen EXE must actually display the new dialogs; unit mocks/self-check alone are insufficient.

### Task 1: Native dialog adapter and DesktopUI wiring

**Files:**
- Create: `src/dwg_to_pdf/windows_picker.py`
- Modify: `src/dwg_to_pdf/desktop_launcher.py`
- Create: `tests/unit/test_windows_picker.py`
- Modify: `tests/unit/test_desktop_launcher.py`

**Interfaces:**
- Consumes: Windows `IFileOpenDialog`/`IShellItem`/`IShellItemArray` with STA COM initialization.
- Produces: `pick_dwg_files(title: str) -> tuple[str, ...]`, `pick_folder(title: str) -> str`.
- DesktopUI public method signatures and `run_desktop` CLI arguments unchanged.

- [ ] **Step1 RED:** Add tests for file multi-selection preserving literal paths `D:/도면 입력/a.dwg` and `D:/도면 입력/b.dwg`; folder result `D:/PDF 출력`; only cancelled HRESULT yields empty; other Show/GetResult failure yields OSError; success/cancel/partial error release and initialization-failure no-uninitialize. Update old subprocess-picker tests to new native-boundary behavior. Verify the missing adapter/old backend fails for the intended reason.
- [ ] **Step2 GREEN:** Implement lazy ctypes native adapter using `IFileOpenDialog`, preserving default options; DWG filter/multiselect for files; folder mode with `FOS_PICKFOLDERS`. Return filesystem Unicode paths and release every owned interface/allocated string. Wire only three DesktopUI selectors.
- [ ] **Step3 focused verification:** `python -m pytest -q tests/unit/test_windows_picker.py tests/unit/test_desktop_launcher.py tests/unit/test_cad_desktop.py`; Expected:0 failures,all cancellation/error/CLI tests pass.
- [ ] **Step4 full verification:** `python -m pytest -q --basetemp=<fresh workspace path> --junitxml=<local report>`; Expected:0 failures/errors; SKIP named separately. No live CAD opt-in inferred.
- [ ] **Step5 commit:** Stage only the adapter,DesktopUI and associated tests; commit `feat: use Explorer-style native path dialogs`.

### Task 2: Validation EXE, actual UI/conversion and handoff

**Files:**
- Read/run: `packaging/build.ps1`, `packaging/dwg_to_pdf.spec`, `packaging/verify_bundle.ps1`
- Modify only if verified packaging need: `packaging/dwg_to_pdf.spec`
- Create: `docs/autocad/GUI-01-HANDOFF-2026-10-07.md`
- Build outputs: ignored local `dist/` and `.pytest-tmp/`, never customer artifacts in Git.

**Interfaces:**
- Consumes: Task1 DesktopUI and safe lazy imports.
- Produces: New validation ZIP/hash,actual dialog acceptance evidence and explicit NOT_RUN list.

- [ ] **Step1 preserve/build:** Copy prior validation ZIP to a new no-overwrite backup; verify hash. Run existing approved build/preflight/verifier. Expected:`RUNTIME_SELF_CHECK_OK`,`VALIDATION_BUNDLE_OK`,exit0. Test any new packaging failure before changing packaging.
- [ ] **Step2 actual UI:** Use Computer Use on the new EXE: address-bar paste/selection on file mode and both folder dialogs,plus cancel. Expected:Explorer-style windows and exact paths; cancelled flow does not start CAD. Never automate terminal apps or bypass security dialogs.
- [ ] **Step3 actual CAD:** Run folder and multi-file modes against existing approved ESS7 inputs,each to a new local output folder. Record all7 success,originalhash/mtime,userCAD preserved,oneAPP-ownedCAD closed; inspect PDF single/nonblank/A4 landscape and full renders. Expected:successfully validated outputs; do not infer dimensional semantics.
- [ ] **Step4 report/commit:** Write measured results,failures/retries,model,source/runtime hashes and limits. Full suite rerun before completion. Commit only source packaging changes if needed and public handoff. OtherPC/AutoCAD latest,MAIN/release and Desktop install remain separate gates.

## Execution and approval

The user approved the short design and requested written planning before work. This spec/plan pair awaits document review; do not treat initial concept approval as document review. After approval Codex executes inline on the preserved isolated repository, using TDD and verification-before-completion. No sub-agent/model escalation is presumed necessary for this bounded change.
