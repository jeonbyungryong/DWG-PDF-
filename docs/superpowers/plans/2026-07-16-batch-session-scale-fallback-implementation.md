# Batch Session and Scale Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revise the DWG-to-PDF application so one proven-owned GstarCAD process handles a sequential batch, individual file failures do not stop later files, and blank or `N/A` Scale cells use unique structural matching against exactly 13 approved template profiles.

**Architecture:** `GstarSession` owns one newly created GstarCAD process and exposes an explicit document close boundary so many documents can be processed sequentially without changing PID. Scale-cell inspection becomes a stateful detector that distinguishes valid, blank, `N/A`, and invalid values; valid values restrict matching to one profile while blank/`N/A` values evaluate all 13 approved profiles. A batch runner owns session replacement after a broken document/COM boundary and accumulates stable user-facing errors for one final result dialog.

**Tech Stack:** Python 3.11+, pywin32 COM automation, GstarCAD 2026 (`GStarCAD.Application.26`), pytest, JSON Schema profile store, Windows PowerShell.

## Global Constraints

- The supported universe is exactly the 13 approved template scales: `1:1`, `1:2`, `1:5`, `1:10`, `1:20`, `1:50`, `1:100`, `2:1`, `5:1`, `10:1`, `20:1`, `50:1`, and `100:1`.
- One APP-owned GstarCAD process serves the batch; only a proven-owned PID may be quit or force-killed.
- User-started GstarCAD processes are never attached to, closed, or killed.
- Only one DWG document is open in the APP-owned process at a time.
- A broken document or COM session may be replaced with a new proven-owned process so remaining files continue.
- A per-file geometry, plot, validation, or COM error does not stop later files.
- Blank or case-insensitive `N/A` Scale values use structural fallback across all 13 profiles; other invalid text fails that file.
- Missing Scale label, multiple Scale labels, no unique structural match, and out-of-universe drawings fail closed.
- The target DWG's saved Plot Window is never used as a candidate, fallback, or output window.
- Initial entity collection uses server-side filtered SelectionSet calls; no full `ModelSpace` or full `Blocks` enumeration is allowed.
- Supported frame transforms remain X/Y translation and rigid 0°/90°/180°/270° rotation. Non-uniform scale, mirror, shear, singular transforms, and non-finite geometry fail that file.
- Original DWGs are never saved; source SHA-256 and modification time must remain unchanged.
- Use the bundled runtime: `C:\Users\dknbtech\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.

## File Structure

| File | Responsibility |
|---|---|
| `src/dwg_to_pdf/gstarcad/com_session.py` | Proven-owned process lifetime and sequential one-document-at-a-time boundary |
| `src/dwg_to_pdf/gstarcad/template_detector.py` | Exactly-one Scale label detection and valid/blank/N/A/invalid state |
| `src/dwg_to_pdf/templates/structural_fallback.py` | Select profile universe and choose a unique structural match |
| `src/dwg_to_pdf/batch_session.py` | Reuse a healthy session and replace a broken one without touching user processes |
| `src/dwg_to_pdf/orchestrator.py` | Per-file exception isolation and ordered `JobResult` aggregation |
| `src/dwg_to_pdf/result_presenter.py` | Korean batch summary model and final dialog text |
| `tests/integration/test_com_contract.py` | Real sequential-document same-PID contract and source preservation |
| `tests/unit/test_gstarcad_contracts.py` | Partial-failure, close, reuse, and ownership unit contracts |
| `tests/unit/test_bounded_detector.py` | Scale state and bounded detection contracts |
| `tests/unit/test_structural_fallback.py` | 13-profile candidate-universe and ambiguity contracts |
| `tests/integration/test_orchestrator.py` | Continue-after-error, session replacement, and final error summary |

---

### Task R1: Reusable Owned GstarCAD Batch Session

**Files:**
- Modify: `src/dwg_to_pdf/gstarcad/com_session.py`
- Modify: `tests/unit/test_gstarcad_contracts.py`
- Modify: `tests/integration/test_com_contract.py`

**Interfaces:**
- Consumes: `require_registered_prog_id(prog_id)`, `GstarDocument(raw)`, existing PID and mutex helpers.
- Produces: `GstarSession.open_readonly_copy(path) -> GstarDocument`, `GstarSession.close_document() -> None`, `GstarSession.owned_pid`, and reusable session state after a successful close.

- [ ] **Step 1: Write failing sequential-document tests**

```python
def test_session_reuses_owned_app_after_each_document_is_closed(session_with_fake_app, tmp_path):
    first = make_dwg(tmp_path / "first.dwg")
    second = make_dwg(tmp_path / "second.dwg")
    session = session_with_fake_app
    session.open_readonly_copy(first)
    session.close_document()
    session.open_readonly_copy(second)
    session.close_document()
    assert session.app.Documents.opened == [(str(first.resolve()), True), (str(second.resolve()), True)]
    assert session.app.quit_calls == 0


