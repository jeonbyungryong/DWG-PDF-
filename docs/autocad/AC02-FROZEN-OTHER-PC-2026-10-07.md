# AC02 새 frozen 후보 — AutoCAD PC 최종 검증 인계

상태: HANDOFF_READY / 현재 PC GstarCAD 검증 완료 / 받는 PC AutoCAD 실기 NOT_RUN / 공식지원 및 MAIN 병합 미승인.

## 사용할 후보

- 전달 브랜치: `codex/ac02-gstar-frozen-validation`.
- 제품 소스 기준: `c6bb03f8326aa854b753ba8631ec0d8ed11264b8`. 문서 후속 커밋과 구분한다.
- [검증용 사전 배포](https://github.com/jeonbyungryong/DWG-PDF-/releases/tag/windows-ac02-pc-validation-20261007): `dwg-to-pdf-validation.zip` 및 `dwg-to-pdf-validation-checksums.csv`.
- ZIP SHA256: `AEEAAD610D5887071A06E011403E7AA26E9E2E23CF5CBA72E1B25837207C9BC2` (43,352,730바이트).
- EXE SHA256: `018A4759F3AEF130800D337E6F15FB3508A3811D1483E3CF4CEA6F75BAC1FB8E`.
- [현재 PC 새 EXE 검증 결과](AC02-PC-A-FROZEN-VALIDATION-2026-10-07.md): 947 PASS/4 SKIP/9 CAD deselect, 새 EXE43/43 성공, 실제GUI 파일/폴더 각7개 성공, 원본·사용자 CAD 보호.

ZIP은 runtime260개 파일과 부모 폴더의 체크섬CSV를 포함한다. 승인43종 표본은 브랜치의 `tools/regression/gstarcad/inputs/`와 manifest를 사용한다. Python은 frozen 실행에 필요 없으며, 소스 테스트·PDF 감사에는 별도 개발 환경이 필요하다. 이전 GUI-01 ZIP로 이번 AC02 검증을 대신하지 않는다. 앱은 LLM 없이 동작한다.

## 기존 환경 보호와 준비

기존 설치본과 업무 CAD를 보존한다. 기존 정상 runtime과 `rollback-main-before-ac02-20261007` 복구 ref를 별도 폴더에 확보한다. 원격 MAIN은 여전히 기존 버전이며 위 전달 브랜치를 새 폴더로 가져온다. dirty checkout을 reset/clean/stash하거나 보안·실행 정책을 낮추지 않는다.

ZIP과 체크섬 CSV를 다운로드한 후 ZIP 해시가 위 값과 일치하는지 확인하고 새 빈 폴더에 압축 해제한다. EXE만 복사하지 않는다. GitHub 자동 소스 ZIP과 release asset runtime ZIP은 서로 다른 파일이다.

새 runtime 폴더에서 Windows PowerShell5.1 이상으로 다음 읽기 전용 점검을 실행한다. CSV는 runtime의 부모 폴더에 둔다.

```powershell
$ErrorActionPreference = 'Stop'
$root = (Get-Location).Path
$exe = Join-Path $root 'dwg-to-pdf.exe'
$csv = Join-Path (Split-Path $root -Parent) 'dwg-to-pdf-validation-checksums.csv'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'EXE missing' }
if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ne '018A4759F3AEF130800D337E6F15FB3508A3811D1483E3CF4CEA6F75BAC1FB8E') { throw 'Wrong AC02 EXE' }
$rows = @(Import-Csv -LiteralPath $csv -Encoding UTF8)
if ($rows.Count -eq 0) { throw 'Empty checksum manifest' }
$prefix = $root.TrimEnd('\') + '\'
foreach ($row in $rows) {
    if ([IO.Path]::IsPathRooted($row.Path)) { throw 'Absolute checksum path' }
    $path = [IO.Path]::GetFullPath((Join-Path $root $row.Path))
    if (-not $path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Checksum path outside runtime' }
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Runtime file missing' }
    if ((Get-Item -LiteralPath $path).Length -ne [long]$row.Bytes) { throw 'Runtime size mismatch' }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $row.SHA256) { throw 'Runtime hash mismatch' }
}
& $exe --self-check
$code = $LASTEXITCODE
if ($code -ne 0) { throw 'Runtime self-check failed' }
& $exe --list-cad
$code = $LASTEXITCODE
if ($code -ne 0) { throw 'CAD discovery failed' }
```

게시 전 위 블록을 현재 PC의 Windows PowerShell5.1에서 실제 runtime 경로로 실행해 해시/self-check/discovery 통과를 확인했다. EXE 없는 폴더에서 실행하면 종료코드 비정상으로 중단되는 음성시험도 확인했다. ZIP의260개 파일과 체크섬CSV 일치 및 고객 PDF/원시로그 미포함을 검사했다. 게시 직전 전체pytest는947 PASS/13 SKIP(9 CAD opt-in 미설정 및4 환경 SKIP),36.28초,exit0이었다.

해시/self-check 성공은 AutoCAD 변환 성공이 아니다. 실제 AutoCAD 제품·버전·ProgID·라이선스, `DWG To PDF.pc3` 절대경로, A4가로 용지명을 해당 PC에서 확인한다. LT/수직제품·등록 충돌이면 임의 ProgID나 타PC 설정을 복사하지 않고 차단 사유를 남긴다.

## AutoCAD 검증 순서

1. [AC02 소스 인계](AC02-OTHER-PC-GITHUB-2026-10-07.md), `AGENTS.md`, 관리 이슈 #1을 읽는다. 승인43종의 파일명·SHA256·manifest 개수를 확인한다.
2. 받는 PC의 로컬 AutoCAD TOML을 준비한다. `[cad] provider="autocad"`, 정확한 ProgID, `allow_experimental_autocad=true`를 사용하고 기존 `[gstarcad]` 절은 제거한다. `[plot].autocad_pc3_path`는 받는 PC에 존재하는 `DWG To PDF.pc3`의 절대경로다. matching 기준과 CTB-only 정책은 유지한다.
3. 새 EXE에서 `--config <검토한 로컬 TOML>`로 대표1개 smoke, 승인43종 CLI 변환을 새 출력 폴더에 수행한다. `--cad autocad --allow-experimental-autocad`를 명시하고 필요한 경우 확인한 `--cad-prog-id`를 지정한다. stdout/stderr와 첫 실패를 로컬에 보존한다.
4. 실제GUI의 주소 입력, 파일 다중선택/폴더 입력, 각 선택 단계 취소, 완료 안내를 확인한다. 각각 새 출력 폴더를 사용한다. GUI에서 AutoCAD 옵션을 선택한다. 받는 PC의 PC3/용지 설정이 기본값과 다르면 CLI 로컬 config 성공을 GUI 성공으로 대체하지 말고 GUI 설정 제약을 보고한다.
5. 각 실행 전후 원본 SHA256·수정시각, 사용자 CAD의 PID/생성시각·열린 도면·미저장 상태와 앱 소유 CAD 종료를 별도 확인한다. 업무 CAD를 수정/저장/닫지 않는다.
6. A4가로297x210mm·단일 비공백 페이지·방향·축척·도곽 영역·선가중치를 확인한다. 잔존 색상 및 수용된 표제란 문자 중첩은 실패 조건이 아니다. manifest 감사·육안 검토는 구분한다.
7. 소스 OFF43/ON43·실패 격리는 기존 AC02 소스 인계 계약에 따라 별도 수행/기록한다. 소스 PASS와 frozen PASS, CLI PASS와 GUI PASS를 합치지 않는다.

과거 첫 도면 E203 재발 시 stage/code/HRESULT/예외·traceback을 로컬에 보존한다. Documents.Open/Close 재시도나 시간 제한 완화로 임의 우회하지 않는다. 문제가 생기면 후보 사용을 중단하고 이전 정상 runtime으로 복귀한다. 고객 파일·개인 경로·PID·원시로그·토큰은 공개 GitHub에 올리지 않는다.

## 결과와 최종 배포 게이트

PC별명/제품버전/source·EXE·ZIP SHA/명령과 종료코드/43종 결과/GUI 각 항목/보호 확인/PDF 품질/NOT_RUN/첫 실패·복귀 여부를 로컬 비식별 보고서로 작성한다. 사용자 검토 후 GitHub에 요약한다. AutoCAD 최종 수용과 사용자 MAIN/Release 승인이 있기 전 정식 배포·설치본 교체·브랜치 삭제를 하지 않는다.

## 다른 PC Codex에 전달할 요청

> codex/ac02-gstar-frozen-validation 브랜치의 docs/autocad/AC02-FROZEN-OTHER-PC-2026-10-07.md를 읽고, 해당 사전 배포 ZIP의 해시를 확인한 뒤 새 폴더에서 AutoCAD 최종 검증을 진행해줘. 기존 설치본과 사용자 CAD·원본을 보호하고, 43종 CLI와 실제GUI·소스 OFF/ON을 구분해 검사해줘. PC3/용지는 현재 PC에서 확인하고 오류나 설정 제약은 임의 우회하지 말아줘. 잔존 색상과 기존 표제란 문자 중첩은 무시하며, 결과는 우선 로컬 보고서로 보여줘. MAIN/정식 Release는 별도 승인 전 변경하지 마.
