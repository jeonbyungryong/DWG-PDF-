# AutoCAD Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 GstarCAD 변환을 보존하면서 Windows 일반 AutoCAD를 명시적으로 선택하는 실험적 어댑터와 검증 경로를 만든다.

**Architecture:** 설정/탐지 → 공급자 팩토리 → 소유권이 증명된 단일 세션 → 문서/플롯 어댑터 순서로 연결한다. 템플릿 판정·원본 보호·PDF 검증·배치 실패 격리는 공유하고, COM 생성/네이티브 호출/출력 방향 처리는 제품별로 분리한다. 저장소 전체 이동이나 별도 APP 복제는 하지 않는다.

**Tech Stack:** Windows x64, Python(기존 패키지 범위 `>=3.11,<3.14`, 개발/빌드 기준3.12 x64), pywin32, pytest, 기존 PDF 라이브러리와 PyInstaller. 신규 외부 의존성 도입 없음.

**Spec:** [승인된 REV01](../specs/2026-10-02-autocad-support-design.md). 제품 기준 `d7df6c6d34c546c5f2fb8622a5ab3039bdb2355d`, 승인 명세 게시본 `32e3400173efd537f8eaa191eb9ad9d6a02c9046`.

## Global Constraints

- Windows x64 일반 AutoCAD를 우선 목표로 한다. LT/Mac/Web/수직 제품군 일괄 지원은 제외한다.
- 기존 GstarCAD 기본 동작과 설정 파일 하위 호환을 유지한다. 다른 CAD로 조용히 전환하지 않는다.
- 기존 13종 템플릿, 회전0/90/180/270도, Scale 공란/N/A 구조 판정을 유지한다. 새 양식/축척/다중 도곽은 제외한다.
- APP 소유 CAD 한 개로 순차 처리한다. 사용자 CAD 사용/종료 금지, 원본 DWG 저장 금지, 실패 파일 격리.
- A4가로297×210mm, `DWG To PDF.pc3`, `monochrome.ctb`, 선가중치 의도를 유지한다. 기존 용지/PDF 치수 공차0.20mm를 넓히지 않는다.
- AutoCAD 기본 비활성, 명시적 opt-in과 경고 필수. 실제 검증 전에는 지원 버전이나 생산 사용 승인을 주장하지 않는다.
- LISP 보안 완화, CAD 설치/활성화, 신규 COM watchdog, 고객 도면 자동 업로드는 하지 않는다.
- 제품 구현은 루트 `AGENTS.md`에 따라 DWG-PDF 전용 저장소에서 직접 만든 `codex/*` 격리 작업트리에서 한다. 2026-10-02 사용자 지시로 Antigravity 의존을 제거했다.
- 문서 게시 승인과 구현/배포/main 병합 승인은 별개다. 본 계획은 **G1 승인 / Native 실행**이며 완료한 구현만 기록한다.

## Review Focus

1. COM 생성이 기존 사용자 프로세스를 돌려주는 경우: `Visible` 쓰기조차 하기 전에 거부하며 Quit/문서열기/강제종료하지 않는다 → T3.
2. 레지스트리 별칭·동일 ProgID의 충돌·동시에 설치된 여러 버전: 잘못된 후보 선택/임의 최신 선택/실행파일 명령 주입을 막는다 → T1.
3. 구 설정과 새 설정 또는 GUI/CLI 선택이 충돌하는 경우: 명시 오류 또는 명시적 사용자 override만 허용하고 실제 선택을 보여준다 → T1,T6.
4. 앞 도면의 native 응답/캐시가 다음 도면에 남거나 한글 경로에서 응답 인코딩이 다른 경우: 문서 식별 실패를 fallback으로 숨기지 않는다 → T4.
5. AutoCAD가 이미 올바른 가로 PDF를 출력한 경우: GstarCAD 전용 보정으로 이중 회전하지 않으며 잘못된 출력은 게시하지 않는다 → T5.

---

## 상태·근거·진행 방식

- 2026-10-02 사용자의 `go` 및 후속 계획 작성/게시 요청을 G0 승인으로 기록한다. 승인된 범위는 REV01 기반 상세 계획 작성이다.
- 이 문서의 신규 파일/인터페이스/오류코드는 **구현 제안**이며 현재 제품에 존재하거나 동작한다고 주장하지 않는다.
- 현재 코드에서 `AppConfig.prog_id`, CLI의 `GstarSession` 팩토리, `ConversionService`의 `GstarDocument` 타입 검사와 `.raw` 플롯 접근을 확인했다. `GstarSession`은 현재 소유권 증명 전에 `Visible=False`를 쓰므로 T3에 보호 순서 테스트를 포함한다.
- AutoCAD 실기: NOT_RUN / 환경 미확보. GstarCAD 과거 시험은 이번 확장 브랜치의 회귀 증거가 아니다.
- 권장 실행은 Native(동일 구현자가 T1~T7 순차 수행 후 독립 전체 리뷰)다. 공통 세션/문서/CLI 파일의 의존성이 높다. 작업별 외부 리뷰 방식은 G1 때 선택한다.
- T1~T7은 AC-02~05 구현 단계, T8/T9는 AC-06/07 검증 단계다. T8/T9는 환경 확보까지 차단 상태로 남긴다.

