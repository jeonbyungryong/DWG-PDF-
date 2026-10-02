# Task 6 완료 보고서 - 정확 플롯, PDF 검증, 원본 안전 출력

## 결론

Task 6의 정확한 Window 플롯 설정, 임시 DWG 작업공간, PDF 하드 게이트, 원자적 게시를 구현하고 검증했다. 최초 구현/테스트 커밋은 `2de71cf`, 리뷰 lifecycle·cleanup 수정 커밋은 `63354f2`이다. 대상 도면에 저장된 Plot Window는 읽지 않으며, 계산된 Window만 `SetWindowToPlot`에 전달한다.

## 확인된 사실

- 구현 파일: `plot_settings.py`, `plotter.py`, `temp_workspace.py`, `pdf_validator.py`, `com_session.py`.
- 플롯 계약: `DWG To PDF.pc3`, 해석된 A4 Canonical Media, mm 단위, Window, Fit, Center, `monochrome.ctb`, plot style, lineweight를 명시적으로 적용한다.
- GstarCAD COM의 `SetWindowToPlot`에는 `VT_ARRAY | VT_R8` VARIANT 두 개를 전달한다.
- 도곽 0/90/180/270도는 각각 역회전 PlotRotation 0/270/180/90도, 즉 COM enum 0/3/2/1로 매핑한다. 그 외 값과 Boolean 유사값은 `E307`로 거부한다.
- `BACKGROUNDPLOT`을 0으로 설정하고 플롯 후 가능한 경우 기존 값을 복원한다.
- `PlotToFile` false/예외/파일 누락/0-byte/불안정 출력을 `E410`으로 거부한다.
- PDF는 `%PDF-` 헤더, 엄격 파싱, 암호화 거부, 정확히 1페이지, 유한 치수, A4 가로 ±0.20 mm, 렌더 성공, 비공백을 모두 통과해야 한다.
- 검증기는 PDF를 메모리에서 열고 reader/page/bitmap/PIL handle을 닫아 Windows rename/cleanup을 방해하지 않는다.
- `SourceWorkspace`는 일반 `.dwg` 원본만 허용하고 symlink/reparse, fabricated workspace, 원본/외부/비활성 경로, 동일 파일을 거부한다. 원본 SHA-256과 mtime은 종료 시 다시 확인한다.
- 쓰기 문서는 반드시 `with session.working_document(workspace) as document:` 경계로 열며, 탐지·플롯·검증 본문 예외에서도 `Close(False)`가 `SourceWorkspace` 정리 전에 실행된다. 수동 성공 경로 close에 의존하는 public opener는 제거하고 내부 opener만 유지했다.
- `SourceWorkspace` 삭제는 `ignore_errors=True`를 사용하지 않는다. 50 ms 간격으로 최대 4회 제한 재시도하고, 실패하면 primary 오류를 note/cause로 보존한 `E400`을 반환한다.
- cleanup 재시도가 모두 실패해도 `SourceWorkspace.__exit__`는 원본 SHA-256과 mtime을 각각 다시 검사한다. cleanup 오류와 identity 오류를 독립 수집하며, 둘 다 발생하면 원본 변경 `E400`을 최종 오류로 유지하고 cleanup 잔여 경로는 note, 본문 예외는 note와 cause로 함께 보존한다. 따라서 cleanup 실패가 원본 변경을 숨길 수 없다.
- 실패하거나 잘못된 부분 PDF는 plot/publish의 `finally`에서 제거한다. plot false/예외/누락/0-byte/불안정, PDF 검증, replace, cleanup 오류에서 기존 최종 PDF는 교체되지 않는다.
- source/output `resolve`, `stat/lstat`, `samefile`, `copy`, `mkdir`, replace, unlink 계열 파일 시스템 오류는 `E400`, `E410`, `E420`, `E421` 경계로 감싸 raw OS 오류를 노출하지 않는다.

## 테스트 결과

잠금 파일 `requirements.lock`을 새 `.task6-review-deps` 경로에 설치하고 pywin32의 `win32`, `win32/lib`, `pywin32_system32` 경로를 명시하여 실행했다.

- 수정 전 집중 기준: `38 passed, 1 skipped, 1 deselected`.
- 수정 전 전체 기준: `250 passed, 1 skipped, 5 deselected`.
- 임시 PDF 누락 RED: `1 failed`, `temp_workspace.py:129`의 raw `FileNotFoundError` 확인.
- 최소 수정 GREEN: `1 passed`.
- 리뷰 RED: `23 failed, 26 passed, 1 skipped, 1 deselected`. lifecycle context 부재, silent cleanup, raw FS 오류, 임시 PDF 잔류, 안정성 주입점 부재가 각각 재현됐다.
- 추가 경계 RED: temporary resolve, 일반 COM exception, samefile, reparse/lstat 결함을 각각 독립 실패로 재현했다.
- 최종 집중: `66 passed, 1 skipped, 1 deselected`.
- 최종 전체 비실기: `278 passed, 1 skipped, 5 deselected`.
- staged `git diff --check`: 통과.

### cleanup + 원본 변경 복합 경계 추가 수정

리뷰에서 확인된 마지막 Important를 위해 다음 세 회귀 테스트를 추가했다.

- 본문 예외 + cleanup 영구 실패 + 원본 변경: identity 검사 실행, 원본 변경 최종 `E400`, cleanup residue/path note, 본문 detail/cause를 동시에 요구한다.
- cleanup 실패 + 원본 불변: identity 검사 후 cleanup `E400`을 요구한다.
- 원본 변경 + cleanup 성공: 원본 변경 `E400`과 임시 작업공간 제거를 요구한다.