def test_close_failure_marks_session_unusable_and_never_saves(session_with_failing_close, tmp_path):
    session = session_with_failing_close
    session.open_readonly_copy(make_dwg(tmp_path / "bad-close.dwg"))
    with pytest.raises(AppError) as raised:
        session.close_document()
    assert raised.value.code == "E203"
    assert session.is_usable is False
    assert session_with_failing_close.raw_document.close_arguments == [False]
```

- [ ] **Step 2: Run the focused unit tests and verify RED**

Run:
`C:\Users\dknbtech\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/unit/test_gstarcad_contracts.py -v`

Expected: FAIL because `close_document` and `is_usable` do not exist and the current class documents a single-file contract.

- [ ] **Step 3: Implement the explicit document boundary**

```python
class GstarSession(AbstractContextManager["GstarSession"]):
    def __init__(self, prog_id: str) -> None:
        # existing ownership fields remain
        self._document_close_failed = False

    @property
    def is_usable(self) -> bool:
        return self.app is not None and self._owns_app and not self._document_close_failed

    def close_document(self) -> None:
        raw = self.document
        wrapped = self._wrapped_document
        self.document = None
        self._wrapped_document = None
        if wrapped is not None:
            wrapped.raw = None
        if raw is None:
            return
        try:
            raw.Close(False)
        except Exception as exc:
            self._document_close_failed = True
            raise AppError("E203", "GstarCAD could not close the current document") from exc
        finally:
            gc.collect()

    def open_readonly_copy(self, path: Path) -> GstarDocument:
        if not self.is_usable:
            raise AppError("E201", "GstarCAD batch session is not usable")
        if self.document is not None:
            raise AppError("E201", "close the current document before opening another")
        # retain existing strict path and ReadOnly verification
```

Update `_release()` to call `close_document()`, suppress only its shutdown-time error, then quit only the proven-owned application. Keep idempotent COM and mutex cleanup.

- [ ] **Step 4: Add a real same-PID sequential-open integration test**

```python
@pytest.mark.gstarcad
@pytest.mark.skipif("GSTARCAD_TEST_DWGS" not in os.environ, reason="set GSTARCAD_TEST_DWGS")
def test_one_owned_pid_opens_multiple_drawings_sequentially_without_source_changes():
    paths = tuple(Path(value) for value in os.environ["GSTARCAD_TEST_DWGS"].split(";"))
    before = {path: (_sha256(path), path.stat().st_mtime_ns) for path in paths}
    with GstarSession("GStarCAD.Application.26") as session:
        pid = session.owned_pid
        for path in paths:
            document = session.open_readonly_copy(path)
            assert document.filtered_snapshots(("TEXT", "MTEXT", "INSERT")) is not None
            session.close_document()
            assert session.owned_pid == pid
    assert {path: (_sha256(path), path.stat().st_mtime_ns) for path in paths} == before