## 파일과 책임

모든 경로는 저장소 루트 기준이다. 신규 패키지에는 빈 `__init__.py`를 포함한다. 기존 테스트를 삭제하거나 수용 기준을 낮추지 않는다.

| 작업 | 생성/수정 파일 | 책임 |
|---|---|---|
| T1 / AC-02 | 생성 `src/dwg_to_pdf/cad/selection.py`, `cad/discovery.py`; 수정 `configuration.py`, `config.example.toml` | 설정 이행, 읽기 전용 후보 탐지/선택 |
| T2 / AC-03 | 생성 `cad/contracts.py`; 수정 `gstarcad/document.py`, `conversion_service.py` | 공급자 중립 경계, 기존 Gstar 플롯 위임 |
| T3 / AC-03 | 생성 `cad/process_ownership.py`, `cad/com_session.py`, `autocad/com_session.py`; 수정 `gstarcad/com_session.py`, `batch_session.py` | COM 수명·소유권·단일 배치 |
| T4 / AC-04 | 생성 `cad/com_document.py`, `cad/bulk_snapshot.py`, `cad/bulk_extract.lsp`, `autocad/document.py`, `autocad/native.py`; 수정 `gstarcad/document.py`, `gstarcad/bulk_snapshot.py`, `gstarcad/template_detector.py`, `packaging/dwg_to_pdf.spec`, `packaging/preflight.py`, `packaging/verify_bundle.ps1` | 기존 스냅샷/한도 재사용, 제품별 native 호출/자산 경로 |
| T5 / AC-04 | 생성 `autocad/plotting.py`; 수정 `autocad/document.py` | AutoCAD 용지·플롯·방향 처리 |
| T6 / AC-02,03,05 | 생성 `cad/factory.py`, `cad/diagnostics.py`; 수정 `cli.py`, `desktop_launcher.py`, `orchestrator.py` | 선택 UI/CLI, 팩토리, 오류/환경 진단 |
| T7 / AC-05 | 수정 `pyproject.toml`, `packaging/dwg_to_pdf.spec`, `packaging/preflight.py`, `packaging/verify_bundle.ps1`, `tools/smoke_frozen_bundle.py`, `docs/DEVELOPMENT.md`, `docs/autocad/COLLABORATION.md`; 생성 `tests/conftest.py`, `docs/autocad/VALIDATION.md` | 오프라인/기존 회귀, 번들, 시험 안내 |
| T8 / AC-06 | 생성 `tests/integration/test_autocad_live.py`; 수정 `tools/benchmark_conversion.py`; 검증 기록은 `docs/autocad/VALIDATION.md` | 실제 AutoCAD PDF/보호/성능 증거 |
| T9 / AC-07 | 수정 `docs/autocad/VALIDATION.md`, `README.md`; 승인 후 생성 `docs/releases/<실제 검증일>-autocad-validation.md` | 타PC/frozen/사용자 수용, 지원 상태 |

아래 `src/` 축약 경로는 `src/dwg_to_pdf/`를 뜻한다. 테스트 파일은 각 작업에 명시한다. 한 작업의 공유 파일 편집을 종료하고 인계 SHA를 기록한 후 다음 작업이 시작한다.

## 공통 설계 결정

### 설정·오류

- `AppConfig`에 기본값 `cad_provider="gstarcad"`, `allow_experimental_autocad=False`를 추가하고 기존 생성자 인자 순서를 보존한다. `prog_id`는 `str | None`으로 확장한다.
- 구 `[gstarcad]`만 있으면 기존 ProgID를 명시 선택으로 유지한다. 새 `[cad]`는 `provider`, 선택적 `prog_id`, `allow_experimental_autocad`를 읽는다.
- 두 절을 함께 주면 공급자가 GstarCAD이고 ProgID가 같거나 새 값이 생략된 경우만 허용한다. AutoCAD 설정에 구 `[gstarcad]` 절이 남으면 `E001`로 제거/이행 안내한다. 조용한 무시 금지.
- CLI의 명시적 `--cad`는 제품 선택 override다. 제품을 바꾸면 이전 제품의 ProgID를 계승하지 않는다. `--cad-prog-id`는 후보와 일치해야 한다. 설정 자체가 충돌하면 CLI로 숨기지 않고 먼저 `E001` 처리한다.
- 기존 오류코드를 보존한다. 신규: `E220` 후보없음, `E221` 후보다수/선택필요, `E222` AutoCAD opt-in 미허용, `E223` 제외/식별불가 제품. 등록 불일치 `E202`, 소유권 `E201`, 문서 `E203`, 세션불능 `E311`, 추출 `E303`, 출력환경 `E210~212`, 플롯 `E410`, PDF `E420` 유지. 오류는 제품·단계·조치와 함께 표시한다.
- `config.toml`의 실제 GstarCAD 기본값/템플릿/보정값은 이번 확장만을 위해 바꾸지 않는다. 예제 AutoCAD 설정에는 실제 PC의 ProgID를 넣지 않는다.

### 공통 인터페이스

`cad/contracts.py`에 Protocol을 두고 `Any`는 원시 COM 구현 내부에서만 사용한다. 아래 메서드는 기존 판정 호출과 일치시키며 detector의 알고리즘/한도는 바꾸지 않는다.

