# Task 7A core conversion report

## Scope

Implemented the bounded R3 core-conversion prerequisites only:

- explicit DWG input resolution (`input_resolver.py`)
- two-snapshot input stability gate (`file_stability.py`)
- scale-free output naming (`output_planner.py`)
- PDF conflict policy resolution (`conflict_resolver.py`)
- caller-owned-session `ConversionService.convert_in_session()` (`conversion_service.py`)

No batch-session replacement, `run_jobs`, result summary, CLI, GUI, ModelSpace/Blocks full enumeration, filename-scale inference, or real COM exercise was added.

## RED evidence

Tests were added before any Task 7A production modules.

```text
python -m pytest --basetemp C:\Users\dknbtech\Documents\APP 개발\.codex-test-tmp\task-7a-red \
  tests/unit/test_input_resolver.py tests/unit/test_file_stability.py \
  tests/unit/test_output_planner.py tests/unit/test_conflict_resolver.py \
  tests/integration/test_conversion_service.py

collected 0 items / 5 errors
ModuleNotFoundError: No module named 'dwg_to_pdf.input_resolver'
ModuleNotFoundError: No module named 'dwg_to_pdf.file_stability'
ModuleNotFoundError: No module named 'dwg_to_pdf.output_planner'
ModuleNotFoundError: No module named 'dwg_to_pdf.conflict_resolver'
ModuleNotFoundError: No module named 'dwg_to_pdf.conversion_service'
```

The collection failures were expected: the requested modules did not yet exist.

## GREEN evidence

```text
python -m pytest --basetemp C:\Users\dknbtech\Documents\APP 개발\.codex-test-tmp\task-7a-green \
  tests/unit/test_input_resolver.py tests/unit/test_file_stability.py \
  tests/unit/test_output_planner.py tests/unit/test_conflict_resolver.py \
  tests/integration/test_conversion_service.py

collected 14 items
14 passed in 0.45s
```

The mock integration test proves that the supplied session's `working_document()` boundary is used and that `apply_plot_settings()` receives only `decision.candidate.plot_window`. It does not create, enter, exit, quit, or kill a `GstarSession`.

During self-review, an additional sleep-boundary regression test was added before its one-line exception-boundary fix:

```text
python -m pytest --basetemp C:\Users\dknbtech\Documents\APP 개발\.codex-test-tmp\task-7a-sleep-red tests/unit/test_file_stability.py
2 passed, 1 failed
E OverflowError: too large

python -m pytest --basetemp C:\Users\dknbtech\Documents\APP 개발\.codex-test-tmp\task-7a-sleep-green tests/unit/test_file_stability.py
3 passed in 0.06s
```

## Full non-COM regression evidence

```text
python -m pytest --basetemp C:\Users\dknbtech\Documents\APP 개발\.codex-test-tmp\task-7a-full-final -m "not gstarcad"

collected 321 items / 5 deselected / 316 selected
315 passed, 1 skipped, 5 deselected in 1.44s
```

The required dependency/runtime environment was used for all commands:

```text
PYTHONPATH=<deps>\win32\lib;<deps>\win32;<deps>;src
PATH includes <deps>\pywin32_system32;<deps>
PYTHONDONTWRITEBYTECODE=1
```

## Self-review

- `resolve_inputs()` only accepts explicit DWGs and immediate directory DWGs, resolves case-insensitive duplicates, sorts deterministically, and fails closed with `E100` when none are valid.
- `require_stable()` compares `(st_size, st_mtime_ns)` snapshots and maps change/stat/sleep-boundary failures to `E215`.
- `output_names()` produces `A.pdf`, `A_2.pdf`, etc.; zero or negative integer frame counts return an empty tuple, while boolean/non-integer counts are rejected.
- Existing PDFs are never altered by `copy`, `skip`, or `ask`; `copy` follows `part - 복사본.pdf`, then `part - 복사본 2.pdf`; `skip`/`ask` fail closed with `E500`.
- The service requires calibrated automatic matching, uses `SourceWorkspace` outside the caller-provided session document context, detects the Scale cell with `DetectionLimits(64, 5000)`, uses canonical profile matching/rotation verification, plots only the computed candidate window, and delegates validation plus atomic publication to `publish_pdf`.

## Limits / remaining verification

- Real GstarCAD COM was deliberately not retried: the known `DispatchEx` environment blocker is outside this bounded prerequisite task.
- The mock integration proves lifecycle ownership and plot-window wiring, while actual GstarCAD plotting remains covered only by the existing opt-in `gstarcad` test marker.
- `git` is not currently available on this shell's executable path and no standard Git installation location was present, so this task could not create its requested commit from this environment.

## Review-fix evidence (follow-up)

The review identified a publication-order defect: the first implementation called `publish_pdf()` before the successful `SourceWorkspace` exit identity gate. A source mutation after plotting could therefore replace a prior final PDF before `SourceWorkspace` reported `E400`.

### Review RED

```text
python -m pytest --basetemp C:\Users\dknbtech\Documents\APP 개발\.codex-test-tmp\task-7a-review-red \
  tests/unit/test_input_resolver.py tests/unit/test_file_stability.py \
  tests/unit/test_output_planner.py tests/unit/test_conflict_resolver.py \
  tests/integration/test_conversion_service.py

collected 25 items
9 failed, 16 passed in 0.40s
```

The failures proved: the missing `ask` prompt seam, missing bounded copy-name constant, raw `FileNotFoundError` after `require_stable()`, and that publication occurred before the source-workspace identity exit. The source-mutation regression writes a valid nonblank temporary A4 PDF, mutates the source after a successful plot, and asserts that the old final remains unchanged and the owned temporary is removed.

### Review GREEN

```text
python -m pytest --basetemp C:\Users\dknbtech\Documents\APP 개발\.codex-test-tmp\task-7a-review-green2 \
  tests/unit/test_input_resolver.py tests/unit/test_file_stability.py \
  tests/unit/test_output_planner.py tests/unit/test_conflict_resolver.py \
  tests/integration/test_conversion_service.py

collected 25 items
25 passed in 0.37s
```

Changes verified by these tests:

- `publish_pdf()` now runs only after successful exit from both the caller-provided document context and `SourceWorkspace`; the outer failure path removes only the one service-owned temporary PDF and adds any cleanup failure as a note to the original exception.
- `resolve_collision(path, "ask")` uses the narrow `_prompt_conflict()` helper. Existing-output responses accept case-insensitive `overwrite` and `copy`; `skip`, invalid input, EOF, and prompt errors all preserve the existing file and fail closed with `E500`.
- `MAX_COPY_NAME_ATTEMPTS` bounds sequential candidate checks without a directory-wide scan; exhaustion is stable `E500`.
- Source disappearance/resolve errors after `require_stable()` are normalized to `AppError("E100", ..., source)`.
- The strengthened integration test uses a `GetWindowToPlot()` sentinel that fails on any saved-Plot-Window getter access. It observes `plot -> identity -> publish`, wraps the real `publish_pdf()`, and retains the real `SourceWorkspace` identity boundary.

### Review full non-COM regression

```text
python -m pytest --basetemp C:\Users\dknbtech\Documents\APP 개발\.codex-test-tmp\task-7a-review-full -m "not gstarcad"

collected 331 items / 5 deselected / 326 selected
325 passed, 1 skipped, 5 deselected in 1.48s
```
