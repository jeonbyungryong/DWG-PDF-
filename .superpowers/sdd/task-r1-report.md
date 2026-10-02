# Task R1 Report — Reusable Owned GstarCAD Batch Session

## 결론

Task R1 구현과 테스트를 완료했다. 구현 커밋은
`da8dff7fb112c31e5a7cd3f7aaf4965140cbd2d2`
(`fix: reuse one owned GstarCAD batch session`)이다.

한 번 소유권이 증명된 APP 전용 GstarCAD 프로세스에서 DWG 3개를 한 번에 하나씩
순차적으로 열고 `Close(False)`로 닫았다. 세 파일 모두 같은 APP 소유 PID `16912`를
유지했고, 실행 전부터 존재한 사용자 GstarCAD PID `10068`은 실행 중·종료 후 모두
살아 있었다. APP 소유 PID `16912`는 세션 종료 후 사라졌다.

## 구현 내용

- `GstarSession.is_usable`은 APP 참조, 소유권, 문서 닫기 실패 상태를 함께 검사한다.
- `close_document()`는 현재 raw/wrapped 문서 참조를 먼저 분리하고, raw 문서가 있으면
  항상 `Close(False)`를 정확히 한 번 호출한다.
- 정상 닫기 후 같은 APP/PID에서 다음 문서를 열 수 있다.
- 문서 닫기 실패는 안정 오류 `E203`으로 변환하며 세션을 재사용 불가로 표시한다.
- 멱등 닫기와 반복 `_release()`는 추가 Close/Quit 호출 없이 안전하게 끝난다.
- 종료 경로는 닫기 오류를 억제하고도 소유권이 증명된 APP만 Quit한다. 기존의 30초
  graceful timeout 및 proven-owned PID 한정 `taskkill` 조건은 유지했다.
- 서버 측 필터 SelectionSet, 제한된 중첩 블록 탐색, 원본 read-only 열기, 대상 DWG의
  저장 Plot Window 미사용 등 Task 4 계약은 변경하지 않았다.

## TDD RED/GREEN 증거