```python
Snapshot = dict[str, object]
# CadDocument Protocol: 아래 외에도 기존 detector가 사용하는 분류 메서드를 보존한다.
configure_extraction(self, enabled: bool) -> None
for_scale_detection(self) -> CadDocument
filtered_snapshots(self, types: tuple[str, ...], bounds: Rect | None = None) -> list[Snapshot]
nested_text_snapshots(self, reference: Snapshot, max_blocks: int | None = None,
                      max_entities: int | None = None, *, budget: TraversalBudget | None = None) -> list[Snapshot]
filtered_geometry_snapshots(self, bounds: Rect, max_blocks: int = 64,
                            max_entities: int = 5000) -> list[Snapshot]
is_known_noncontributing_text_insert(self, reference: Snapshot) -> bool
is_noncontributing_text_insert(self, reference: Snapshot, *, budget: TraversalBudget) -> bool
is_noncontributing_unsupported_insert(self, reference: Snapshot, *, budget: TraversalBudget) -> bool
plot_pdf(self, output: Path, window: Rect, rotation: Rotation,
         preferred_media_names: tuple[str, ...]) -> None
# CadSession Protocol: ContextManager[CadSession], 읽기 전용 property is_usable: bool
# 읽기 전용 property owned_pid: int | None, reported_version: str | None
working_document(self, workspace: SourceWorkspace) -> AbstractContextManager[CadDocument]
```

`TraversalBudget`는 기존 클래스를 T4에서 공통 모듈로 기계적으로 이동하고 구 import 경로에서 다시 export한다. Protocol의 타입 전용 import에는 TYPE_CHECKING을 사용해 순환 import를 피한다. `Rect`, `Rotation`은 기존 `domain.py`, `SourceWorkspace`는 기존 `temp_workspace.py`를 사용한다. 세션은 문서를 소유하고 서비스는 스냅샷/플롯 계약만 소비한다. `plot_pdf`는 임시 PDF만 만들며 최종 검증/게시 책임은 기존 `publish_pdf`에 남긴다.

## T1 — 설정과 후보 탐지 (AC-02)

**Files:** 위 T1 파일 + `tests/unit/test_cad_selection.py`, `tests/unit/test_cad_discovery.py`, 기존 `tests/unit/test_configuration.py`.

**Interfaces:** 생성 `ProviderId = Literal["gstarcad", "autocad"]`; frozen `CadSelection(provider: ProviderId, prog_id: str | None, allow_experimental_autocad: bool)`; frozen `CadCandidate(provider: ProviderId, prog_id: str, clsid: str, executable: Path, product_name: str, reported_version: str | None)`. 제공 `discover_candidates(provider: ProviderId) -> tuple[CadCandidate, ...]`, `select_candidate(selection: CadSelection, candidates: tuple[CadCandidate, ...]) -> CadCandidate`. `load_config(path: Path) -> AppConfig` 유지.

- [ ] **실패 테스트 작성:** 후보는 테스트가 만든 레지스트리/파일 메타데이터 mock만 사용한다. `candidate_a/b`는 서로 다른 CLSID, `alias_a`는 a의 같은 CLSID/실행파일로 정의한다.
  ```python
  assert load_config(legacy_path).cad_provider == "gstarcad"
  assert load_config(legacy_path).prog_id == "GStarCAD.Application.26"
  assert select_candidate(explicit_a, (candidate_a, candidate_b)) == candidate_a
  with pytest.raises(AppError) as error:
      select_candidate(no_selection, (candidate_a, candidate_b))
  assert error.value.code == "E221"
  ```
  별도 테스트명: `test_zero_candidates_e220`, `test_one_candidate_selected`, `test_alias_deduplicated_by_clsid_and_executable`, `test_conflicting_registration_e202`, `test_lt_or_unknown_identity_excluded`, `test_old_new_config_conflict_e001`, `test_autocad_requires_opt_in_e222`, `test_discovery_never_dispatches_or_writes_registry`.
- [ ] **실패 확인:** `python -m pytest tests/unit/test_cad_selection.py tests/unit/test_cad_discovery.py tests/unit/test_configuration.py -q` → 신규 모듈/필드 부재로 FAIL 확인.
- [ ] **최소 구현:** 64bit HKLM/HKCU 클래스 등록과 제품 메타데이터를 읽어 ProgID→CLSID→LocalServer32를 교차 확인한다. 별칭 중복만 병합하고 같은 ProgID가 다른 실행파일을 가리키면 거부한다. 경로 문자열을 shell 실행하지 않는다. 등록/파일 존재/일반 제품 식별이 맞는 후보만 내보내며 LT/수직 제품/식별불가는 `E223`로 설명한다. 버전 번호를 연도로 추정하거나 라이선스 성공으로 표시하지 않는다. 실제 PC에 없는 레지스트리 모양은 mock 근거일 뿐이다.
- [ ] **통과 확인:** 같은 명령 전체 PASS. BOOL에 문자열/정수, 빈 ProgID, 다른 공급자의 ProgID 입력도 거부한다. 미설치 PC에서 `load_config` 자체는 CAD를 기동하지 않는다.
- [ ] **커밋:** T1 명시 파일만 stage, `git commit -m "feat: add explicit CAD selection and read-only discovery"`. 이슈에 AC-02 부분 진행과 SHA 기록; GUI는 T6까지 미완료.