```

- [ ] **Step 5: Run focused, full, and real-COM verification**

Run unit/full suite and then set `GSTARCAD_TEST_DWGS` to three provided template/sample DWGs. Expected: all unit tests pass; one real APP-owned PID remains constant across the three opens; all source hashes and mtimes remain exact; any pre-existing user PID remains alive.

- [ ] **Step 6: Commit Task R1**

```powershell
git add src/dwg_to_pdf/gstarcad/com_session.py tests/unit/test_gstarcad_contracts.py tests/integration/test_com_contract.py
git commit -m "fix: reuse one owned GstarCAD batch session"
```

---

### Task R2: Scale Cell State and 13-Profile Structural Fallback

**Files:**
- Modify: `src/dwg_to_pdf/domain.py`
- Modify: `src/dwg_to_pdf/gstarcad/template_detector.py`
- Create: `src/dwg_to_pdf/templates/structural_fallback.py`
- Modify: `src/dwg_to_pdf/templates/profile_schema.py`
- Modify: `src/dwg_to_pdf/templates/profile_store.py`
- Modify: `tests/fixtures/profile_1_to_50.json`
- Modify: `tests/unit/test_bounded_detector.py`
- Modify: `tests/unit/test_profile_store.py`
- Create: `tests/unit/test_structural_fallback.py`

**Interfaces:**
- Consumes: `GstarDocument.filtered_snapshots`, `nested_text_snapshots`, `ProfileStore`, `compute_candidate`, `choose_unique`, and Task 5's `verify_rotation(document, profile, candidate) -> float`.
- Produces: `ScaleCell(anchor, state, token, handle)`, `detect_scale_cell(document, limits, profiles) -> ScaleCell`, `ProfileStore.all() -> tuple[TemplateProfile, ...]`, `profiles_for_scale_cell(cell, store) -> tuple[TemplateProfile, ...]`, and `choose_profile_by_structure(cell, profiles, scorer, minimum_score, minimum_gap) -> MatchDecision`.

- [ ] **Step 1: Write failing Scale-state tests**

```python
@pytest.mark.parametrize((text, state), [("", "blank"), (" N/A ", "na"), ("n/a", "na")])
def test_one_scale_label_preserves_blank_or_na_for_fallback(text, state):
    document = FakeScaleDocument(label="Scale", value=text)
    cell = detect_scale_cell(document, DetectionLimits(64, 5000), approved_profiles())
    assert cell.state == state
    assert cell.token is None


def test_multiple_scale_labels_fail_closed():
    with pytest.raises(AppError) as raised:
        detect_scale_cell(FakeScaleDocument(labels=2), DetectionLimits(64, 5000), approved_profiles())
    assert raised.value.code == "E303"


def test_invalid_non_na_text_fails_instead_of_using_fallback():
    with pytest.raises(AppError) as raised:
        detect_scale_cell(FakeScaleDocument(label="Scale", value="UNKNOWN"), DetectionLimits(64, 5000), approved_profiles())
    assert raised.value.code == "E305"
```

- [ ] **Step 2: Run detector tests and verify RED**

Run:
`C:\Users\dknbtech\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/unit/test_bounded_detector.py -v`

Expected: FAIL because the detector currently drops blank/N/A values and permits zero or multiple labels by returning an empty/list result.

- [ ] **Step 3: Add learned Scale-value cell geometry to approved profiles**

```python
@dataclass(frozen=True)
class TemplateProfile:
    # existing fields remain
    scale_value_offset: Point
    scale_value_tolerance: float
```

`scale_value_offset` is the reference value object's insertion point minus the reference `Scale` label anchor in template-local coordinates. `scale_value_tolerance` is a finite positive registration tolerance. Add both required fields to `profile_schema.py`, reject Boolean/non-finite/non-positive tolerance values in `profile_store.py`, and update the existing fixture. Task 5 registration must calculate these values from the supplied reference DWG; it must not ask the operator to enter coordinates numerically.

Expose the immutable closed profile set:

```python
class ProfileStore:
    def all(self) -> tuple[TemplateProfile, ...]:
        return tuple(sorted(self._profiles.values(), key=lambda profile: profile_key(profile)))
```

- [ ] **Step 4: Add the stateful domain model and detector**

```python
ScaleCellState = Literal["valid", "blank", "na"]


@dataclass(frozen=True)
class ScaleCell:
    anchor: Point
    state: ScaleCellState
    token: str | None
    handle: str
