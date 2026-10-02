# Task 4 Report — Owned GstarCAD Session and Filtered Drawing Inspection

## 결론

Task 4 구현과 테스트를 완료했다. 구현 커밋은
`66edbe63968bc5574a403ca53b1c9a187054ce34` (`feat: add owned filtered GstarCAD inspection`)이다.

GstarCAD 2026 실제 COM 스모크 테스트에서 새 프로세스 소유권 증명, 원본 DWG 읽기 전용 열기,
서버 측 필터 SelectionSet, 필터 결과 유형 제한, 중첩 블록을 포함한 Scale 후보 탐지, 정상 종료,
원본 SHA-256 보존을 확인했다. 실행 전부터 존재한 사용자 프로세스 PID 10068에는 연결하거나 종료하지 않았다.

## 주요 결정 및 확인된 COM 계약

- 파일마다 `DispatchEx`로 새 GstarCAD 인스턴스를 만들고, `Application.HWND`의 PID가 실행 전에는 없고 실행 후에는 존재하며 새 PID 집합이 정확히 하나인지 확인한다.
- 소유권 증명 전에는 `Quit` 또는 강제 종료를 호출하지 않는다. 강제 종료 대상은 증명된 PID만 가능하다.
- named mutex는 initial-owner로 획득하며, COM 초기화 성공 여부를 별도로 추적한다. 부분 `__enter__` 실패와 반복 `_release()`를 안전하게 처리한다.
- `open_readonly_copy()`는 존재하는 `.dwg`만 허용하고, COM 반환 문서의 `ReadOnly`도 다시 검증한다. 세션당 한 파일만 허용한다.
- 초기 수집은 `SelectionSet.Select`의 DXF group 0 필터만 사용한다. `ModelSpace`와 `Blocks` 전체 열거 경로는 없다.
- 실제 GstarCAD 계약 조사 결과:
  - FilterType: `VT_ARRAY | VT_I2`
  - FilterData: `VT_ARRAY | VT_VARIANT`
  - `acSelectionSetAll`의 미사용 Point1/Point2: `pythoncom.Empty`
  - crossing Point1/Point2: `VT_ARRAY | VT_R8`
  - `None`은 `E_INVALIDARG`, `pythoncom.Missing`은 후속 필터를 무시하므로 사용하지 않는다.
- 필터로 도달한 INSERT에서만 `Blocks.Item(name)`을 호출한다. 익명/동적 블록은 실제 정의명인 `Name`을 사용하며 `EffectiveName`은 탐색 키로 사용하지 않는다.
- 중첩 탐색에는 cycle guard와 블록/엔티티 상한을 적용한다. TEXT, MTEXT, attribute definition, attached attribute value, nested/anonymous block을 처리한다.
- 좌표와 변환은 모두 유한값이어야 한다. uniform similarity transform만 허용하고 non-uniform scale, reflection, shear, singular transform은 `E303`으로 거부한다.
- Scale 라벨과 비율값은 전역 방향을 가정하지 않고 유클리드 최근접으로 연결한다. 0/90/180/270도 전체 프레임 회전에서도 동일하게 동작하며 최종 모호성은 후속 기하 검증 책임이다.
- 대상 DWG의 저장 Plot Window는 읽거나 후보/출력 입력으로 사용하지 않는다.

## 변경 파일

- `src/dwg_to_pdf/gstarcad/__init__.py`
- `src/dwg_to_pdf/gstarcad/discovery.py`
- `src/dwg_to_pdf/gstarcad/com_session.py`
- `src/dwg_to_pdf/gstarcad/document.py`
- `src/dwg_to_pdf/gstarcad/media_resolver.py`
- `src/dwg_to_pdf/gstarcad/template_detector.py`
- `tests/unit/test_bounded_detector.py`
- `tests/unit/test_gstarcad_contracts.py`
- `tests/integration/test_com_contract.py`

## 테스트 증거

번들 Python:
`C:\Users\dknbtech\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

- TDD RED: 신규 패키지 부재로 unit collection 실패를 확인했다.
- 실제 COM 회귀 RED: `None` point가 `E_INVALIDARG`를 발생시키고, `Missing`이 필터를 무시하며, tuple crossing point가 `E_INVALIDARG`를 발생시키는 것을 좁은 probe matrix로 재현했다.
- TDD GREEN: Task 4 단위 테스트 및 기존 Tasks 1–3 단위 테스트 91개 통과 후 보강 테스트까지 통과했다.
- 최종 전체 suite: `94 passed, 1 skipped in 0.56s`. skip 1건은 환경변수 없을 때 의도적으로 비활성화되는 opt-in 실제 COM 테스트다.
- 최종 실제 COM: `1 passed in 22.37s`.
- 실제 COM 테스트는 필터 결과가 `TEXT/MTEXT/ATTRIB/INSERT` 범위인지와 `detect_scale_candidates()`가 실제 후보를 반환하는지도 확인한다.
- `git diff --check`: 오류 없음.
- 금지 패턴 정적 검사: `ModelSpace`/`Blocks` 전체 열거 및 저장 Plot Window 참조 0건.

## 원본 보존 검증

대상:
`D:\2026 PROJECT\APP 개발\DWG TO PDF 자동변환 프로그램\학습용 템플릿\윈도우 영역 학습용\TEMPLETE_1대1.DWG`

- 실행 전 SHA-256: `15F65A792E68FD3A079F8104DDCC2A19DB001CF200CE309F6D3BC8D8753EFEF0`
- 실제 COM 실행 후 SHA-256: `15F65A792E68FD3A079F8104DDCC2A19DB001CF200CE309F6D3BC8D8753EFEF0`
- 최종 검증 SHA-256: `15F65A792E68FD3A079F8104DDCC2A19DB001CF200CE309F6D3BC8D8753EFEF0`

## 리스크 및 한계

- 실제 통합 검증 범위는 이 PC의 GstarCAD 2026 ProgID와 지정된 1:1 학습용 DWG다. 다른 GstarCAD 버전/언어팩은 별도 opt-in 검증이 필요하다.
- PID 탐지는 실행 파일명이 `gcad.exe`이고 Application이 유효한 `HWND`를 제공한다는 설치 계약에 의존하며, 어느 조건이든 불명확하면 폐쇄적으로 실패한다.
- plot device/media/style 실제 설치 조합은 이번 Task 4 스모크의 범위가 아니며 `media_resolver`는 fake-COM 단위 계약으로 검증했다. 실제 출력 단계에서 별도 통합 검증이 필요하다.
- reflection과 non-uniform nested scaling은 잘못된 월드 좌표를 만들지 않도록 지원하지 않고 명시적으로 거부한다.
- COM 정리 중 정상 종료가 제한 시간 내 완료되지 않을 때만 소유권이 증명된 PID에 한해 `taskkill` fallback을 사용한다.