## T2 — 공통 경계와 GstarCAD 위임 (AC-03)

**Files:** 위 T2 파일 + `tests/unit/test_cad_contracts.py`, 기존 `tests/integration/test_conversion_service.py`.

**Interfaces:** 위 공통 Protocol 제공. `ConversionService.convert_in_session(session: CadSession, source: Path, output_dir: Path, conflict_policy: ConflictPolicy) -> ConversionOutcome`로 타입만 중립화. `GstarDocument.configure_extraction`과 `plot_pdf` 구현.

- [ ] **실패 테스트 작성:** `.raw` 접근 시 AssertionError를 내는 fake document가 공통 메서드만 제공하게 한다.
  ```python
  outcome = service.convert_in_session(fake_session, source, output_dir, "copy")
  assert fake_document.extraction_enabled is True
  assert fake_document.plot_calls == [(temporary_pdf, expected_window, expected_rotation, preferred_names)]
  assert outcome.frames[0].scale == expected_scale
  assert source.read_bytes() == original_bytes
  ```
  기존 테스트 fixture를 재사용하되 임시 경로는 호출 spy에서 캡처한다. `test_provider_independent_service_never_reads_raw`, `test_failed_plot_never_publishes_pdf`를 추가한다.
- [ ] **실패 확인:** `python -m pytest tests/unit/test_cad_contracts.py tests/integration/test_conversion_service.py -q` → 기존 타입검사/직접 raw 접근 때문에 FAIL.
- [ ] **최소 구현:** 서비스의 `isinstance(GstarDocument)`와 제품별 플롯 import를 없앤다. GstarDocument 안에서 기존 `require_plot_environment`→`apply_plot_settings`→`plot_to_file`→`normalize_portrait_plot` 순서를 그대로 호출한다. 서비스의 Scale/구조 판정·임시복사·충돌·원자적 게시 순서는 유지한다.
- [ ] **통과 확인:** 같은 명령 PASS + `python -m pytest -m "not gstarcad" -q`. native cache/기존 Scale fast path 시험을 약화하지 않는다.
- [ ] **커밋:** T2 명시 파일만 stage, `git commit -m "refactor: isolate CAD document and plot contracts"`.

## T3 — 소유권 증명과 세션 수명 (AC-03)

**Files:** 위 T3 파일 + `tests/unit/test_cad_process_ownership.py`, `tests/unit/test_autocad_session.py`, 기존 `tests/integration/test_owned_process_cleanup.py`.

**Interfaces:** T1 `CadCandidate`, T2 `CadSession` 소비. `OwnedProcess`는 PID/생성시각/정규화 실행파일/정확한 프로세스 핸들을 가진 context manager다. `capture_owned_process(candidate: CadCandidate, hwnd: int, before: frozenset[int], after: frozenset[int]) -> OwnedProcess`; `OwnedProcess.close() -> None`; `OwnedProcess.terminate_if_running() -> None`. `ComSession(candidate: CadCandidate, document_factory: Callable[[Any], CadDocument])`에 공통 수명 구현. `AutoCADSession(candidate: CadCandidate)` 제공, 기존 `GstarSession(prog_id: str)` 생성자 유지.

- [ ] **실패 테스트 작성:** Win32/COM fake 호출 순서와 핸들 정체성을 기록한다.
  ```python
  with pytest.raises(AppError) as error:
      reused_user_session.__enter__()
  assert error.value.code == "E201"
  assert fake_app.writes == []  # Visible 포함
  assert fake_app.open_count == fake_app.quit_count == 0
  assert fake_process.terminated_handles == []
  ```
  `test_pid_reuse_never_terminates_replacement`, `test_extra_created_process_is_ambiguous`, `test_executable_mismatch_rejected`, `test_handle_capture_failure_never_sets_owns_app`, `test_second_file_reuses_session`, `test_partial_initialization_releases_only_owned_resources`, `test_document_failure_continues_batch`, `test_broken_session_replacement_failure_e311` 추가.
