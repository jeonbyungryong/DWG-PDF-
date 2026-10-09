# AC03 — 현재 PC 최종 검증 / 2026-10-09

## 결론

승인한 AutoCAD GUI TOML 선택과 읽기 조회 오류 수정을 완료했다. 현재 PC의 수정 소스와 새 일반 frozen 후보는 아래 수용 시험을 통과했다. 과거 사용자 도면 DBMOD17→21의 발생 변수·시점은 여전히 미확정이며, 사용자는 일체 조작하지 않았다. 이번 수정이 과거 DBMOD의 원인을 해결했다고 주장하지 않는다. GstarCAD 실기 회귀는 원래 PC에서 필요하다.

기준 제품 SHA `c6bb03f8326aa854b753ba8631ec0d8ed11264b8`, 로컬 격리 브랜치 `codex/ac02-autocad-readiness-fix-20261009`. 기존 배포 runtime·MAIN·정식 Release는 변경하지 않았다. 원래 frozen 인계 문서의 후속 최종 배포 게이트를 유지한다.

## 수정과 실패 원인

1. **E410:** 플롯 뒤 Application metadata GetIDsOfNames가 `RPC_E_CALL_REJECTED` (`0x80010001`)로 거부됐고 pywin32가 `AttributeError: Open.Application`으로 전달했다. 기존 준비 상태 함수는 com_error만 처리해 BACKGROUNDPLOT 복원 호출 전에 중단됐다. 읽기 전용 준비 조회를 기존 대기 루프로 처리한다.
2. **E303:** E410/GUI 수정만 포함한 일반 후보 V1의43건에서42성공/1실패가 나왔다. 별도 두 도면 재현에서 ObjectName GetIDsOfNames의 같은 HRESULT가 `AttributeError: Item.ObjectName`으로 전달되어 도곽 구조 조회가 중단됨을 확인했다. AutoCADDocument의 읽기 조회에서 직접 또는 원인 체인에 포함된 AttributeError를 처리한다. 순회·entity 방문 예산은 반복하지 않는다.
3. **GUI E211:** 기존 GUI는 PC별 TOML을 전달하지 않아 A4 후보6개의 모호성으로7건 모두 실패했다. 사용자가 승인한 설계에 따라 AutoCAD 설치 선택 후 TOML을 한 번 선택하고 기존 CLI `--config`로 전달한다. 취소하면 변환 없이 종료한다. 잘못된 TOML은 기존 CLI 검증에서 차단한다. GstarCAD는 설정 선택을 추가하지 않는다.

30초 한도·0.05초 조회 간격, Documents.Open/Close·PlotToFile·SetVariable 변경 호출 정책, 보안 설정,13종 템플릿, 승인 입력43종, matching 기준, requirements.lock와 제품 packaging spec을 유지했다. 실제 속성이 영구적으로 없으면 기존 한도에서 실패한다.

## 검증 결과

| 항목 | 실제 결과 |
|---|---|
| 최신 전체 pytest |964 PASS /13 SKIP,44.98초,exit0|
| 읽기 준비 조회 새 회귀4개 |수정 전4 FAIL → 수정 후 PASS|
| entity metadata 새 회귀6개 |수정 전6 FAIL → 수정 후 PASS|
| GUI 설정·취소 새 회귀7개 |수정 전7 FAIL → 수정 후 PASS|
| 관련 단위 시험 최종 묶음 |72 PASS|
| 수정 소스 AutoCAD 실기 |3 PASS,632.73초,exit0|
| 소스 시험 실제 범위 |대표1 + OFF43 + ON43 + 불량헤더1/후속 정상1: 정상88건,예상 실패1건|
| 새 일반 frozen CLI |대표1/1 + 승인43/43,각exit0|
| 새 일반 frozen 실제GUI |파일 다중선택7/7 + 폴더7/7,각exit0·완료 안내 확인|
| 실제GUI 취소 |파일·입력폴더·출력폴더·TOML의4경로,각exit0·PDF0·소유CAD0|
| PDF 구조·렌더 |소스86개·CLI44개·GUI14개,단일 비공백 A4가로297×210mm·Rotate0·비암호화|
| golden 결정 감사 |OFF/ON86건의입력SHA·축척·회전·도곽window일치|
|144dpi 픽셀 비교 |OFF/ON43쌍,새frozen/소스43쌍,GUI/CLI14쌍 동일|
| 원본·설치PC3 |SHA256·mtime 보존|
| 사용자 CAD |원래 프로세스·도면·미저장 상태 보존;후속DBMOD21→21|
| 사용자 상태 관찰 |소스1257표본,GUI1206표본;각 이벤트0,명시적 메시지펌프|
| 소유 CAD 종료 |각 변환 후 사용자 CAD만 유지|
| 배포 파일 |기존260개·새259개체크섬일치;새ZIP CRC·모든파일해시검증|

