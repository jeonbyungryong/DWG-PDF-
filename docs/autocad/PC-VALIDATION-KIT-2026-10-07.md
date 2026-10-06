# 다른 PC용 검증 패키지 — 2026-10-07

## 목적과 제한

GstarCAD 2026이 설치된 다른 Windows PC에서 Python 개발 환경 없이 검증용 EXE를 시험한다. 패키지 준비·현재 PC 실행은 다른 PC 수용 완료가 아니다. AutoCAD는 별도 실험적 검증 범위이며 이 절차의 대상이 아니다. GUI 시험은 사용자 요청으로 제외했으므로 아래 명령행 절차를 사용한다.

압축을 새 폴더에 풀고 전체 폴더를 유지한다. EXE만 복사하거나 `_internal`/기준 도면/설정을 삭제하지 않는다. 고객 도면·개인 로그·라이선스키는 포함하지 않는다.

## 구성

- `dwg-to-pdf-validation/`: 기존 검증용 runtime 전체. 제품 SHA `2f849b6`.
- `samples/`: 공개 승인13종 및 기존 승인 파생30종, 총43개.
- `inputs-manifest.json`: 승인 표본의 해시와 기대 판정값.
- `verify_bundle.ps1`: 기존 runtime 검증 도구, Python 불필요.
- `README-KO.md`, `GC-02-HANDOFF.md`: 최신 절차·실측·미검증 범위.
- `checksums.csv`: 패키지 각 파일의 경로·크기·SHA-256(목록 자체 제외).

runtime 내 과거 README/시험 보고서는 빌드 당시 자료다. 최신 범위는 외부 GC-02 인계를 따른다. 최신 테스트 하네스 수정은 소스 저장소 변경이며 EXE의 변환 로직을 바꾸지 않는다.

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

1. 정상 표본43개 모두 성공, PDF43개를 확인한다. 일부 실패 시 원본/로그/생성 출력 보존 후 해당 사유를 기록한다.
2. PDF의 A4 가로·도곽·방향·문자·선굵기·빈 페이지 여부를 확인한다. 잔존 색상은 현재 CTB-only 정책에 따라 허용한다.
3. 입력 표본 SHA-256을 manifest와 대조하고 실행 전후 원본의 해시·수정시간을 확인한다. 예상값 감사는 manifest 기반이며 새 양식 수용 시험이 아니다.
4. 기존 사용자 CAD가 살아 있고 APP이 새로 연 CAD만 종료됐는지 확인한다. CAD 이름으로 모든 프로세스를 종료하지 않는다.
5. 별도 승인된 실패 표본이 있으면 정상 도면과 함께 시험해 오류 보고와 다음 정상 파일 계속 처리를 확인한다. 실제 도면을 임의 손상시켜 실패 표본을 만들지 않는다. GUI 보고 창은 이번 절차에서 요구하지 않는다.
6. PC 별명, Windows/PowerShell/CAD 제품·버전, Python 미설치 여부, runtime SHA,43개 결과,총 시간,보호 확인,육안 확인,실패 원인을 기록한다. 미검증은 NOT_RUN으로 남긴다. 개인경로·PID·고객파일·개인 원시로그는 공개 이슈에 올리지 않는다.

별도 PC 실행과 사용자 수용 결과를 받은 뒤 최신 AutoCAD 실기 및 MAIN/공식배포를 판단한다. 이번 패키지는 검증 전용이며 자동 업데이트·원격 보고 기능이 없다.