- [ ] **실패 확인:** `python -m pytest tests/unit/test_cad_process_ownership.py tests/unit/test_autocad_session.py tests/integration/test_owned_process_cleanup.py -q` → 신규 계약/보호 순서 FAIL.
- [ ] **최소 구현:** COM 초기화→앱 공통 단일 실행 mutex→전체 PID 스냅샷→DispatchEx→HWND PID와 제품 프로세스 집합 확인→핸들 확보/실행파일/생성시각 재확인→소유 플래그→Visible 쓰기 순서. 전체 PID snapshot으로 기존 PID를 배제하고 제품 실행파일별 delta가 정확히 해당 PID 하나인지 확인한다. TOCTOU 실패/모호성에서는 COM 변경·Quit 금지. 종료는 소유 확인된 COM과 원래 핸들만 사용한다. GetActiveObject와 이름 기준 kill 금지. 기존 Gstar mutex도 전환 기간 함께 확보해 구 APP와 동시 실행을 막는다.
- [ ] **문서 수명 구현:** `ComSession.working_document(workspace)`는 활성 SourceWorkspace의 임시 DWG만 열고 파일 정체성/쓰기 가능 여부를 확인한다. 예외에서도 `Close(False)`하며 실패 시 세션 불능 처리. 한 번에 열린 작업 문서는1개, 정상 배치 세션1개. BatchSession 기존 교체/실패 전파 의미 보존; 제품 중립 오류로 바꾸되 오류코드는 유지한다. 소유권 확인 후 읽은 실제 COM 버전을 `reported_version`으로 제공하고 실패/미확인은 None으로 남긴다. AutoCAD 문서 factory는 T4/T5 완성 전 mock으로만 시험하며 CLI 노출은 T6까지 하지 않는다.
- [ ] **통과 확인:** 위 명령 PASS, 종료 실패가 원래 파일 오류를 덮어쓰지 않는 기존 배치 시험 PASS. 강제 중단 없는 동기 COM 무응답 한계는 유지/문서화한다.
- [ ] **커밋:** T3 명시 파일만 stage, `git commit -m "feat: enforce owned CAD session lifecycle"`.

## T4 — 공통 스냅샷과 제품별 native 호출 (AC-04)

**Files:** 위 T4 파일 + `tests/unit/test_autocad_document.py`, `tests/unit/test_autocad_native.py`, 기존 `tests/unit/test_bulk_snapshot.py`, `tests/unit/test_bounded_detector.py`, `tests/unit/test_packaging_contract.py`. 기존 `gstarcad/bulk_extract.lsp`는 공유 자산으로 이동 후 중복본을 남기지 않는다. 같은 커밋에서 패키징/검사기의 자산 경로도 바꿔 중간 커밋의 번들 계약을 깨뜨리지 않는다.

**Interfaces:** `cad/com_document.py`에 기존 GstarDocument의 순수 스냅샷/변환/캐시 로직을 `ComDocument`로 옮긴다. 기존 GstarDocument와 AutoCADDocument는 제품별 `plot_pdf`와 `_extract_snapshot(self, types: tuple[str, ...], bounds: Rect | None) -> Any`만 연결한다. 공통 `parse_snapshot(text: str, token: str, document: str) -> Any`, 제품별 `extract_snapshot(raw: Any, types: tuple[str, ...] = ("TEXT", "MTEXT", "INSERT"), bounds: Rect | None = None, timeout: float = 30.0) -> Any`를 제공한다. 구 import 경로는 호환 wrapper/re-export를 유지한다.

- [ ] **실패 테스트 작성:** mock의 식별된 완전 응답만 COM fallback을 허용한다.
  ```python
  assert native_off_document.filtered_snapshots(("TEXT",)) == expected_text
  assert transport.send_count == 0
  with pytest.raises(AppError) as error:
      parse_snapshot(stale_response, current_nonce, current_document)
  assert error.value.code == "E303"
  assert fallback_spy.call_count == 0
  ```
  `test_cache_does_not_cross_documents`, `test_korean_space_quote_path_roundtrip`, `test_nonce_document_complete_and_size_limits`, `test_timeout_does_not_retry`, `test_identified_complete_unavailable_falls_back_once`, `test_secureload_and_trustedpaths_unchanged`, `test_com_and_native_snapshot_decisions_equal` 추가. 한글 UTF-8/Windows 코드페이지 표본은 합성 자료만 사용한다.
- [ ] **실패 확인:** `python -m pytest tests/unit/test_autocad_document.py tests/unit/test_autocad_native.py -q` → 신규 클래스/제품 호출 부재 FAIL.
- [ ] **최소 구현:** 16MiB 응답, 20,000 객체/2,048 블록정의, 판정64블록/5,000객체, WCS 좌표·owner/layout·instance identity 검증을 보존한다. 공통 파서/자산은 재사용하고 LISP 호출·텍스트 decoding은 제품 wrapper에서 선택한다. AutoCAD 초기 호출은 기존2인자 open/UTF-8 후 로컬 코드페이지 경로를 실험 대상으로 두며 실기 호환은 T8까지 미확인이다. 앱 경로/nonce만 명령 인자에 넣고 도면문자열을 명령으로 실행하지 않는다. 보안 차단/미완료/식별 불일치 응답에서 임의 재실행하지 않는다.
- [ ] **통과 확인:** 위 시험 + `python -m pytest tests/unit/test_bulk_snapshot.py tests/unit/test_bounded_detector.py tests/unit/test_snapshot_performance.py tests/unit/test_packaging_contract.py -q` PASS. 템플릿 프로파일 파일/해시와 기존판정은 변경 없음. import wrapper만 보존하고 검증 로직을 복제하지 않는다.
- [ ] **커밋:** T4 명시 파일과 이동만 stage, `git commit -m "refactor: share bounded snapshots with CAD-specific transports"`.

## T5 — AutoCAD 플롯 어댑터 (AC-04)

**Files:** 위 T5 파일 + `tests/unit/test_autocad_plotting.py`, 기존 `tests/unit/test_pdf_orientation.py`.

