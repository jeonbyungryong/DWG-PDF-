# GASKET `_Oblique` INSERT 오탐 수정 보고서

## 결론

`XXX-XXXXA_GASKET_FRT.DWG`의 균일 축척 `_Oblique` 치수기호 INSERT가 Scale 탐지 전에 전체 중첩 순회를 중단시키던 결함을 수정했다. 비지원 변환 자체를 허용하지 않았다. 대신 bounded 정의 순회로 해당 INSERT가 Scale 텍스트/속성 또는 title/frame linework에 기여할 수 없음을 증명한 경우에만 건너뛴다. Scale/title/frame 후보가 한 개라도 있으면 기존 `E303` fail-closed 경로를 그대로 사용한다.

## 확인된 원인

- `template_detector._bounded_text_and_insert_snapshots()`가 server-filtered top-level INSERT를 모두 `nested_text_snapshots()`로 순회했다.
- 해당 순회는 block 정의/관련성 판정 전에 `_matrix_for(reference)`를 호출한다.
- 실제 GASKET의 `C07`은 `_Oblique`, 90도 회전, `x_scale == y_scale == 17.5`이므로 `document.py`의 `unsupported scaled or reflected block transform` (`E303`)에서 탐지가 중단됐다.
- INSERT snapshot은 Scale 값 매칭에 사용하지 않는다. 수정 뒤에도 `detect_scale_cell()`은 `INSERT`를 값 후보에서 제외한다.

## 수정 내용

- `GstarDocument.is_noncontributing_unsupported_insert()`를 추가했다.
  - 원래 `_matrix_for()`가 허용하는 단위 축척 + quarter-turn 변환은 이 경로에서 건너뛰지 않는다.
  - 오직 root의 scale/reflection 또는 non-quarter-turn 변환에만 bounded block-definition preflight를 실행한다.
  - reached definition에 `TEXT`, `MTEXT`, `ATTRIB`, `LINE`, `LWPOLYLINE`, 또는 속성 보유 INSERT가 하나라도 있으면 `False`를 반환하여 기존 변환 `E303`을 다시 발생시킨다.
  - 위 기여 가능 객체가 전혀 없는 annotation-only 정의(예: `_Oblique` marker)만 `True`로 반환해 건너뛴다.
  - `Blocks.Item(name)`만 사용하며 Blocks/ModelSpace 전체 열거를 추가하지 않았다. 동일 shared `TraversalBudget`, cycle guard, root-to-instance Handle 경로는 유지한다.
- text detector와 `filtered_geometry_snapshots()` 모두 위 증명 결과가 `True`인 INSERT만 skip한다. 따라서 Scale 탐지 후의 frame/title structural 검증도 `_Oblique`에서 다시 중단되지 않는다.
- global uniform-scale allowance, filename scale 판정, source DWG write 경로, COM batch PID/`Close(False)` 동작은 변경하지 않았다.

## TDD 증거

### RED

생성한 최소 회귀 테스트는 top-level `C07` 형태의 `_Oblique` (90도, 17.5/17.5)와 top-level `Scale`/`1:5`를 함께 둔다. `_Oblique` 정의는 detector/structural pipeline이 사용하지 않는 `AcDbPoint` marker 하나만 갖는다.

명령:

```powershell
$py -m pytest tests\unit\test_bounded_detector.py::test_detector_ignores_scaled_oblique_annotation_before_scale_traversal --basetemp .pytest-tmp\gasket-oblique-red -q
```

결과: `1 failed in 0.15s`.

예상한 실패 위치는 `template_detector.py:48 -> document.py:375 -> _matrix_for()`였고, 정확한 오류는 `E303: unsupported scaled or reflected block transform`이었다. 즉 테스트 오타가 아니라 기존의 전수 INSERT 중첩순회 결함을 재현했다.

### GREEN 및 fail-closed 보호

수정 뒤 동일 회귀 테스트는 다음 결과였다.

```powershell
$py -m pytest tests\unit\test_bounded_detector.py::test_detector_ignores_scaled_oblique_annotation_before_scale_traversal --basetemp .pytest-tmp\gasket-oblique-green -q
# 1 passed in 0.10s
```

추가 보호 테스트 `test_detector_rejects_scaled_insert_that_can_contribute_frame_linework`는 2배 균일 축척 FRAME INSERT 안의 `AcDbLine`을 사용한다. 해당 INSERT는 건너뛰지 않고 기존대로 `E303`이 발생함을 확인했다.

최종 집중 명령:

```powershell
$py -m pytest tests\unit\test_bounded_detector.py::test_detector_ignores_scaled_oblique_annotation_before_scale_traversal tests\unit\test_bounded_detector.py::test_detector_rejects_scaled_insert_that_can_contribute_frame_linework --basetemp .pytest-tmp\gasket-oblique-final-targeted -q
# 2 passed in 0.11s
```

## 최종 검증

명령은 hash-locked 의존성 디렉터리 `C:\Users\dknbtech\Documents\APP 개발\.codex-deps\dwg-to-pdf`를 사용했다.