```

```python
def detect_scale_cell(document: Any, limits: DetectionLimits, profiles: tuple[TemplateProfile, ...]) -> ScaleCell:
    snapshots = _bounded_text_and_insert_snapshots(document, limits)
    labels = [item for item in snapshots if str(item.get("text", "")).strip().casefold() == "scale"]
    if len(labels) != 1:
        raise AppError("E303", f"expected exactly one Scale label, found {len(labels)}")
    label = labels[0]
    lx, ly = _validated_point(label)
    expected = []
    for profile in profiles:
        for rotation in (0, 90, 180, 270):
            offset = rotate(profile.scale_value_offset, rotation)
            expected.append((lx + offset.x, ly + offset.y, profile.scale_value_tolerance))
    value_matches = []
    for item in snapshots:
        if item is label or not str(item.get("text", "")).strip():
            continue
        x, y = _validated_point(item)
        if any((x - ex) ** 2 + (y - ey) ** 2 <= tolerance ** 2 for ex, ey, tolerance in expected):
            value_matches.append(item)
    by_handle = {str(item.get("handle", "")): item for item in value_matches}
    if len(by_handle) > 1:
        raise AppError("E304", "multiple Scale value-cell objects matched")
    value = next(iter(by_handle.values()), None)
    raw = str(value.get("text", "")).strip() if value is not None else ""
    if not raw:
        return ScaleCell(Point(*_validated_point(label)), "blank", None, str(label.get("handle", "")))
    if raw.casefold() == "n/a":
        return ScaleCell(Point(*_validated_point(label)), "na", None, str(label.get("handle", "")))
    try:
        parse_internal_scale(raw)
    except AppError as exc:
        raise AppError("E305", f"unsupported Scale value: {raw}") from exc
    return ScaleCell(Point(*_validated_point(label)), "valid", raw, str(label.get("handle", "")))
```

Blank means none of the four rotated, learned value-cell positions for any approved profile contains text. It does not mean no arbitrary nearby ratio happened to be found. Attached attributes at the learned position participate using their transformed world insertion point.

- [ ] **Step 5: Write failing closed-universe fallback tests**

```python
def test_valid_scale_returns_exactly_one_approved_profile(store_13, valid_cell):
    profiles = profiles_for_scale_cell(valid_cell, store_13)
    assert [profile_key(profile) for profile in profiles] == ["1:50"]


@pytest.mark.parametrize("state", ["blank", "na"])
def test_fallback_evaluates_exactly_13_approved_profiles(store_13, state):
    cell = ScaleCell(Point(100, 50), state, None, "A1")
    assert len(profiles_for_scale_cell(cell, store_13)) == 13


def test_fallback_rejects_equal_best_structures(store_13, na_cell):
    with pytest.raises(AppError) as raised:
        choose_profile_by_structure(na_cell, store_13.all(), equal_scorer, 0.95, 0.02)
    assert raised.value.code == "E304"


def test_fallback_rejects_out_of_universe_structure(store_13, na_cell):
    with pytest.raises(AppError) as raised:
        choose_profile_by_structure(na_cell, store_13.all(), low_scorer, 0.95, 0.02)
    assert raised.value.code == "E310"
```

- [ ] **Step 6: Implement closed-universe selection**

```python
APPROVED_SCALE_KEYS = (
    "1:1", "1:2", "1:5", "1:10", "1:20", "1:50", "1:100",
    "2:1", "5:1", "10:1", "20:1", "50:1", "100:1",
)


def _decimal_key(value: Decimal) -> str:
    raw = format(value, "f")
    return raw.rstrip("0").rstrip(".") if "." in raw else raw


def profile_key(profile: TemplateProfile) -> str:
    return f"{_decimal_key(profile.scale.numerator)}:{_decimal_key(profile.scale.denominator)}"


def profiles_for_scale_cell(cell: ScaleCell, store: ProfileStore) -> tuple[TemplateProfile, ...]:
    if cell.state == "valid":
        assert cell.token is not None
        return (store.find(parse_internal_scale(cell.token)),)
    profiles = store.all()
    if len(profiles) != 13 or tuple(profile_key(item) for item in profiles) != APPROVED_SCALE_KEYS:
        raise AppError("E300", "exactly 13 approved template profiles are required")
    return profiles


def choose_profile_by_structure(cell, profiles, scorer, minimum_score, minimum_gap):
    scored = []
    for profile in profiles:
        for rotation in (0, 90, 180, 270):
            candidate = compute_candidate(profile, ScaleCandidate(cell.anchor, profile_key(profile), cell.handle), rotation)
            scored.append((candidate, scorer(profile, candidate)))
    try:
        return choose_unique(scored, minimum_score, minimum_gap)
    except AppError as exc:
        if exc.code == "E303":
            raise AppError("E310", "no approved template structure matched") from exc
        raise