**Interfaces:** `autocad/plotting.py`: `plot_pdf(raw: Any, output: Path, window: Rect, rotation: Rotation, preferred_media_names: tuple[str, ...]) -> None`; `validate_orientation(output: Path) -> None`. AutoCADDocument의 공통 `plot_pdf`는 이 함수에 위임한다. GstarCAD 전용 방향 보정을 호출하지 않는다.

- [ ] **실패 테스트 작성:** 원시 COM fake와 합성 PDF로 계약 확인.
  ```python
  plot_pdf(raw, output, window, 90, ("User77",))
  assert raw.layout.measured_media_mm == (297.0, 210.0)
  assert raw.layout.window == window
  assert gstar_normalizer.call_count == 0
  assert output.read_bytes() == already_landscape_pdf_bytes
  ```
  `test_unknown_a4_name_resolved_by_dimensions`, `test_letter_named_user77_rejected`, `test_window_before_window_plot_type`, `test_four_rotations_inverse_mapping`, `test_portrait_or_unexplained_rotation_e420`, `test_missing_ctb_or_pc3_fails_before_plot`, `test_invalid_pdf_not_published` 추가.
- [ ] **실패 확인:** `python -m pytest tests/unit/test_autocad_plotting.py -q` → 미구현 FAIL.
- [ ] **최소 구현:** 공개 COM 속성에 대한 시험 구현으로 장치/CTB 존재→용지 실치수→SetWindowToPlot→PlotType→Fit/Center/선가중치→역회전→PlotToFile 순서를 적용한다. AutoCAD에서의 적합성은 T8 검증 대상이며 GstarCAD 성공을 근거로 대신하지 않는다. AutoCAD 용지 선택은 선호 이름보다 실치수를 우선하고, 미확인 portrait를 자동 보정하지 않고 E420으로 처리한다. 공통 validate_pdf 기준을 완화하지 않는다.
- [ ] **통과 확인:** 위 시험과 기존 `tests/unit/test_pdf_orientation.py`, `tests/unit/test_pdf_validator.py`, `tests/unit/test_plot_settings.py` PASS. 올바른 가로 PDF는 바이트 변경 없이 유지한다. 방향 보정이 실제로 필요하면 T8 증거와 명세 변경 검토 후 별도 수정한다.
- [ ] **커밋:** T5 명시 파일만 stage, `git commit -m "feat: add experimental AutoCAD plot adapter"`.

## T6 — CLI/GUI 선택과 진단 연결 (AC-02/03/05)

**Files:** 위 T6 파일 + `tests/unit/test_cad_factory.py`, `tests/unit/test_cad_diagnostics.py`, 기존 `tests/unit/test_cli.py`, `tests/unit/test_desktop_launcher.py`, `tests/unit/test_result_presenter.py`.

**Interfaces:** `create_session(candidate: CadCandidate) -> CadSession`. `resolve_selection(config: AppConfig, provider: ProviderId | None, prog_id: str | None, allow_experimental: bool) -> CadSelection`. `DesktopUI.choose_cad_provider() -> ProviderId | None`, `choose_cad_candidate(candidates: tuple[CadCandidate, ...]) -> str | None`, `confirm_experimental_autocad() -> bool` 추가. `build_diagnostic_record(provider: ProviderId, prog_id: str, reported_version: str | None, app_version: str, stage: str, code: str | None) -> dict[str, object]`는 허용 필드만 반환한다.

- [ ] **실패 테스트 작성:** CLI/UI fake가 실제 선택과 무기동 상태를 확인한다.
  ```python
  assert main(["--self-check"]) == 0
  assert dispatch_spy.call_count == 0
  assert main(ambiguous_noninteractive_args) == 2
  assert run_desktop(run_cli_spy, ui=cancelled_ui) == 0
  assert run_cli_spy.call_count == 0
  assert record["provider"] == "autocad"
  assert set(record) == {"provider", "prog_id", "reported_version", "app_version", "stage", "code"}
  ```
  `test_provider_override_clears_old_progid`, `test_opt_in_warning_before_start`, `test_autocad_failure_never_starts_gstarcad`, `test_gui_selection_roundtrips_to_cli`, `test_unavailable_cad_does_not_break_self_check`, `test_error_names_selected_provider` 추가.
- [ ] **실패 확인:** `python -m pytest tests/unit/test_cad_factory.py tests/unit/test_cad_diagnostics.py tests/unit/test_cli.py tests/unit/test_desktop_launcher.py tests/unit/test_result_presenter.py -q` → 옵션/메서드 부재 FAIL.
- [ ] **최소 구현:** `--cad {gstarcad,autocad}`, `--cad-prog-id`, `--allow-experimental-autocad`, 읽기전용 `--list-cad`를 추가한다. GUI는 기본GstarCAD 표시, AutoCAD 선택 시 미검증 경고/확인, 후보1개는 표시 후 사용·다수는 필수선택·취소는0종료. 선택 결과는 CLI 인자로 전달하여 동일 preflight 사용. 동적으로 만든 PowerShell UI에 경로/제품명을 코드로 삽입하지 않고 데이터 인코딩해서 전달한다. AutoCAD 경고 문구: `AutoCAD 지원은 실험적이며 실제 출력/버전 호환 검증이 완료되지 않았습니다.`
- [ ] **진단 연결:** COM import는 변환 실행 때 lazy load. self-check는 후보/실행환경 성공을 요구하지 않고 기존 의존성/프로파일 검증만 한다. 시작/열기/판정/플롯/검증/종료 단계에 선택제품/보고버전(미확인은null)/앱버전/오류코드를 붙인다. 공개용 증거는 위 allowlist만 사용하고 traceback/절대경로/원본문자는 로컬 기술로그와 분리한다. E203/E311 안내를 GstarCAD로 고정하지 않는다.
- [ ] **통과 확인:** T6 전부 PASS + `python -m dwg_to_pdf --help`, `python -m dwg_to_pdf --self-check`; 후자는 `RUNTIME_SELF_CHECK_OK`, CAD 생성0회. `--list-cad`는 목록만 표시하고 변환/GUI를 시작하지 않는다.
- [ ] **커밋:** T6 명시 파일만 stage, `git commit -m "feat: expose explicit experimental CAD selection"`.