13SKIP은 관리자 권한 필요symlink4개와 CAD opt-in9개이다. AutoCAD3개는 별도 실기에서 전부 수행했다. 나머지 GstarCAD6개는 해당 프로그램이 없는 현재 PC에서 수행할 수 없다. symlink4개는 앞선 관리자 실행의4PASS/0SKIP 증거가 있으며 이번 변경 파일과 무관한 원본보호 경로다. 수정 후 관리자 재실행 결과와 합쳐 단일968PASS라고 주장하지 않는다.

ON 시험은 신뢰 제한에 따른 native E303 fallback을 포함한다. LISP가 native 경로로 성공했다고 주장하지 않는다. 잔존 색상은 CTB-only 정책상 허용하고, 이전에 수용한 표제란 문자 중첩은 실패로 집계하지 않는다. 픽셀 일치는144dpi 렌더 기준이며 모든 프린터의 물리 출력 증명은 아니다.

사용자 도면에 Save/Close/SetVariable/SendCommand를 호출하지 않았다. 이벤트0·상태 표본은 이번 구간 관찰 결과이며 과거 DBMOD 변경 시점·원인을 소급 증명하지 않는다. 기존 미저장 관찰 사본의17→17 결과도 기존 사용자 메모리와 동일한 복제 상태의 증명은 아니다.

## 새 후보와 복구

- 새 검증 ZIP: `AC03-normal-validation-2026-10-09.zip`,42,077,189바이트.
- ZIP SHA256: `DB3662FBDA6A7748FB196403FC192E507364AA6AE663E1E7E31BC602F6107A90`.
- EXE SHA256: `56579D7B26799596A8A5791707EF126FE15C2972383EC9FDCBDC5880859BBA11`.
- 일반 제품 spec으로 만든 로컬 후보이며 진단 계측 EXE와 구분한다. 현재는 미게시 후보다.
- 빌드 환경의 선택적 cryptography는 기존50.0.1에서 번들 basePython의50.0.2로 달라졌고, 사용하지 않는 win32ui.pyd는 포함하지 않는다. lock과 제품 spec 변경은 없다. 기존260개와 새259개의 파일 수 차이는 manifest에 기록했다.
- 코드·테스트·인계 문서는 격리 Git 브랜치로 보존하고, 해당 이력의 별도 Git bundle 및 새 실행 파일·로컬 원시 증거의 private ZIP을 만든다. 압축 CRC·개별 SHA와 git bundle verify를 확인한다. 기존 백업은 덮어쓰지 않는다.
- 복구는 기존 정상 runtime 또는 `rollback-main-before-ac02-20261007`을 새 폴더에서 사용한다. 이번 소스 bundle을 새 폴더에 clone하고 위 브랜치를 checkout하면 수정 코드를 복원할 수 있다. 원본 checkout을 reset/clean하지 않는다.

## 원래 PC 다음 작업

1. 이 변경 브랜치의 고정 commit과 새 검증 ZIP을 별도 폴더에서 준비하고 SHA/self-check를 확인한다. 현재 PC의 로컬TOML·개인PC3경로는 복사하지 않는다.
2. GstarCAD용 현지 설정을 확인한 뒤 기존6개실기,승인43종CLI,GUI파일/폴더각7종,취소 경로를 실행한다. 변경된 공용 picker의 GstarCAD 경로도 확인한다.
3. 원본·사용자CAD·소유CAD종료·PDF/golden결정/선가중치를 이전 GstarCAD 증거와 대조한다. AutoCAD metadata수정 때문에 보안·timeout·Open/Close정책을 바꾸지 않는다.
4. 과거DBMOD원인 미확정과 새시험성공을 구분해 수용 판단한다. 사용자 최종 MAIN/정식 Release 승인 전 기존 설치본 교체·MAIN 병합·정식배포를 하지 않는다.

## PART 권장 모델

| PART | 모델 | 추론 강도 |
|---|---|---|
| 원인 재현·수정·회귀·GUI 실기 |GPT-6.1 Sol|High|
| 최종 독립 검토·원래PC 회귀 결과 판정 |GPT-6 Astra|Xhigh|

위 표는 사용자 선택을 위한 권장 설정이며 실제 대화 모델을 전환했다는 기록은 아니다. 원시 로그·사용자 경로·프로세스 식별자·로컬TOML은 private 로컬 증거에만 보존한다. 기존E211·E410·V1 E303 실패 기록도 보존한다.
