# AC02 GstarCAD frozen validation plan

> Execute natively in this session. This is verification of existing behavior, not feature implementation. No additional feature specification or product change is planned.

**Goal:** Build the fixed AC02 source into a separate validation runtime and verify actual GstarCAD output, GUI and coexistence.

**Architecture:** Preserve previous MAIN/runtime. Use the existing packaging scripts at pinned product source c6bb03f8326aa854b753ba8631ec0d8ed11264b8, approved43 input manifest and the current PC's GstarCAD settings. Keep source, frozen and UI evidence distinct.

**Tech Stack:** Windows, Python3.12, PyInstaller, GstarCAD2026, Common Item Dialog, PDF rendering and SHA256.

**Spec:** docs/autocad/AC02-OTHER-PC-GITHUB-2026-10-07.md; docs/superpowers/specs/2026-10-07-explorer-path-picker-design.md.

## Global constraints

Preserve original hashes/mtime and existing user CAD. Only APP-owned CAD may be controlled/closed. Keep 13 profiles,43 approved samples,monochrome.ctb with residual colors accepted and title-block overlap accepted. No security policy changes,customer upload,MAIN merge,installation replacement or GitHub publication.

## Review focus

Old EXE must not substitute for AC02. Frozen environment must not depend on development PYTHONPATH. Cancellation must create no CAD/output. Files and folders must both use Explorer-style dialogs. A successful CLI run is not a GUI acceptance result.

## Task1: Separate build

- [x] Run fresh offline regression and record PASS/SKIP/deselect.
- [x] Verify candidate dist is absent; run packaging/build.ps1 with explicit Python and approved source root.
- [x] Require exit0,self-check and VALIDATION_BUNDLE_OK; record product/EXE/ZIP hashes.

## Task2: Frozen43 acceptance

- [x] Run exact new EXE in a clean child environment against approved43 into a new output folder.
- [x] Monitor existing/new CAD identities; verify all originals unchanged and owned CAD closed.
- [x] Check source43 manifest scale/rotation/window acceptance, then compare frozen PDF structure and144dpi rendering against those source outputs. Frozen CLI does not expose an internal decision trace; pixel equivalence is output evidence, not a fresh internal trace.

## Task3: GUI/coexistence

- [x] Use official Computer Use for actual file/input-folder/output-folder UI observation.
- [x] Confirm cancellation separately at all3 stages. Each picker and launcher closed without starting conversion. During the concurrent43 test only its one owned CAD was observed; no separate per-cancellation process monitor was used.
- [x] Confirm address manipulation and file multi-select/folder input using new output folders.
- [x] Verify actual success completion dialog,PDF/inputs and existing user CAD preservation separately.
- [x] Computer Use was available; blocked-environment fallback was not needed.

## Task4: Handoff

- [x] Record verified facts and remaining AutoCAD/frozen/GUI gaps in a local report.
- [x] Preserve old/new artifacts; no publication or installation change in this task.

Result: docs/autocad/AC02-PC-A-FROZEN-VALIDATION-2026-10-07.md.