- `PYTHONPATH=<deps>\win32\lib;<deps>\win32;<deps>;src`
- `PATH`에 `<deps>\pywin32_system32;<deps>` 선행
- `PYTHONDONTWRITEBYTECODE=1`
- workspace-local `--basetemp .pytest-tmp\gasket-oblique-*`만 사용했고, 기존 untracked `.pytest-tmp` ACL residue를 수정/삭제하지 않았다.

```powershell
$py -m pytest tests\unit\test_bounded_detector.py tests\unit\test_reference_registrar.py --basetemp .pytest-tmp\gasket-oblique-final-related -q
# 60 passed in 0.17s

$py -m pytest -m "not gstarcad" --basetemp .pytest-tmp\gasket-oblique-final-full -q
# 283 passed, 1 skipped, 5 deselected in 1.33s

$py -m compileall -q src tests\unit\test_bounded_detector.py
# exit 0
```

## 실제 COM 검증 상태

실제 원본은 존재하며 읽기만 수행했다.

| 항목 | 값 |
|---|---|
| 원본 | `D:\2026 PROJECT\SK ON\PAD\05.설계도면\02.설계도면(3D)\PART\변환 도면\XXX-XXXXA_GASKET_FRT.DWG` |
| 현재 SHA-256 | `65AA3461769C8DD139A6C74E9C5819F08D9E02A5C6CD9D4F20D32EA7469854B3` |
| 현재 mtime UTC | `2026-07-15T06:13:47.7874200Z` |
| 크기 | `807,597` bytes |

유효한 실기 탐지/변환 증거는 이번 수정 후 획득하지 못했다. `GstarSession('GstarCAD.Application.26')` read-only probe는 noninteractive 실행에서 stdout 없이 반환했고, 새 APP-owned `gcad` PID `22444`를 남겼다. 해당 PID는 probe 시점에 생성된 것으로 확인해 종료했고, 이후 생성된 PID는 없었다. PID `5408`은 task brief보다 앞선 `08:32:45`에 이미 존재해 사용자 소유 가능성이 있으므로 보존했다. 따라서 내부 Scale `1:5`, A4 landscape 1-page nonblank PDF, 원본 before/after hash+mtime 동일성은 이번 task에서 실기 검증하지 않았으며 주장하지 않는다.

## 변경 파일

- `src/dwg_to_pdf/gstarcad/document.py`
- `src/dwg_to_pdf/gstarcad/template_detector.py`
- `tests/unit/test_bounded_detector.py`
- `.superpowers/sdd/task-gasket-oblique-report.md`

## Self-review 및 잔여 리스크

- self-review로 새 판단 경로가 root INSERT에만 적용되고, `Blocks.Item` indexed 접근과 shared budget을 유지함을 확인했다.
- line/polyline/text/attribute/child INSERT가 하나라도 있으면 fail-closed이므로 비지원 frame/title/Scale 구조를 균일 축척이라는 이유만으로 허용하지 않는다.
- annotation-only 판정은 현재 detector와 structural verifier가 소비하지 않는 entity type에만 의존한다. 향후 verifier가 ARC/CIRCLE/HATCH 등 새 primitive를 구조 판정에 사용하게 되면 이 allowlist를 그 변경과 함께 재검토해야 한다.
- 실제 `_Oblique` block definition 및 1:5 PDF end-to-end는 COM probe blocker 때문에 미검증이다.
- Git 실행 파일을 현재 PATH와 일반 설치 위치에서 찾지 못했으므로 diff/status/commit을 수행할 수 없었다. 이 보고서와 source/test 변경은 uncommitted 상태다.

## Review 보완 (Important + Minor)

### 추가 TDD RED → GREEN

리뷰 보완 전에 아래 parameterized integration-level 테스트를 먼저 추가했다.

- detector route: `TEXT`, `ATTRIB`, frame `LINE` contributor 각각에 uniform scale, nonuniform scale, mirror/reflection, non-quarter-turn transform을 적용했다 (12 cases).
- geometry route: frame `LINE` contributor와 위 4 transform 각각에 대해 `filtered_geometry_snapshots()` 직접 호출 및 `verify_rotation()` 호출을 모두 검증했다 (4 cases; 두 geometry API 경로를 함께 실행).
- Minor regression: 비지원 transform 아래 `AcDbCircle` 같은 unknown primitive는 annotation-only로 fail-open하지 않고 `E303`이어야 한다.

RED 명령:

```powershell
$py -m pytest tests\unit\test_bounded_detector.py -k "relevant_unsupported_root_transforms or geometry_routes_remain_fail_closed or unknown_annotation_primitive" --basetemp .pytest-tmp\gasket-review-red -q
```

RED 결과: `1 failed, 16 passed, 49 deselected in 0.15s`.