```

- [ ] **Step 7: Run focused and full tests**

Expected: valid Scale restricts to one profile; blank/N/A evaluates all and only 13; no candidate returns E310; ties return E304; the full suite remains green.

- [ ] **Step 8: Commit Task R2**

```powershell
git add src/dwg_to_pdf/domain.py src/dwg_to_pdf/gstarcad/template_detector.py src/dwg_to_pdf/templates/structural_fallback.py src/dwg_to_pdf/templates/profile_schema.py src/dwg_to_pdf/templates/profile_store.py tests/fixtures/profile_1_to_50.json tests/unit/test_bounded_detector.py tests/unit/test_profile_store.py tests/unit/test_structural_fallback.py
git commit -m "feat: match blank Scale drawings to approved structures"
```

---

### Task R3: File-Isolated Batch Recovery and Final Error Report

**Files:**
- Create: `src/dwg_to_pdf/batch_session.py`
- Modify or create: `src/dwg_to_pdf/orchestrator.py`
- Create: `src/dwg_to_pdf/result_presenter.py`
- Modify: `src/dwg_to_pdf/domain.py`
- Create or modify: `tests/integration/test_orchestrator.py`
- Create: `tests/unit/test_result_presenter.py`

**Interfaces:**
- Consumes: `GstarSession`, `ConversionService.convert_in_session(session, source, output_dir, conflict_policy)`, `AppError`, and `JobResult`.
- Produces: `BatchSession.run_one(callback)`, `run_jobs(service, sources, output_dir, conflict_policy) -> tuple[JobResult, ...]`, and `build_result_report(results) -> ResultReport`.

- [ ] **Step 1: Extend `JobResult` with a stable user message**

```python
@dataclass(frozen=True)
class JobResult:
    source: Path
    status: Literal["success", "failed", "held", "skipped"]
    outputs: tuple[Path, ...]
    code: str | None = None
    reason: str | None = None
    log_detail: str | None = None
```

- [ ] **Step 2: Write failing continuation and session-replacement tests**

```python
def test_bad_middle_file_does_not_stop_later_file(tmp_path, fake_session_factory):
    service = FakeService(fail_names={"bad.dwg"})
    results = run_jobs(service, paths(tmp_path, "a.dwg", "bad.dwg", "c.dwg"), tmp_path, "skip", fake_session_factory)
    assert [item.status for item in results] == ["success", "failed", "success"]
    assert results[1].reason == "비균일 블록 축척이 검출되었습니다."


def test_broken_close_replaces_owned_session_and_continues(tmp_path, fake_session_factory):
    factory = fake_session_factory(close_failure_on="bad.dwg")
    results = run_jobs(FakeService(), paths(tmp_path, "bad.dwg", "good.dwg"), tmp_path, "skip", factory)
    assert [item.status for item in results] == ["failed", "success"]
    assert factory.created_owned_pids == [2001, 2002]
    assert factory.killed_pids == [2001]
    assert 10068 not in factory.killed_pids
```

- [ ] **Step 3: Implement the replaceable session owner**

```python
class BatchSession:
    def __init__(self, factory):
        self.factory = factory
        self.session = None

    def __enter__(self):
        self.session = self.factory()
        self.session.__enter__()
        return self

    def run_one(self, callback):
        if self.session is None:
            raise AppError("E311", "GstarCAD batch session is unavailable")
        primary_error = None
        try:
            return callback(self.session)
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            try:
                self.session.close_document()
            except AppError as close_error:
                try:
                    self._replace()
                except AppError as replacement_error:
                    self.last_cleanup_error = replacement_error
                    if primary_error is None:
                        raise replacement_error
                if primary_error is None:
                    raise close_error

    def _replace(self):
        old, self.session = self.session, None
        if old is not None:
            old.__exit__(None, None, None)
        replacement = self.factory()
        replacement.__enter__()
        self.session = replacement