사용 런타임:
`C:\Users\dknbtech\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

- 기준선: `94 passed, 1 skipped in 0.57s`.
- RED: 생산 코드 변경 전 focused 테스트에서 기존 7개는 통과했고 신규 계약 4개는
  `AttributeError: 'GstarSession' object has no attribute 'close_document'`로 예상 실패했다.
- 최초 GREEN 점검은 신규 계약을 모두 통과했지만 기존 오류 메시지 호환성 테스트가
  `one file` 문구 회귀를 검출했다(`10 passed, 1 failed`). 기존 안정 문구를 보존했다.
- focused 최종: `11 passed in 0.14s`.
- 전체 최종: `99 passed, 1 skipped in 0.45s`. skip 1건은 환경변수 없을 때 의도적으로
  비활성화되는 실제 GstarCAD opt-in 테스트다.
- `git diff --check`: 오류 없음.

추가된 단위 계약은 순차 재사용, 두 번째 동시 open 거부, 멱등 close, close 실패 E203,
실패 후 재사용 거부, close 실패 후 반복 shutdown 안전성, 동일 owned PID 유지를 검증한다.

## 실제 GstarCAD 2026 검증

실행 조건:

- ProgID: `GStarCAD.Application.26`
- 기존 사용자 PID: `10068`
- APP 소유 PID: `16912`
- 결과: `1 passed in 51.92s`

한 세션에서 다음 3개를 순서대로 read-only open → 서버 측 filtered snapshot → Scale 후보
탐지 → `close_document()` 처리했다. 각 close 뒤 `owned_pid == 16912`를 확인했다.

| 입력 | SHA-256 실행 전/후 | mtime_ns 실행 전/후 |
|---|---|---:|
| `윈도우 영역 학습용/TEMPLETE_1대1.DWG` | `15F65A792E68FD3A079F8104DDCC2A19DB001CF200CE309F6D3BC8D8753EFEF0` | `1784163568833450800` |
| `TEMPLETE_1대50.DWG` | `4E0B38F20F1E600A59FD95BC776B98BC2ACCCE68FA0621013EE164001C7E80BF` | `1784104078643563400` |
| `TEMPLETE_5대1.DWG` | `00B5E797E3256C2FD7E53A14C3E49AFAEDC8FF37AF92E23BA7B4E974996A3F8C` | `1784108478235191000` |

표의 SHA-256과 mtime_ns는 각 파일에서 실행 전 값과 실행 후 값이 정확히 같았다.
테스트 종료 후 `gcad.exe` PID 집합은 다시 `{10068}`이었으므로 사용자 PID는 보존되고
APP 소유 PID만 정상 종료되었다.

## 변경 파일

- `src/dwg_to_pdf/gstarcad/com_session.py`
- `tests/unit/test_gstarcad_contracts.py`
- `tests/integration/test_com_contract.py`
- `.superpowers/sdd/task-r1-report.md`

## 리스크 및 한계

- 실제 COM 검증은 이 PC의 GstarCAD 2026과 위 3개 승인 템플릿에 한정한다. 다른 버전,
  언어팩, 손상 DWG 및 장시간 대량 배치는 후속 R3/R4 회귀가 필요하다.
- 실제 close 실패를 GstarCAD 프로세스에 강제로 주입하지 않았다. close 실패와 반복 정리는
  fake COM 단위 계약으로 검증했다.
- 세션 교체와 파일별 오류 격리는 R1 범위 밖이며 후속 BatchSession/오케스트레이터 작업이
  재사용 불가 상태를 보고 새 proven-owned 세션을 생성해야 한다.
- 테스트 실행용 `.test-deps`, `__pycache__`, `.pytest_cache`는 커밋 대상에서 제외했다.

## Review Follow-up — Open/cleanup 실패 경로 보강

리뷰 후속 구현 커밋은
`c6ec661f66bf8a57b583ab5287b968e03521d7d7`
(`fix: harden GstarCAD session cleanup failures`)이다.

### 수정 내용

- `Documents.Open(..., True)`가 `ReadOnly=False` 문서를 반환하면 그 raw 문서를 먼저 현재
  세션 문서로 추적한 뒤 공통 `close_document()` 경계로 닫는다.
- 이 `Close(False)`가 실패하면 `E203`을 유지하고 `_document_close_failed=True`로 세션을
  재사용 불가 처리한다. 이후 open은 `E201`로 차단되며 종료는 APP 소유 프로세스에만
  `Quit`을 적용한다.
- APP 소유 PID의 graceful 종료 대기 및 `taskkill`을 best-effort 구간으로 격리했다.
  `OSError`, `subprocess.TimeoutExpired`, 예기치 않은 일반 예외가 발생해도 finally에서
  `owned_pid`를 비우고 COM uninitialize와 mutex release를 계속한다.
- COM/mutex 정리 자체의 예외도 후속 상태 초기화를 막지 않으며 반복 `_release()`는
  추가 Quit/uninitialize/mutex-close 없이 멱등으로 끝난다.
- 실제 통합 테스트는 기존 사용자 PID가 세션 실행 중과 종료 후 모두 존재하는지,
  APP 소유 PID가 context 종료 후 실제 PID 집합에서 사라졌는지를 직접 assertion한다.

### Review RED/GREEN 증거

- RED focused: `11 passed, 4 failed in 0.36s`.
  - ReadOnly=False + Close(False) 실패 후 `session.is_usable`이 잘못 `True`인 상태 재현.
  - taskkill `OSError`, `TimeoutExpired`, `RuntimeError`가 각각 `_release()`를 탈출하는 상태 재현.
- GREEN focused: `15 passed in 0.19s`.
- GREEN 전체 suite: `103 passed, 1 skipped in 0.51s`.
- 강화된 실제 GstarCAD: `1 passed in 58.75s`.

### 강화된 실제 PID 및 원본 보존 증거

- 실행 전 사용자 PID: `10068`
- APP 소유 PID: `33708`
- context 내부: 사용자 PID `10068` 존재, owned PID `33708`로 세 파일 순차 처리
- context 종료 후: owned PID `33708` 부재, 사용자 PID `10068` 존재
- 검증 대상 3개 파일의 SHA-256과 mtime_ns는 위 표와 정확히 동일했다.

## Second Review Follow-up — ReadOnly getter 상태 공백 제거

두 번째 리뷰 후속 구현 커밋은
`6714f1d9bf83895d5f6f67e0bf2774abb45e3216`
(`fix: track GstarCAD documents before COM validation`)이다.

### 수정 내용

- `Documents.Open()` 성공 직후 raw 문서를 `self.document`로 추적한다. `ReadOnly` COM
  property 접근보다 추적이 먼저이므로 getter가 예외를 던져도 열린 문서가 상태 밖에
  남지 않는다.
- `ReadOnly` 접근 예외를 안정 오류 `E203`으로 변환하고 공통 `close_document()` 경계를
  실행한다. 그 Close(False)도 실패하면 세션은 unusable로 표시되고 후속 open은 E201로
  차단된다.
- 실제 통합 테스트는 실행 전 사용자 GstarCAD PID 집합이 비어 있지 않아야 한다.
  사용자 프로세스가 없으면 명확한 assertion 메시지로 실패하므로 PID 보존 검증이
  공집합 때문에 무의미하게 통과할 수 없다.

### Second Review RED/GREEN 증거

- RED focused: `15 passed, 1 failed in 0.44s`.
  - Open 성공 후 ReadOnly getter의 raw `RuntimeError`가 그대로 유출되고 Close(False)에
    도달하지 않는 상태를 재현했다.
- GREEN focused: `16 passed in 0.18s`.
- GREEN 전체 suite: `104 passed, 1 skipped in 0.57s`.
- 실제 GstarCAD: `1 passed in 58.06s`.

### 실제 PID 및 원본 증거

- 실제 테스트 선행 사용자 PID 집합: `{10068}` (비어 있지 않음을 명시적으로 확인)
- APP 소유 PID: `22612`; 세 파일 처리 중 동일 PID 유지, context 종료 후 부재
- 사용자 PID `10068`: context 내부와 종료 후 모두 존재
- 세 파일 SHA-256 및 mtime_ns: 위 표의 값과 모두 동일