실패한 것은 의도한 Minor 결함 하나였다. `test_detector_fails_closed_on_unknown_annotation_primitive_under_unsupported_transform`가 `DID NOT RAISE AppError`로 실패했다. 즉 기존 preflight가 `_entity_type()`의 unknown `AcDbCircle`을 `continue`해 scaled root를 annotation-only로 잘못 허용했다. 나머지 16 cases는 기존 `TEXT`/`ATTRIB`/frame 및 text/geometry outer guard가 이미 `E303` fail-closed임을 확인하는 coverage였다.

최소 수정은 preflight의 generic unknown-entity `continue`을 제거하고, `_ANNOTATION_ONLY_OBJECT_NAMES = {"ACDBPOINT"}` 및 `_is_permitted_annotation_only_entity()`로 바꾼 것이다. `AcDbPoint`만 현재 Scale/title/frame detector와 structural verifier가 소비하지 않는 annotation marker로 명시 허용한다. 어떤 신규 primitive도 소비하지 않았고, 새로운/unknown entity는 모두 원래 `E303`으로 fail closed 한다. 기존 `_Oblique` regression은 `AcDbPoint` marker로 이 explicit allowlist도 실행한다.

GREEN 명령:

```powershell
$py -m pytest tests\unit\test_bounded_detector.py -k "relevant_unsupported_root_transforms or geometry_routes_remain_fail_closed or unknown_annotation_primitive" --basetemp .pytest-tmp\gasket-review-green -q
# 17 passed, 49 deselected in 0.12s
```

최종 review covering 결과:

```powershell
$py -m pytest tests\unit\test_bounded_detector.py tests\unit\test_reference_registrar.py --basetemp .pytest-tmp\gasket-review-final-related -q
# 77 passed in 0.20s

$py -m pytest -m "not gstarcad" --basetemp .pytest-tmp\gasket-review-final-full -q
# 300 passed, 1 skipped, 5 deselected in 1.35s

$py -m compileall -q src tests\unit\test_bounded_detector.py
# exit 0
```

### Bounded real COM 재조사

기존 guarded harness를 다음 환경으로 한 번 실행했다. `GSTARCAD_TEST_DWGS`에는 같은 GASKET 원본을 세 번 넣어 harness의 sequential-open contract (`len >= 3`)을 만족시켰다. 이는 원본을 write하지 않는 `open_readonly_copy()` 경로다.

```powershell
$env:GSTARCAD_TEST_DWGS="$src;$src;$src"
$env:GSTARCAD_PROG_ID='GstarCAD.Application.26'
$py -m pytest tests\integration\test_com_contract.py::test_one_owned_pid_opens_multiple_drawings_sequentially_without_source_changes -m gstarcad -s -q --basetemp .pytest-tmp\gasket-oblique-com
```

Harness stdout (강제 중단 전):

```text
COM_BEFORE_PIDS=5408
COM_BEFORE_SHA256=65AA3461769C8DD139A6C74E9C5819F08D9E02A5C6CD9D4F20D32EA7469854B3
COM_BEFORE_MTIME_UTC=2026-07-15T06:13:47.7874200Z
```

stdout에는 `owned_pid=...`가 출력되지 않았고 stderr도 없었다. runner Python PID `31408` 및 새 `gcad` PID `31684`가 계속 살아 있어 harness는 exit code를 반환하지 못했다. `31684`는 이 attempt에서 새로 생성된 APP-owned PID임을 시작 전/후 PID 비교로 확인했고, runner PID `31408` 및 its attempt PowerShell `3888`과 함께 회수했다. `5408`은 시작 전부터 존재한 PID이므로 종료하지 않았다.

단일 bounded diagnostic으로 정확한 stage를 좁혔다. 명령은 같은 `$py -u -c` 진단 코드에서 `pythoncom` import, `win32com.client` import, `_gstar_pids()`, `DispatchEx` 전후를 flush log로 남겼다. stage log는 다음과 같았다.

```text
STAGE BOOT
STAGE PYTHONCOM_IMPORTED
STAGE WIN32COM_IMPORTED
STAGE SESSION_IMPORTED
STAGE BEFORE_PIDS={5408}
STAGE DISPATCH_BEGIN
```

새 `gcad` PID `17628`와 diagnostic Python PID `7348`가 남았고 `STAGE DISPATCH_DONE`은 기록되지 않았다. 따라서 정확한 blocker는 `win32com.client.DispatchEx('GstarCAD.Application.26')`가 새 process를 생성한 뒤 반환하지 않는 것이며, `Visible`, HWND/PID ownership proof, DWG read-only open, `_Oblique` traversal, PDF 변환에는 도달하지 못했다. 이 attempt에서 생성된 `17628`/`7348`만 회수했고 최종 `gcad` PID는 `5408` 하나다.

최종 원본 identity는 SHA-256 `65AA3461769C8DD139A6C74E9C5819F08D9E02A5C6CD9D4F20D32EA7469854B3`, mtime UTC `2026-07-15T06:13:47.7874200Z`로 harness 시작 전 값과 동일하다. COM의 `DispatchEx` blocker 때문에 `1:5` detector result, structural score, A4 one-page nonblank PDF는 여전히 실기 미검증이다.
