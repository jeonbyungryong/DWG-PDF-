# 다른 PC Codex 인계 — AC02 AutoCAD 검증
상태: HANDOFF_READY / 다른 PC 실기 NOT_RUN. 사용자 요청에 따라 GitHub의 검증 브랜치와 복구 태그로 인계한다.

## 반드시 사용할 기준
- 저장소: https://github.com/jeonbyungryong/DWG-PDF-
- 인계 브랜치: `codex/autocad-followup-validation`. 브랜치의 문서 후속 커밋과 아래 검증 제품 SHA를 구분한다.
- 실제 시험 시작 SHA: `c6bb03f8326aa854b753ba8631ec0d8ed11264b8` (로컬 MAIN에 병합하고 전체 회귀를 검증한 커밋).
- 제품 코드 기준: `ca11b14c6123fa952f999c0d4bf2b0f444f4c70b`. 위 병합본의 src/tests/프로파일/설정/packaging은 이 제품 코드와 같다.
- 기존 MAIN 복구 SHA: `30d6f23996035784154f3c306641488bcd2879bf`.
- 복구 태그: `rollback-main-before-ac02-20261007`; 복구 브랜치: `codex/backup-main-before-ac02-20261007`.
- 병합 태그: `ac02-main-integration-20261007` → `c6bb03f8326aa854b753ba8631ec0d8ed11264b8`.
- 이번 인계 게시 대상은 위 검증 브랜치와 복구 ref다. 원격 MAIN과 공식 Release 승인은 별도다.

## GitHub에서 두 환경 준비
기존 작업과 설치본을 그대로 보존한다. 현재 폴더에서 reset/clean/stash로 작업을 숨기지 않는다. 다음 두 경로는 받는 PC에서 선택하는 **새 폴더**다. 이미 존재하면 다른 경로를 선택한다.

