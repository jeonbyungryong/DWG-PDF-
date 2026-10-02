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
.\.venv\Scripts\python.exe -m pytest -m 'not gstarcad'
```

설치에는 인터넷이 필요합니다. `gstarcad` 표식 시험은 실제 CAD와 별도 시험 도면·환경변수를 요구합니다. 고객 도면을 저장소에 올리지 않습니다.

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