## T7 — 오프라인/기존 회귀와 실험 번들 (AC-05)

**Files:** 위 T7 파일 + `tests/unit/test_autocad_validation_gate.py`, 기존 `tests/unit/test_packaging_contract.py`, `tests/unit/test_release_harness.py`.

**Interfaces:** `autocad` pytest marker 등록. `tools/smoke_frozen_bundle.py`에 `--config` 선택인자를 추가해 미검증 AutoCAD 설정을 별도 파일로 넘긴다. 기존 인자는 유지한다. `VALIDATION.md`는 제품/버전/commit/PC별명/표본해시/native여부/명령/PASS·FAIL·SKIP/NOT_RUN/사용자검토 필드를 갖는다.

- [ ] **실패 테스트 작성:** `test_bundle_contains_shared_lisp`, `test_default_provider_remains_gstarcad`, `test_live_autocad_requires_opt_in_environment`, `test_frozen_smoke_passes_config_explicitly` 추가. `assert manifest_default_provider == "gstarcad"`; `assert live_tests_run_without_opt_in == 0`; `assert packaged_lisp_count == 1`를 검증한다.
- [ ] **실패 확인:** `python -m pytest tests/unit/test_autocad_validation_gate.py tests/unit/test_packaging_contract.py tests/unit/test_release_harness.py -q` → 이전 번들 경로/marker 계약 FAIL.
- [ ] **최소 구현:** 공유 LISP와 양쪽 lazy import를 번들에 포함한다. 개발/협업 안내의 오프라인 명령을 `python -m pytest -m "not gstarcad and not autocad" -q`로 바꾼다. AutoCAD 실기 실행은 marker뿐 아니라 환경 opt-in도 요구하도록 공통 fixture를 둔다. 기존 release ZIP을 덮어쓰거나 AutoCAD 공식 지원으로 표시하지 않는다.
- [ ] **G2 확인:** 새 오프라인 명령 전체 PASS. 기존660PASS/10SKIP는 과거 참고치일 뿐 정확한 현재 count를 기록한다. CAD 없는 self-check와 금지 API/설정 변경 여부를 검토한다.
- [ ] **G3 확인:** GstarCAD가 있는 허가된 시험 PC에서 `python -m pytest -m gstarcad -q` 실행. 기존 시험별 `GSTARCAD_TEST_DWGS` 등 필수 환경을 안내대로 설정하고 필수시험 SKIP는 게이트 미통과로 남긴다. 승인13종+기존 파생30개를 native on/off로 비교하고 원본해시/mtime·사용자PID·APP 종료·판정·PDF를 기록한다. baseline은 제품기준 커밋과 같은환경으로 측정, 기존 비교 도구로 회귀 확인. 환경이 없으면 BLOCKED_ENVIRONMENT.
- [ ] **번들 검증:** G2/G3 통과 후 개발 안내의 `packaging/build.ps1` 빌드 및 `packaging/verify_bundle.ps1` 검사를 실행한다. EXE 자체검사와 GstarCAD 변환 시험, AutoCAD 미설치/opt-in 거부 시험을 분리 기록한다. AutoCAD 실제 변환은 T8 전 NOT_RUN. 배포 게시에는 별도 사용자 승인 필요.
- [ ] **커밋:** T7 명시 파일만 stage, `git commit -m "test: gate experimental CAD support and packaging"`. AC-05 결과/남은위험을 이슈에 남기고 독립 전체 리뷰를 받는다. 구현 main 병합은 사용자 승인 후 PR로 수행한다.

## T8 — 실제 AutoCAD 검증 (AC-06 / 환경 확보 후)

**Files:** 위 T8 파일 + `tests/unit/test_benchmark_safety.py`.

**Interfaces:** benchmark의 기존 인자에 `--config PATH`를 추가하고 선택된 팩토리를 사용한다. 라이브 fixture는 `AUTOCAD_TEST_ENABLED=1`, `AUTOCAD_TEST_CONFIG`, `AUTOCAD_TEST_DWGS`(세미콜론 구분 절대경로)를 요구한다. 환경이 없으면 이유 있는 SKIP; G4는 NOT_RUN으로 남긴다. 기존 Gstar benchmark 동작은 유지한다.

