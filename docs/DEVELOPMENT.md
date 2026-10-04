# 개발 작업 안내

AutoCAD 확장 작업자는 먼저 [개발 허브](autocad/README.md)와 [다른 PC 인계 규칙](autocad/COLLABORATION.md)을 확인합니다. 기획 문서 게시만으로 제품 구현이 승인된 것은 아닙니다.

실행 ZIP 이용자는 Python이 필요하지 않습니다. 개발·빌드는 Windows Python 3.12 x64를 기준으로 합니다.

## 소스 실행·시험

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
$env:PYTHONPATH = "$PWD\src"
$env:DWG_TO_PDF_TEMPLATE_SOURCE_ROOT = "$PWD\template_profiles"
.\.venv\Scripts\python.exe -m dwg_to_pdf 'D:\input' --output 'D:\output' --template-source-root "$PWD\template_profiles"
.\.venv\Scripts\python.exe -m pytest -m 'not gstarcad and not autocad' -q
```

설치에는 인터넷이 필요합니다. `gstarcad` 표식 시험은 실제 CAD와 별도 시험 도면·환경변수를 요구합니다. 고객 도면을 저장소에 올리지 않습니다.

AutoCAD는 실험적입니다. PC-B의 AutoCAD 2021 소스 실기 증거와 최신 MAIN 인계는 [인계 기록](autocad/HANDOFF-2026-10-04.md)을 확인합니다. 기존 릴리스 ZIP에는 이 확장이 포함되지 않으며 GstarCAD 회귀와 새 frozen EXE 검증은 남아 있습니다.

```powershell
python -m dwg_to_pdf --list-cad
python -m dwg_to_pdf 'D:\input' --output 'D:\output' --cad autocad --allow-experimental-autocad
# 설치 후보가 여러 개면 목록에서 확인한 정확한 --cad-prog-id도 지정합니다.
```

실제 AutoCAD 시험은 `AUTOCAD_TEST_ENABLED=1`, `AUTOCAD_TEST_CONFIG`(절대경로), `AUTOCAD_TEST_DWGS`(절대경로를 세미콜론으로 구분)가 모두 있어야 시작됩니다. 설정은 `[cad] provider="autocad"`, `allow_experimental_autocad=true`를 사용하며 기존 `[gstarcad]` 절은 제거합니다. 나머지 설정은 기존 승인값을 유지합니다. `python -m pytest -m autocad -q`의 SKIP는 지원 통과가 아닙니다. [검증 현황](autocad/VALIDATION.md)을 확인하십시오.

## 배포 빌드

위 venv를 준비한 뒤 다음을 실행합니다. 기존 빌드는 Python 3.12 bytecode 규칙을 사용합니다.

```powershell
$site = "$PWD\.venv\Lib\site-packages"
$env:PYTHONPATH = "$site;$site\win32;$site\win32\lib"
$env:DWG_TO_PDF_TEMPLATE_SOURCE_ROOT = "$PWD\template_profiles"
.\.venv\Scripts\python.exe -m compileall -q "$site\typing_extensions.py" "$site\pythoncom.py" "$site\win32\lib\pywintypes.py"
.\packaging\build.ps1 -Python "$PWD\.venv\Scripts\python.exe"
```

`dist/dwg-to-pdf-validation.zip`이 생성됩니다. 내장 self-check, 13개 프로파일·기준 DWG 해시와 파일별 체크섬을 검사합니다. 새 개발 PC의 재빌드 절차는 별도 검증 대상입니다.

## 반영 규칙

변경은 격리된 작업 브랜치에서 검증한 뒤 MAIN에 반영합니다. 기존 로컬 프로젝트는 ESS 저장소와 Git 메타데이터를 공유한 이력이 있어 DWG 전용 저장소에는 프로젝트 스냅샷만 반영합니다. 타 프로젝트 이력·자료는 업로드하지 않습니다.