Windows PowerShell 콘솔에서:
```powershell
$ErrorActionPreference = 'Stop'
$repo = 'https://github.com/jeonbyungryong/DWG-PDF-.git'
$candidate = 'D:\DWG validation\AC02 candidate'
$previous = 'D:\DWG validation\previous MAIN'
if ((Test-Path -LiteralPath $candidate) -or (Test-Path -LiteralPath $previous)) { throw 'Choose new directories; preserve existing work' }
git clone --branch codex/autocad-followup-validation -- $repo $candidate
if ($LASTEXITCODE -ne 0) { throw 'Candidate clone failed' }
git -C $candidate switch --detach c6bb03f8326aa854b753ba8631ec0d8ed11264b8
if ($LASTEXITCODE -ne 0) { throw 'Cannot pin validated source' }
$head = git -C $candidate rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $head.Trim() -ne 'c6bb03f8326aa854b753ba8631ec0d8ed11264b8') { throw 'Candidate SHA mismatch' }
git clone --branch rollback-main-before-ac02-20261007 -- $repo $previous
if ($LASTEXITCODE -ne 0) { throw 'Previous MAIN clone failed' }
$head = git -C $previous rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $head.Trim() -ne '30d6f23996035784154f3c306641488bcd2879bf') { throw 'Recovery SHA mismatch' }
```
detached HEAD는 검증 SHA를 고정하기 위한 상태다. 코드 수정이 필요하면 전용 codex/* 작업 브랜치를 먼저 만든다. 다른 PC에서 기록된 SHA가 보이지 않으면 인계를 진행하지 말고 remote/ref 확인부터 한다.

복구 clone의 `releases/windows/dwg-to-pdf-validation.zip`은 기존 MAIN의 실행본이다. ZIP SHA256은 `E98EA569C8EE6F99184512E7DD589F3C6F25850149BE026836C7A44D1664C39D`. 기존 정상 설치본과 동일 제품임을 확인하고 새 폴더에 전체 압축 해제해 보존한다. 새 AutoCAD 기능이 포함된 실행 파일이라고 판단하지 않는다.

## 검증 순서
1. AGENTS.md, AutoCAD 개발 허브, [복구 안내](AC02-MAIN-ROLLBACK-2026-10-07.md), [개발 안내](../DEVELOPMENT.md)와 관리 이슈 #1의 최신 기록을 읽는다. 실제 Windows/PowerShell/Python/CAD 제품·버전과 기존 사용자 CAD 상태를 확인한다. AutoCAD가 없거나 LT/수직제품/등록 충돌이면 AutoCAD 실기는 NOT_RUN 또는 차단으로 남긴다.
2. Python 개발 환경이 있으면 개발 안내의 의존성 계약을 확인한다. 실행 정책이나 CAD 보안/신뢰 설정은 낮추지 않는다. Python이 없으면 소스 검증 환경 준비 또는 새 검증 runtime 빌드를 먼저 한다. 이전 GUI-01/GstarCAD EXE로 이번 AC02 AutoCAD 소스 성공을 대신하지 않는다.
3. 새 출력/로그 폴더를 사용한다. `python -m dwg_to_pdf --list-cad`로 실제 ProgID를 확인한다. AutoCAD 설정은 받는 PC의 새 로컬 TOML에만 작성한다. `[cad]`의 provider/정확한 ProgID/allow_experimental_autocad=true와 받는 PC의 PC3 경로·A4 가로 용지명을 확인한다. `[plot].autocad_pc3_path`는 실제 존재하는 절대 경로이며 파일명은 `DWG To PDF.pc3`이어야 한다. `[cad]` 설정 시 기존 `[gstarcad]` 절을 제거한다. 기존 matching 수용값과 monochrome.ctb 정책을 유지한다. 이전 PC의 개인 경로·설정·라이선스를 복사하지 않는다.
4. `tools/regression/gstarcad/inputs-manifest.json`의 cases43개와 `tools/regression/gstarcad/inputs/`의 DWG43개가 정확히 대응하는지 SHA256으로 확인한다. 배열 count는 ConvertFrom-Json 후 별도 변수에 담아 검사한다. 새 고객 도면은 검증 표본에 추가하지 않는다.
5. 전체 오프라인 회귀를 먼저 실행한다: `python -m pytest -m 'not autocad and not gstarcad' -q -ra`. CAD deselect와 환경 SKIP은 실기 성공이 아니다.
6. 사용자 AutoCAD가 준비되어 있으면 PID/생성시각/창·열린 도면/미저장 상태 및 입력 해시·수정시각을 읽기 전용으로 기록한다. 기존 업무 도면을 저장/닫기/수정하지 않는다. 아래 실기 계약에 따라 smoke → OFF43/ON43 → 실패 후 정상 파일 계속 진행을 시험한다. 앱이 소유한 새 CAD만 제어·종료한다.
7. 별도 frozen runtime을 빌드하면 product SHA, EXE/ZIP SHA, self-check,43종 및 GUI를 따로 검증한다. GUI는 파일 다중선택/폴더 입력, 각 단계 취소와 완료 요약을 확인한다. 소스 실기로 GUI/frozen 성공을 대신하지 않는다.
8. A4가로297x210mm 단일 비공백 페이지, 방향/축척/출력 영역, 원본 보호·사용자 CAD 유지·앱 CAD 종료를 확인한다. 잔존 색상 허용, 추가 RGB 보정 없음. **우측 하단 표제란 문자 겹침은 사용자가 무시하도록 결정했다.** 그 외 변환 실패/원본 변경/사용자 CAD 간섭/부적합 출력이면 새 시험본 사용을 중단하고 이전 폴더로 복귀한다.

## 실제 AutoCAD 테스트 진입점
받는 PC에서 검증한 설정과 표본의 절대 경로를 사용한다.
```powershell
# 후보 소스 폴더에서, 개발 안내에 따른 Python/의존성이 준비된 뒤 실행.
$env:PYTHONPATH = Join-Path $PWD 'src'
$env:DWG_TO_PDF_TEMPLATE_SOURCE_ROOT = Join-Path $PWD 'template_profiles'
$env:AUTOCAD_TEST_ENABLED = '1'
$env:AUTOCAD_TEST_CONFIG = 'D:\DWG validation\local-autocad.toml' # 해당 PC에서 검토한 설정
$manifest = Get-Content -LiteralPath 'tools/regression/gstarcad/inputs-manifest.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$cases = @($manifest.cases)
if ($cases.Count -ne 43) { throw 'Expected 43 approved cases' }
$inputs = Join-Path $PWD 'tools/regression/gstarcad/inputs'
$env:AUTOCAD_TEST_DWGS = ($cases | ForEach-Object { Join-Path $inputs $_.file }) -join ';'
# 실행 전에 43개 존재/해시 및 공존 사용자 AutoCAD 준비 상태를 검증한다.
$run = Join-Path (Split-Path $PWD) ('AC02-validation-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $run) { throw 'Output path exists; preserve previous evidence' }
python -m pytest tests/integration/test_autocad.py -q -s -p no:cacheprovider --basetemp $run
$testExit = $LASTEXITCODE
if ($testExit -ne 0) { throw 'CAD validation failed; preserve outputs/logs and return to previous version' }
```
테스트는 OFF/ON 판정 일치와 파일/PID 보호를 포함하지만, 이 명령만으로 사용자 도면의 미저장 상태 유지, 실제 선가중치/육안 품질 및 전체 수용을 입증하지 않는다. 전후 증거를 별도로 확인한다.

## 현재 PC 근거와 남는 항목
- 병합 MAIN 오프라인947 PASS/4 symlink SKIP/9 CAD deselect,48.86초.
- AutoCAD2021 소스 OFF43/ON43, 일반 동결43종 및 원본/사용자 CAD 보호 통과.
- 일반 GUI7종, 진단 GUI4회 각7종, 추가 CLI7종 통과. PDF 감사 및 동일 제품 기준 RGB 비교 통과.
- 사용자 PDF 확인 양호. 우측 하단 글자 겹침 수용/무시.
- 독립 코드 리뷰 Critical0/Important0. Windows PowerShell5.1 복구 clone 및 별도 clone의 revert로 이전 MAIN tracked tree 정확한 복원 확인.
- 과거 일반 GUI 첫 파일 E203 실패2회는 원인 미확정이다. 재발 시 첫 실패의 stage/code/원인 예외/HRESULT/traceback을 로컬에 보존한다. Documents.Open/Close 재시도를 추가하거나 추측 수정하지 않는다.
- native LISP 자체 성공, 다른 PC 실기 및 공식지원 완료는 미확정이다. 현재 PC Codex elevated Computer Use setup-refresh 오류는 제품 변환과 별개다.
- 모델·추론 설정 변경 없음.

## 실패 시 복귀와 인계
시험본을 중단하고 보존한 previous MAIN/기존 정상 runtime 폴더를 사용한다. 후보 실행과 업무 CAD 상태가 불명확하면 이름으로 강제 종료하지 않고 정확한 소유권을 확인한다. 필요 시 별도 깨끗한 clone에서 `git revert -m 1 ac02-main-integration-20261007`을 검토한다. 공유 MAIN의 revert/push는 검증 결과와 사용자 승인 후 수행한다.

결과는 우선 로컬 비식별 보고서로 작성한다: PC별명/환경, source·runtime SHA,명령/종료코드,43종 성공·실패 수,GUI 각 항목,입력/업무 CAD 보호,SKIP/NOT_RUN,실패 원인·복귀 여부·다음 행동. 고객 DWG/PDF, 개인 경로/PID/원시로그/토큰은 GitHub에 게시하지 않는다. 보고 게시 전 사용자에게 검토받는다.

## 다른 PC Codex에 전달할 문장
> 이 GitHub AC02 인계 문서를 읽고 codex/autocad-followup-validation에서 c6bb03f8326aa854b753ba8631ec0d8ed11264b8을 새 검증 폴더에 고정해 검증해줘. 먼저 rollback-main-before-ac02-20261007의 이전 MAIN30d6f239를 별도 폴더에 확보하고 기존 설치본과 업무 CAD를 보호해줘. 위 순서로 환경·43종 해시·오프라인·AutoCAD 실기·GUI/frozen을 구분해 검사하고, 문제 발생 시 로그를 보존하고 이전 버전으로 돌아가줘. 우측 하단 표제란 글자 겹침은 무시해줘. 결과는 우선 로컬 보고서로 보여줘.