최신 코드에 대해 의존성 없는 수동 하네스를 실행한 결과는 다음과 같다. 각 경우 종료 구간의 SHA-256 함수와 mtime stat 함수가 정확히 한 번씩 호출됐음을 함께 단언했다.

- `COMBINED_OK sha=1 stat=1 source_primary cleanup_note body_cause residue`
- `CLEANUP_ONLY_OK sha=1 stat=1 cleanup_primary source_unchanged`
- `SOURCE_CHANGE_ONLY_OK sha=1 stat=1 source_primary cleanup_complete`
- `python -m compileall -q src tests/unit/test_temp_workspace.py`: 통과.
- `git diff --check`: 통과.

2026-07-20에 hash-locked `requirements.lock`으로 임시 workspace-local 의존성 환경을 다시 구성해 최종 pytest를 재실행했다. pywin32 import도 정상 확인했다. 이전 ACL/의존성 승인 제한은 해소됐으며, 아래 결과는 cleanup + 원본 변경 복합 경계 추가 수정을 포함한 최신 코드 기준이다.

- `tests/unit/test_temp_workspace.py`: `26 passed, 1 skipped`.
- 전체 pytest: `281 passed, 6 skipped in 3.12s`.
- pywin32 import: `OK`.

따라서 위의 `66 passed` 및 `278 passed`는 이전 중간 검증 기록이며, 최종 판정은 2026-07-20 전체 결과를 따른다. 변경 범위는 GstarCAD COM open/close 또는 plot 경로가 아닌 `SourceWorkspace.__exit__`의 cleanup 이후 오류 집계이므로 실제 COM 플롯은 다시 실행하지 않았다.

skip/deselect 항목은 opt-in GstarCAD 실기 테스트이며, 아래 실제 기계 증거로 별도 확인했다.

## 실제 DWG/PDF 검증

리뷰 수정 후 실제 GstarCAD 테스트를 다시 실행했다. APP 소유 PID `2444`에서 첫 working document 본문에 의도적 예외를 발생시켜 `Close(False)`와 workspace 제거를 확인한 다음, 같은 PID를 재사용해 아래 세 파일을 연속 플롯했다. 테스트는 `1 passed in 239.97s`로 종료됐다. 출력은 증거 기록 후 삭제했으며 커밋하지 않았다.

| 원본 | 검증 PDF | 크기 | 구조 결과 |
|---|---|---:|---|
| `윈도우 영역 학습용/TEMPLETE_1대1.DWG` | `TEMPLETE_1대1.<uuid>.pdf` | 25,930 bytes | 1 page, 297.0001 x 210.0001 mm, nonblank |
| `윈도우 영역 학습용/TEMPLETE_1대50.DWG` | `TEMPLETE_1대50.<uuid>.pdf` | 25,969 bytes | 1 page, 297.0001 x 210.0001 mm, nonblank |
| `XXX-XXXXA_Silicon Gromet A.DWG` | `XXX-XXXXA_Silicon Gromet A.<uuid>.pdf` | 38,446 bytes | 1 page, 297.0001 x 210.0001 mm, nonblank |

새 실기 PDF 세 장을 PDFium scale 2로 다시 렌더했다. 세 결과 모두 A4 가로 방향, 도곽/제목란 전체 포함, 정상 회전, 비공백이었다. 선과 문자에 잘림, 겹침, 파손이 없었고 실제 Grommet 도면의 형상과 치수가 판독 가능했다. 학습용 1:1/1:50 도면의 넓은 여백은 원본 내용 특성으로 확인했으며 저장된 잘못된 Window에 의한 오등록 징후는 없었다.

## 원본 및 프로세스 증거

| 원본 | SHA-256 | mtime_ns |
|---|---|---:|
| `TEMPLETE_1대1.DWG` | `15F65A792E68FD3A079F8104DDCC2A19DB001CF200CE309F6D3BC8D8753EFEF0` | `1784163568833450800` |
| `TEMPLETE_1대50.DWG` | `A57715DD338BF99240481E2CA67A3F8E43CACDC5AE3E861E37B33D61B4A8FA85` | `1784163594158690400` |
| `XXX-XXXXA_Silicon Gromet A.DWG` | `30E07D900658FEF6A546280340B2E35B96ADAC3C1D4D035C991FE3EE756C52D6` | `1784096583000257100` |

리뷰 후 실기 실행 전후에도 위 SHA-256과 mtime이 정확히 일치했다. pre-existing PID는 없었고 최종 확인 결과 `GCAD_PIDS=NONE`이다. 실제 실행 및 fault-injection 테스트 이후 최근 `dwg-to-pdf-*` 시스템 TEMP residue도 제거하고 재확인했다.

## 리스크와 한계

- GASKET 도면에는 균일 축척된 `_Oblique` 치수 기호 INSERT가 있다. Task 5의 기존 detector가 이를 지원하지 않는 frame transform으로 분류하는 상위 제한이며 Task 6 플롯/PDF 구현 범위가 아니다. 이 커밋에는 detector 변경을 섞지 않았다.
- 실기 PDF와 PNG는 검증 증거를 기록한 뒤 삭제했으므로 저장소에는 생성물이 없다.
- 인간 눈에 보이지 않는 선/제목란 픽셀 차이는 승인 기준이 아니며, 구조·치수·렌더·비공백 하드 게이트를 기준으로 판정했다.

## 정리 상태

리뷰 수정 검증 당시 `.task6-review-deps`, `.pytest_cache`, 모든 `__pycache__`, `tmp/pdfs`, `output/pdf`를 제거했으며 PDF, PNG, 로컬 의존성, 캐시는 커밋하지 않았다. 2026-07-20 최종 pytest는 hash-locked `requirements.lock` 기반의 임시 workspace-local 의존성 환경에서 실행했으며, 해당 환경은 저장소 산출물이나 커밋 대상이 아니다.
