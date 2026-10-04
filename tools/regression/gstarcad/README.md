# 원래 PC의 GstarCAD 회귀 시험

MAIN의 소스와 이 폴더만 내려받으면 승인13종 및 그 복사본에서 만든 변형30종을 같은 입력으로 검증할 수 있다. 고객 도면을 사용하지 않는다. 현재 PC에서는 GstarCAD 실기를 실행하지 않았다.

## 준비

1. 기존 작업을 보존하고 새 폴더에 MAIN을 clone한다. 기존 checkout을 사용할 경우 clean 상태에서만 `git pull --ff-only`한다. reset/clean으로 변경을 삭제하지 않는다.
2. Windows Python 3.12 x64와 `requirements.lock` 의존성을 준비한다.
3. 사용자가 GstarCAD를 먼저 열어 둔다. 아래 후보 목록에서 실제 ProgID를 확인하고 `gstarcad-approved.toml`에 기록한다. 기본값26을 실제 버전 확인 없이 쓰지 않는다.
4. 원래 PC의 승인 PC3/CTB/실측 A4 매체명을 확인한다. AutoCAD 전용 설정·PC3는 GstarCAD에 사용하지 않는다. 기존 보안 설정을 낮추지 않는다.

## 실행 — 저장소 루트의 PowerShell

```powershell
py -3.12 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install --require-hashes -r requirements.lock
$regressionRepo = (Get-Location).Path
$regressionKit = Join-Path $regressionRepo 'tools\regression\gstarcad'
$env:PYTHONPATH = "$regressionRepo\src"
$env:DWG_TO_PDF_TEMPLATE_SOURCE_ROOT = "$regressionRepo\template_profiles"
& '.\.venv\Scripts\python.exe' -m dwg_to_pdf --list-cad
& '.\.venv\Scripts\python.exe' -m dwg_to_pdf --self-check
$env:GSTAR_REGRESSION_REPO = $regressionRepo
$env:GSTAR_REGRESSION_CONFIG = Join-Path $regressionKit 'gstarcad-approved.toml'
$env:GSTAR_REGRESSION_ENABLED = '1'
$regressionRun = Join-Path $regressionRepo ('work\gstar-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $regressionRun | Out-Null

# 기본 pytest 임시 폴더 접근 문제 및 venv 리다이렉터의 프로세스 식별 오판을 피한다.
$regressionBasePython = (py -3.12 -c 'import sys; print(sys.executable)').Trim()
$regressionSite = Join-Path $regressionRepo '.venv\Lib\site-packages'
$env:PYTHONPATH = "$regressionRepo\src;$regressionSite;$regressionSite\win32;$regressionSite\win32\lib"
& $regressionBasePython -m pytest -m 'not gstarcad and not autocad' -q -rs -p no:cacheprovider --basetemp "$regressionRun\offline-temp" --junitxml "$regressionRun\offline.xml" *> "$regressionRun\offline.log"
if ($LASTEXITCODE -ne 0) { throw '오프라인 회귀 실패' }
$env:PYTHONPATH = "$regressionRepo\src"

& '.\.venv\Scripts\python.exe' -m pytest "$regressionKit\test_gstar_regression.py" -c pyproject.toml -q -s -p no:cacheprovider -p no:faulthandler --basetemp "$regressionRun\temporary" --junitxml "$regressionRun\gstar-live.xml" *> "$regressionRun\gstar-live.log"
if ($LASTEXITCODE -ne 0) { throw '실기 실패: 로그와 출력 보존 후 조사' }
& '.\.venv\Scripts\python.exe' "$regressionKit\audit_gstar_outputs.py" $regressionRun
if ($LASTEXITCODE -ne 0) { throw '출력/판정/OFF-ON 차이: 근거 보존 후 조사' }
```

심볼릭 링크4개는 관리자 토큰에서 실행해야 한다. 해당 시험 프로세스만 승격하면 되고 영구 정책 변경은 필요하지 않다. SKIP를 PASS로 기록하지 않는다.

## 실제 수용 증거

- 3개 통합 시험: 원본/사용자CAD 보호,43종×OFF/ON=86변환,손상파일 이후 정상파일 계속 처리.
- 입력 SHA256,기대 축척·회전·출력창(오차0.001도면 단위 미만),한 배치 한 소유 PID,원본hash/mtime,작업용CAD 종료.
- `single/off/on-session.json`: 실제 COM 버전,ProgID,소유PID,원본/PID 보존.
- `extraction-evidence.json`와 로그: 실제 native 성공 또는 COM fallback. ON 설정만으로 직접 LISP 성공을 주장하지 않는다.
- `output-audit.json`: 엄격 PDF 파싱,단일 비암호화 페이지,A4가로±0.2mm,Rotate0,흑백·비공백,144dpi OFF/ON43쌍 동일.
- 사용자 육안 확인: 도곽,방향,문자누락,선굵기. 차이는 근거를 보존하고 수용 여부를 판단한다.

## 이전 코드와 동일 엔진 회귀 비교

이전 인계 기준 `a546c4fc8bc960b6e5e2a36a3317e507db4d4352`를 별도 checkout하여 같은 GstarCAD 버전·승인 설정·입력으로 BEFORE/AFTER를 비교한다. 공식 릴리스 기준 비교가 필요하면 해당 릴리스 SHA도 추가한다. AutoCAD와 GstarCAD 픽셀 동일성을 요구하지 않는다.

```powershell
git worktree add --detach '..\DWG-PDF-gstar-before' a546c4fc8bc960b6e5e2a36a3317e507db4d4352
$regressionBefore = (Resolve-Path '..\DWG-PDF-gstar-before').Path
& '.\.venv\Scripts\python.exe' tools\benchmark_conversion.py --code-root $regressionBefore --source-root "$regressionBefore\template_profiles" --input-root "$regressionKit\inputs" --config $env:GSTAR_REGRESSION_CONFIG --result "$regressionRun\before.json"
if ($LASTEXITCODE -ne 0) { throw 'BEFORE 실패' }
& '.\.venv\Scripts\python.exe' tools\benchmark_conversion.py --code-root $regressionRepo --source-root "$regressionRepo\template_profiles" --input-root "$regressionKit\inputs" --config $env:GSTAR_REGRESSION_CONFIG --result "$regressionRun\after.json"
if ($LASTEXITCODE -ne 0) { throw 'AFTER 실패' }
# pdftoppm이 PATH에 있어야 한다. 순수 시간 측정에는 --probe-com을 쓰지 않는다.
& '.\.venv\Scripts\python.exe' tools\compare_benchmark_results.py "$regressionRun\before.json" "$regressionRun\after.json" --output "$regressionRun\comparison.json"
if ($LASTEXITCODE -ne 0) { throw '이전 버전 대비 판정/픽셀 차이' }
```

기존 `GSTARCAD_WINDOW_LEARNING_DWGS`는 잘못된 저장창을 가진 원래 PC의 승인 자료2개가 별도로 필요하다. 이 폴더의 일반 도면으로 대체해 통과 처리하지 않는다. 기존 gstarcad 표식6개의 환경변수는 `tests/integration`을 참조한다. 여기의 통합3개가 모든 특수 목적시험을 자동 대체하지 않는다. G3 검토 후 frozen EXE·Python 없는 PC의 G5를 진행한다.
