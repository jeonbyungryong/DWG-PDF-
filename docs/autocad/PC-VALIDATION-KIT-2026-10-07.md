# 다른 PC용 검증 패키지 — 2026-10-07

## 목적과 제한

GstarCAD 2026이 설치된 다른 Windows PC에서 Python 개발 환경 없이 검증용 EXE를 시험한다. 패키지 준비·현재 PC 실행은 다른 PC 수용 완료가 아니다. AutoCAD는 별도 실험적 검증 범위이며 이 절차의 대상이 아니다. 최신 GUI-01 키트에서는 아래 명령행43종 시험과 별도 GUI 선택 창 확인을 구분한다.

최신 파일은 `dwg-to-pdf-pc-validation-gui1-20261007.zip`이다. 같은 날짜의 이전 `dwg-to-pdf-pc-validation-20261007.zip`은 GC-02 당시 키트로 보존하며 최신 GUI 키트가 아니다.

압축을 새 폴더에 풀고 전체 폴더를 유지한다. EXE만 복사하거나 `_internal`/기준 도면/설정을 삭제하지 않는다. 고객 도면·개인 로그·라이선스키는 포함하지 않는다.

## 구성

- `dwg-to-pdf-validation/`: GUI-01 검증용 runtime 전체. 제품 소스 SHA `2918308cc07341615484d19868d051e4c77ebc03`, EXE SHA256 `09883ED375E8EFB43700B5B037BF5D012976666B5CD16AF188B86CCEC44DD85E`.
- `samples/`: 공개 승인13종 및 기존 승인 파생30종, 총43개.
- `inputs-manifest.json`: 승인 표본의 해시와 기대 판정값.
- `verify_bundle.ps1`: 기존 runtime 검증 도구, Python 불필요.
- `README-KO.md`, `GC-02-HANDOFF.md`, `GUI-01-HANDOFF.md`, `GUI-01-COEXIST.md`: 최신 절차·실측·미검증 범위.
- `checksums.csv`: 패키지 각 파일의 경로·크기·SHA-256(목록 자체 제외).

runtime 내 과거 README/시험 보고서는 빌드 당시 자료다. 최신 범위는 키트 루트의 GC-02/GUI-01/공존 인계를 따른다. 원래 저장소 상대 링크는 키트 안에서 열리지 않을 수 있으므로 루트에 복사한 인계 문서를 읽는다. 제품 코드를 재빌드하지 않고 현재 PC GUI 및 공존 검증을 통과한 동일 runtime을 패키징한다.

## 실행 — 압축 해제 폴더에서 Windows PowerShell 5.1

GstarCAD에서 저장되지 않은 작업을 먼저 보존하고, 사용자 CAD1개를 열어 공존 보호를 확인한다. 시스템 보안·신뢰·실행 정책을 낮추지 않는다. 실행이 정책으로 차단되면 오류를 기록하고 중단한다.

```powershell
$ErrorActionPreference = 'Stop'
$root = (Get-Location).Path
$bundle = Join-Path $root 'dwg-to-pdf-validation'
$exe = Join-Path $bundle 'dwg-to-pdf.exe'
& $exe --self-check
if ($LASTEXITCODE -ne 0) { throw 'Runtime self-check failed' }
& $exe --list-cad
if ($LASTEXITCODE -ne 0) { throw 'CAD discovery failed' }
```

`RUNTIME_SELF_CHECK_OK`와 실제 GstarCAD 등록 정보를 확인한다. 설치 제품/버전이 다르거나 탐지가 실패하면 추정 ProgID·다른 CAD의 PC3로 계속하지 않는다. 결과를 인계하고 설정 검토 후 재시험한다.

```powershell
$checks = Join-Path $root ('runtime-check-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.csv')
& (Join-Path $root 'verify_bundle.ps1') -BundlePath $bundle -ChecksumsPath $checks
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Runtime bundle validation failed' }
$out = Join-Path $root ('results-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $out -ErrorAction Stop | Out-Null
$inputs = Join-Path $root 'samples'
& $exe $inputs --output $out --cad gstarcad --conflict copy
$conversionExit = $LASTEXITCODE
if ($conversionExit -ne 0) { throw "Conversion failed; keep outputs and errors. Exit=$conversionExit" }
```

PowerShell 네이티브 실행의 종료코드를 바로 확인한다. 경로는 변수와 개별 인수로 전달하며 문자열 명령을 조립하지 않는다. `VALIDATION_BUNDLE_OK`만으로 CAD 변환·타PC 수용 PASS를 주장하지 않는다.

## 수용 확인과 인계

명령행 실행 전 `inputs-manifest.json`의 `cases`43개와 `samples`의 DWG43개가 정확히 대응하며 각 SHA-256이 일치하는지 확인한다. `checksums.csv`는 패키지 기준 파일 해시 목록이다. `verify_bundle.ps1`은 runtime 점검 후 새 해시 목록을 생성하는 도구이며 패키지 전체 기존 해시 목록과 자동 비교하는 도구가 아니다.

1. 정상 표본43개 모두 성공, PDF43개를 확인한다. 일부 실패 시 원본/로그/생성 출력 보존 후 해당 사유를 기록한다.
2. PDF의 A4 가로·도곽·방향·문자·선굵기·빈 페이지 여부를 확인한다. 잔존 색상은 현재 CTB-only 정책에 따라 허용한다.
3. 입력 표본 SHA-256을 manifest와 대조하고 실행 전후 원본의 해시·수정시간을 확인한다. 예상값 감사는 manifest 기반이며 새 양식 수용 시험이 아니다.
4. 기존 사용자 CAD가 살아 있고 APP이 새로 연 CAD만 종료됐는지 확인한다. CAD 이름으로 모든 프로세스를 종료하지 않는다.
5. 별도 승인된 실패 표본이 있으면 정상 도면과 함께 시험해 오류 보고와 다음 정상 파일 계속 처리를 확인한다. 실제 도면을 임의 손상시켜 실패 표본을 만들지 않는다.
6. PC 별명, Windows/PowerShell/CAD 제품·버전, Python 미설치 여부, runtime SHA,43개 결과,총 시간,보호 확인,육안 확인,실패 원인을 기록한다. 미검증은 NOT_RUN으로 남긴다. 개인경로·PID·고객파일·개인 원시로그는 공개 이슈에 올리지 않는다.

## 다른 PC GUI 확인

EXE를 더블클릭하여 파일 선택·입력 폴더 선택·출력 폴더 선택이 모두 탐색기형으로 표시되는지, 주소 복사/붙여넣기가 되는지 확인한다. 각 선택 단계의 취소는 변환이나 CAD 기동 없이 종료돼야 한다. 파일 다중 선택과 폴더 입력은 새 출력 폴더로 각각 대표 표본을 변환해 완료 요약과 PDF를 확인한다. 이 확인은 명령행43종 PASS로 대체하지 않는다. 고객 파일·주소·개인 화면을 공개 이슈에 첨부하지 않는다.

현재 PC에서는 사용자 CAD가 열린 상태의 업무7개 변환과 사용자 CAD 보존도 확인했으나 다른 PC에서 같은 결과를 보장하지 않는다. 별도 PC 실행과 사용자 수용 결과를 받은 뒤 최신 AutoCAD 실기 및 GitHub/공식배포를 판단한다. 로컬 MAIN 통합은 완료됐지만 이번 패키지는 검증 전용이며 자동 업데이트·원격 보고 기능이 없다.