```

The production implementation must preserve the original file exception if close also fails, append the close failure to technical detail, and replace the session before the next file. If replacement fails, remaining files receive `E311` without attempting COM work. `last_cleanup_error` is initialized to `None` and consumed by the orchestrator when it builds technical detail.

- [ ] **Step 4: Implement ordered file isolation**

```python
def run_jobs(service, sources, output_dir, conflict_policy, session_factory):
    results = []
    with BatchSession(session_factory) as batch:
        for source in sources:
            try:
                require_stable(source)
                outcome = batch.run_one(lambda session: service.convert_in_session(session, source, output_dir, conflict_policy))
                results.append(JobResult(source, "success", tuple(frame.output for frame in outcome.frames)))
            except AppError as exc:
                results.append(JobResult(source, "failed", (), exc.code, user_reason(exc), technical_detail(exc)))
            except Exception as exc:
                results.append(JobResult(source, "failed", (), "E900", "예상하지 못한 변환 오류가 발생했습니다.", repr(exc)))
    return tuple(results)
```

- [ ] **Step 5: Write and implement final report tests**

```python
def test_report_lists_file_and_korean_reason_once():
    results = (
        JobResult(Path("good.dwg"), "success", (Path("good.pdf"),)),
        JobResult(Path("XXX-XXX.DWG"), "failed", (), "E303", "비균일 블록 축척이 검출되었습니다."),
    )
    report = build_result_report(results)
    assert report.total == 2 and report.succeeded == 1 and report.failed == 1
    assert report.failure_lines == ("XXX-XXX.DWG — 비균일 블록 축척이 검출되었습니다.",)
```

`result_presenter.py` must construct data and text only. The final GUI adapter may use a Windows message box or packaged UI layer, but it must display one summary after the batch, not one modal dialog per failed file.

- [ ] **Step 6: Run focused and full tests**

Expected: ordered results include all inputs; a bad middle file does not stop later files; a broken owned session is replaced; no user PID appears in termination calls; the final report lists every failure once.

- [ ] **Step 7: Commit Task R3**

```powershell
git add src/dwg_to_pdf/batch_session.py src/dwg_to_pdf/orchestrator.py src/dwg_to_pdf/result_presenter.py src/dwg_to_pdf/domain.py tests/integration/test_orchestrator.py tests/unit/test_result_presenter.py
git commit -m "feat: isolate batch failures and report results"
```

---

### Task R4: Real Batch Regression and Documentation Reconciliation

**Files:**
- Modify: `tests/integration/test_actual_drawings.py`
- Modify: `tests/integration/test_owned_process_cleanup.py`
- Create: `tests/fixtures/scale_blank_or_na_cases.json`
- Modify: `docs/superpowers/specs/2026-07-16-dwg-to-pdf-design.md`
- Modify: `docs/superpowers/plans/2026-07-16-dwg-to-pdf-implementation.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: Tasks R1–R3 and original Tasks 5–8.
- Produces: real-machine evidence that the revised batch contract, closed template universe, PDF output, source preservation, and user-process preservation work together.

- [ ] **Step 1: Prepare non-destructive blank/N/A fixtures from temporary working copies**

Record fixture source SHA, expected profile ID, expected frame rotation, and expected Plot Window. Never edit the supplied 13 reference DWGs in place.

- [ ] **Step 2: Run one owned-process real batch**

Use at least three valid drawings, one intentional non-uniform/unsupported drawing, one blank/N/A Scale working copy, and one out-of-universe working copy. Expected ordered outcomes: successes continue on both sides of failures; blank/N/A uniquely matches the expected profile; unsupported/out-of-universe files fail without PDF.

- [ ] **Step 3: Verify process and source invariants**

Capture user PID set before/after, APP-owned PID history, every source SHA-256, every source mtime, and output PDF structural validation. Expected: user PID set unchanged; only proven-owned PIDs stopped; all source values exact.

- [ ] **Step 4: Reconcile superseded documentation**

Replace statements that require one process per input file or reject blank/N/A without fallback. Add a direct link to `docs/superpowers/specs/2026-07-16-batch-session-scale-fallback-design.md` and preserve all unrelated original requirements.

- [ ] **Step 5: Run final verification and commit**

Run the full unit/integration suite, opt-in real GstarCAD batch test, `git diff --check`, forbidden-pattern search, and source hash verification. Commit only after all required checks pass.

```powershell
git add tests docs README.md
git commit -m "test: verify reusable GstarCAD batch conversion"
```