- [ ] **실패 테스트 작성:** mock benchmark에서 `assert actual_provider == selected_provider`, `assert sources_unchanged`, `assert not foreign_process_terminated`. 라이브 시험 `test_autocad_preserves_source_and_user_process`, `test_autocad_13_profiles_and_30_variants`, `test_autocad_failed_file_does_not_stop_next`는 실제 결과를 assert하며 결과 파일만 조작해 PASS시키지 않는다.
- [ ] **실패 확인:** `python -m pytest tests/unit/test_benchmark_safety.py -q`에서 새 provider/config 계약 FAIL 확인. 라이브시험은 환경 없을 때 FAIL 대신 NOT_RUN/SKIP가 정상이며 통과 증거는 아니다.
- [ ] **시험 장치 구현:** T6 팩토리와 기존 표본/보호/시간 측정을 사용하고 프로파일을 다시 학습하거나 수용 기준을 바꾸지 않는다. CAD 열기/판정/플롯/검증/시작·종료 시간을 분리하고 진단 COM probe 시간은 순수 변환시간으로 보고하지 않는다.
- [ ] **환경 확인:** 제품명/에디션/버전/비트수·유효라이선스·PC3/CTB·폰트·한글경로를 실제 확인하고 해당 버전 Autodesk 공식자료와 대조한다. LT/수직제품이면 시험범위 변경 승인을 먼저 요청한다.
- [ ] **G4 시험:** `python -m pytest -m autocad -q`; 13종 및 파생30개, 이동/직각회전, blank/N/A, 비균일/중복Scale/오류파일→정상파일, 출력잠금, native on/off, LISP차단, 사용자 CAD 공존을 검증한다. 1page/A4가로/비공백/도곽영역/문자/선가중치/흑백을 확인하고 엔진간 차이는 사용자검토 대기로 남긴다. 실제pdf와 원본은 로컬 보관, 공개 증거는 비식별 결과/해시만 사용한다.
- [ ] **커밋:** 테스트/harness와 비식별 결과만 stage, `git commit -m "test: record live AutoCAD validation evidence"`. FAIL/SKIP/NOT_RUN을 숨기지 않고 실패수정은 해당 T작업의 재현시험부터 반복한다.

## T9 — 다른 PC·frozen·지원 승인 (AC-07)

**Files:** 위 T9 문서. 구현 변경이 필요하면 별도 재현시험/수정 커밋으로 분리한다.

**Inputs / Produces:** G4 증거와 T7 ZIP/SHA256을 입력으로 받고, 특정 제품·버전·PC의 G5 결과 및 사용자 승인 링크를 출력한다. 증거 없는 지원 버전은 목록에 넣지 않는다.

- [ ] **준비:** 다른 PC에서 main/작업브랜치의 정확한 SHA를 가져오고 신규 환경 준비/작업 담당을 이슈에 기록한다. 실행용 PC는 개발 Python 없이 ZIP으로 시험한다. AutoCAD 자체/라이선스는 사용자가 준비한다.
- [ ] **실행:** ZIP 해시·self-check·후보선택·실제13종/오류배치·사용자CAD공존·원본보호·APP 종료를 확인한다. `smoke_frozen_bundle.py --config ...`는 개발PC harness 검증에 사용하고 Python 없는 PC에서는 EXE 직접 실행 결과를 기록한다.
- [ ] **수용 판정:** 모든 필수 항목에 증거/사용자 출력 검토 승인 필요. 하나라도 실패/미실시면 G5 미통과. 환경이 없으면 BLOCKED_ENVIRONMENT 유지, GstarCAD 기존 배포는 유지한다.
- [ ] **문서/커밋/게시:** 실제 검증일/환경/지원 버전/한계를 기록하고 사용자 릴리스 승인을 받는다. 명시 파일만 stage, `git commit -m "docs: record approved AutoCAD support matrix"`. 승인된 PR/릴리스만 게시하고 기존 릴리스와 백업 브랜치는 보존한다.

## 자체 검토와 다른 PC 인계

| 명세 요구 | 구현/검증 소유 |
|---|---|
| R01 기존 호환 | T1,T2,T7 |
| R02~05 선택/탐지/실험상태 | T1,T6,T7 |
| R06~08 소유권/단일세션/원본 | T2,T3,T7,T8 |
| R09 기존13종 판정 | T2,T4,T7,T8 |
| R10~11 플롯/제품 차이 | T4,T5,T8 |
| R12~13 응답보안/호환경로 | T4,T7,T8 |
| R14 검증 구분 | T7~T9 |
| R15 진단/정보보호 | T6,T8,T9 |
| R16 배포 보호 | T6,T7,T9 |

작성 시 명세16개 요구의 소유 작업, Review Focus5개 시험, 공통 시그니처, 제품/문서 승인 분리를 자체 점검했다. 신규 알고리즘이나 실기 성공 결과를 이 문서에 가정하지 않았다.

작업 종료/PC 변경 시 [협업 인계 템플릿](../../autocad/COLLABORATION.md)에 T번호+AC번호, 담당/파일, 마지막 push SHA, 실행한 정확한 명령/결과, NOT_RUN, 다음 한 단계를 기록한다. 새 PC는 [관리 이슈 #1](https://github.com/jeonbyungryong/DWG-PDF-/issues/1)의 G1 승인과 실행 방식 확인 전 제품 구현을 시작하지 않는다.
