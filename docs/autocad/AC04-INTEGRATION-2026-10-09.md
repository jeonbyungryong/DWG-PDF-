# AC04 — DBMOD 후속 조사·GitHub 통합·배포 판단

## 요청과 범위

2026-10-09 사용자는 최신 GstarCAD 회귀를 해당 PC 사용 불가로 연기했고, 남은 작업(DBMOD 조사,GitHub 반영·MAIN 통합,최종 수용·배포 판단)을 순서대로 진행하도록 요청했다. [PR #3](https://github.com/jeonbyungryong/DWG-PDF-/pull/3)을 이어서 반영한다. 기존 MAIN `30d6f23996035784154f3c306641488bcd2879bf`, 이전 인계 `be85871508149ea74ccdbe6ba1ee4eb81e15cc72`, 검증된 제품 `0c9ca97ce2ea38004193429d5d1d3b2d95002f44`의 이력을 보존한다. 원격 병합·후보 게시 결과의 고정 SHA는 관리 이슈#1에서 확인한다.

## PART 1 — DBMOD 조사

최초 기록은17→21이며 추가4비트는 [Autodesk DBMOD 계약](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-Core/files/GUID-E255E808-2D48-4BDE-A760-FFEA28E5A86F.htm)의 database variable modified다. 최초 변화 시점·변수 이벤트가 기록되지 않아 숫자로 원인을 특정할 수 없다. 사용자는 일체 조작하지 않았다고 확인했다.

[AC03 실제 검증](AC03-READINESS-2026-10-09.md)에 이어 앞선 NOT_RUN인 기존 GUI 기본설정 E211 실패 경로를 추가 조사했다.

- 기존 frozen EXE와 no-args GUI가 전달하던 CLI 인수(PC별 TOML 없음),승인7종으로 재현했다. 새 실제 GUI 버튼 시험이 아닌 동등 CLI 인수의 진단이다.
- 신원이 증명된 사용자 CAD는 읽기만 했다. 별도 소유 CAD의 빈 시험 도면만 저장·선 추가·뷰 변경하여 DBMOD17을 준비했다. 사용자 미저장 메모리와 동일한 복제 상태는 아니다.
- **7건 E211·PDF0·exit1**을 재현했다. 실패 경로에서 시험 도면17→17,사용자21→21,조회13개 변수 동일,양쪽 변수 이벤트0이었다. 메시지 펌프를 명시적으로 수행했다.
- 관찰 장치의 양성 대조로 **소유 시험 도면의 CECOLOR만 BYLAYER→1로 한 번 변경**했다. 시험 도면17→21과 CECOLOR 이벤트를 실제 감지했다. 사용자 도면은 유지됐다. 과거 사용자 도면의 변경 변수가 CECOLOR였다는 증거가 아니다.
- 첫 준비 시도의 SaveAs는 busy HRESULT로 거부돼 중단됐다. 별도 새 시험에서 읽기 전용 준비 안정 확인을 보완했다. 변경 호출은 재시도하지 않았다. 첫 실패·정확한 소유 핸들 정리를 로컬 증거에 보존한다.
- 원본7종 SHA·mtime,사용자 도면과 프로세스를 보존하고 정상 시험의 소유 CAD 종료를 확인했다. 사용자 도면에 Save/Close/SetVariable/SendCommand를 호출하지 않았다.

**확보 가능한 기록과 미실행 실패 경로 조사는 완료했으나 과거 원인은 미확정이다.** 사용자 도면을 저장·초기화하여17로 되돌리지 않았으며 원인 없이 제품 코드를 추가 변경하지 않았다. 재발 시 변경 전부터 변수 값·이벤트·호출 경계를 수집해야 한다. 후속 변화 없음은 과거 원인 해결의 증명이 아니다.

## PART 2 — 검토·시험·통합

독립 읽기 전용 검토는 `c6bb03f→0c9ca97` 수정과 `30d6f239→0c9ca97` 누적 MAIN 제품 변경을 확인했으며 병합을 막는 결함을 발견하지 못했다. 검토자는 CAD나 pytest를 재실행하지 않고 기존 증거와 코드를 검토했다. 읽기 재조회는30초 한도이며 변경 호출·순회 예산을 반복하지 않는다. GstarCAD 기본 세션 훅은 무동작,플롯 callback 기본값은None,GUI TOML은 AutoCAD에서만 선택한다.

경미한 지적인 readiness.py 끝의 빈 줄만 정리했다. 검증된 원본과 새 파일을 같은 filename으로 compile한 marshal 바이트 일치를 확인한다. 기존 인계 문서는 병합으로 보존했다. 최신 오프라인 회귀와 전체 누적 diff-check를 확인한 뒤 원격 반영한다. 후속 게시 결과는 관리 이슈의 실제 SHA/종료코드를 따른다.

실제 AutoCAD 증거는 소스3시험(정상88개+예상 불량1개),일반 frozen CLI1+43,실제GUI7+7·취소4,golden86개·PDF·144dpi비교,사용자 상태1257+1206표본이다. 오프라인964PASS/13SKIP과 별도 AutoCAD3PASS를 합쳐 단일 전체 PASS로 주장하지 않는다. symlink4개는 앞선 관리자4PASS가 있으며 최신 전체 실행에서는 권한 SKIP이다. GstarCAD6개는 사용자 연기다.

## PART 3 — 수용·배포 판단

| 대상 | 판단 |
|---|---|
| 현재 PC AutoCAD 검증 범위 |통과|
| 소스 GitHub/MAIN 통합 |사용자 요청·독립 검토에 따라 진행 가능|
| 검증용 prerelease |검증 범위·미확정·보류를 명시하여 게시 가능|
| 과거 DBMOD17→21 원인 |UNRESOLVED / 사용자 조작 제외|
| 최신 GstarCAD 실기·공용picker |DEFERRED_USER / 해당 PC 사용 불가|
| 정식 stable Release·공식지원 |HOLD / 전체 수용 완료로 표시하지 않음|

새 검증 후보는 `AC03-normal-validation-2026-10-09.zip`과 runtime checksum CSV다. ZIP SHA256 `DB3662FBDA6A7748FB196403FC192E507364AA6AE663E1E7E31BC602F6107A90`,EXE SHA256 `56579D7B26799596A8A5791707EF126FE15C2972383EC9FDCBDC5880859BBA11`. 제품 의미는 검증된0c9ca97 기준이며 후속 문서·공백 정리와 구분한다. 기존 승인13종 기준DWG만 내장한다. 고객 원본/출력·개인경로/PID·TOML·private 증거 ZIP은 게시하지 않는다. GitHub 재다운로드 해시와 새 복구 bundle을 확인한다. 기존 후보와 백업은 덮어쓰지 않는다.

원래 PC 사용 가능 시 새 고정 MAIN·후보로 GstarCAD6개실기,CLI43,GUI각7·취소·보호·PDF 감사를 수행한다. 사용자 연기 결정을 유지한다. 정식 배포는 남은 항목의 수용 판단 이후다. 이번 소스 통합은 미확정 원인 해결이나 보류된 실기 성공을 뜻하지 않는다.

| PART | 권장 모델 | 추론 강도 |
|---|---|---|
| 조사·게시·인계 |GPT-6.1 Sol|High|
| 독립 검토·최종 판정 |GPT-6 Astra|Xhigh|

권장 설정은 실제 대화 모델을 전환했다는 기록이 아니다.
