# 다른 PC의 Codex 검증 시작 안내 - GUI-01

## 가져올 자료

- 소스: `https://github.com/jeonbyungryong/DWG-PDF-`의 `main`. 작업 전 `git fetch origin` 후 현재 HEAD와 origin/main을 확인한다. 기존 dirty 변경을 덮어쓰지 않는다.
- 검증 키트: [GUI-01 검증용 사전 배포](https://github.com/jeonbyungryong/DWG-PDF-/releases/tag/windows-gui1-pc-validation-20261007)의 `dwg-to-pdf-pc-validation-gui1-20261007.zip`과 `.sha256.txt`.
- ZIP SHA-256: `4DF56A427348BFE37D216444C72FF5FB8E4EA09A4956877E9D9C9C3B7306894B`.
- EXE SHA-256: `09883ED375E8EFB43700B5B037BF5D012976666B5CD16AF188B86CCEC44DD85E`.

GitHub Download ZIP은 소스이며 실행 키트가 아니다. 검증 ZIP을 새 로컬 폴더에 전체 압축 해제하고 `_internal`을 유지한다. 키트 루트의 README-KO/GUI-01 인계를 먼저 읽는다. Python은 frozen EXE 실행에 필요하지 않다.

## Codex에 전달할 요청

아래를 다른 PC의 Codex에 전달한다. 사용자 승인 없이 시스템 설치나 보안 정책 변경, 사용자 CAD 종료, 기존 파일 덮어쓰기, 원격 게시를 하지 않는다.

> DWG-PDF- 저장소의 AGENTS.md, docs/autocad/README.md, OTHER-PC-CODEX-2026-10-07.md, PC-VALIDATION-KIT-2026-10-07.md와 관리 이슈 #1의 최신 인계를 읽고 GUI-01 타PC 검증을 진행해줘. 먼저 저장소 remote/HEAD/dirty 상태와 Windows/PowerShell/CAD 제품·버전을 확인해줘. 릴리스 windows-gui1-pc-validation-20261007의 검증 ZIP을 다운로드해 SHA-256을 확인하고 새 폴더에 전체 압축 해제해줘. 패키지 파일312개와 checksums.csv의311개 항목을 크기·해시로 대조하고, 승인 표본43개와 manifest43개를 검증해줘. verify_bundle.ps1과 --self-check/--list-cad를 실행한 뒤 GstarCAD 2026이 일치하면 새 출력 폴더에서43종을 변환해줘. 출력 개수·페이지·비공백·A4가로·축척·회전·출력영역을 가능한 근거로 대조하고 원본 해시/수정시간을 전후 확인해줘. GUI 파일/입력폴더/출력폴더 선택 창, 주소 복사·붙여넣기,각 단계 취소 및 두 입력 방식의 변환을 명령행 시험과 별도로 확인해줘. 사용자 CAD가 열려 있으면 PID/생성시각/창과 열린 도면 상태를 보존하고 APP이 만든 별도 CAD만 종료되는지 확인해줘. 사용자 CAD가 없으면 공존 시험 환경 준비만 요청하고 임의 사용자 도면을 조작하지 마. monochrome.ctb로 바뀌지 않는 색상은 허용하며 RGB 보정은 하지 마. 보안/신뢰/실행 정책을 낮추지 말고 차단되면 기록해줘. AutoCAD가 없으면 최신 AutoCAD 실기는 NOT_RUN으로 남겨줘. 공개 보고에는 비식별 PC별명,소스·EXE·ZIP SHA,명령과 종료코드,성공/실패 개수,시간,SKIP/NOT_RUN,보호 및 육안 확인 결과,실패 원인과 다음 행동을 구분해줘. 고객DWG/PDF/개인경로/PID/원시로그/라이선스/토큰을 공개하지 마. 코드 수정은 실패 재현 후 별도 승인 범위로 검토하고 검증만으로 공식 지원·릴리스 완료를 선언하지 마. 결과는 먼저 로컬 보고서로 작성해 사용자에게 보여줘.

## 인계와 한계

기존 MAIN은 백업 브랜치 `codex/backup-main-before-gui1-20261007`의 `c951b818035ac6a06dce7b9a464cadb050bdc808`에 보존한다. 현재 PC GUI와 업무7개 공존 실기 근거는 [GUI-01](GUI-01-HANDOFF-2026-10-07.md), [공존 기록](GUI-01-COEXIST-2026-10-07.md), [키트 갱신](GUI-01-PC-KIT-2026-10-07.md)을 따른다.

이번 게시 목적은 다른 PC 검증 준비다. 다른 PC 실기,최신 AutoCAD 검증 및 공식 지원·배포 승인은 아직 완료가 아니다. 사전 배포의 태그 커밋과 frozen 제품 소스 커밋은 문서 후속 커밋 때문에 다르며 BUILD-IDENTITY의 제품 식별을 우선한다. 기존 릴리스·백업·고객 파일은 삭제하지 않는다.
