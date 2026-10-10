# 다른 PC 설치·사용 안내 — 2026-10-10

## 1. 준비와 다운로드

필요 조건은 Windows x64와 정식 CAD 설치·라이선스입니다. AutoCAD2021은 현재 PC에서 실기 확인했습니다. 다른 PC·다른 버전은 아래 대표 도면 시험으로 현지 환경을 확인합니다. GstarCAD2026 경로도 포함되지만 이번 변경의 실기 회귀는 연기 상태입니다.

1. [Release 페이지](https://github.com/jeonbyungryong/DWG-PDF-/releases/tag/windows-autocad-final-20261010)의 Assets에서 `DWG-to-PDF-Windows-x64-20261010.zip`을 받습니다. Source code ZIP은 실행파일이 아닙니다.
2. `C:/DWG-PDF` 등 쓰기 가능한 로컬 폴더에 전체 압축을 풉니다. 이후 안내는 `C:/DWG-PDF/DWG-to-PDF`에 풀었다고 가정합니다.
3. `dwg-to-pdf.exe`와 `_internal` 폴더를 함께 유지합니다. Python·Git 별도 설치는 필요하지 않습니다.
4. 동봉 `시작하기.txt` 또는 이 안내를 읽습니다. 설치형 MSI/관리자 설치 프로그램이 아닌 전체 압축 해제 방식입니다.

## 2. AutoCAD: 새 PC에서 처음 한 번 준비

기존 PC의 TOML·캐시·개인 PC3 경로를 그대로 복사하지 마세요. 현재 PC에서 이미 정상 저장된 설정은 다음 실행부터 자동 적용됩니다.

1. 해당 PC의 AutoCAD를 한 번 정상 실행해 초기 설정·라이선스 확인을 마칩니다.
2. AutoCAD에서 `PLOTTERMANAGER`를 입력해 플로터 폴더를 엽니다. 그 PC의 `DWG To PDF.pc3`를 **복사**하여 프로그램 폴더 아래 `settings/plotter/DWG To PDF.pc3`에 둡니다. 설치 폴더의 원본을 옮기거나 수정하지 않습니다. 이 명령은 플로터 구성 폴더를 여는 Autodesk의 공식 절차입니다. [Autodesk 안내](https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-Core/files/GUID-EC868B37-1C12-40CD-9C26-1983C91D7C3A.htm)
3. 동봉 `AutoCAD.example.toml`을 같은 폴더에 `AutoCAD.toml`로 복사합니다. 메모장으로 열어 `[plot]`의 `autocad_pc3_path`를 방금 복사한 PC3의 **실제 절대 경로**로 수정합니다. 슬래시 `/`를 쓰고 파일명은 `DWG To PDF.pc3`를 유지합니다.
4. 예시의 A4 canonical 용지 이름 `ISO_full_bleed_A4_(297.00_x_210.00_MM)`은 현재 검증 PC 기준입니다. 해당 PC에 같은 용지가 없으면 임의 이름을 만들지 말고 해당 PC의 `DWG To PDF.pc3`에 등록된 canonical A4 이름을 확인해 하나를 `preferred_media_names`에 지정합니다. 출력은297×210mm A4 가로만 지원합니다.
5. AutoCAD에서 `monochrome.ctb`를 사용할 수 있는지 확인합니다. CTB 표는 AutoCAD 색상 기반 플롯 스타일입니다. [Autodesk CTB 안내](https://help.autodesk.com/cloudhelp/2021/ENU/AutoCAD-Core/files/GUID-F6DF548E-DF71-45F7-8DC5-A1EAD73998B1.htm)
6. EXE를 실행해 대표 DWG1개와 출력 폴더를 선택하고, CAD 선택에서 **아니요: AutoCAD**를 선택합니다. 처음 표시되는 설정 선택창에서 준비한 `AutoCAD.toml`을 선택합니다.
7. 성공하면 설치·TOML·PC3의 지문을 저장합니다. 프로그램을 종료하고 다시 실행하여 TOML 선택 없이 자동 변환되는지 확인합니다. 파일을 이동·변경·삭제하거나 CAD 설치가 달라지면 설정 선택창이 다시 나타날 수 있습니다.

`[cad]`의 `allow_experimental_autocad=true`는 기존 설정 형식과의 호환용 활성화 항목이므로 유지하세요. GUI에는 실험적 문구나 추가 실험 확인창을 표시하지 않습니다. ProgID는 예시에서 지정하지 않으며 GUI가 실제 발견한 설치를 CLI에 전달합니다. 복수 설치가 자동 결정되지 않을 때만 설치를 선택합니다.

### A4 이름 확인: E211이 발생할 때만

AutoCAD에서 **새 빈 도면**을 만들고 그 빈 도면을 활성화합니다. 작업 중인 원본 도면에서는 아래 명령을 실행하지 않습니다. 다음 명령을 명령창에 한 줄씩 입력하면 `DWG To PDF.pc3`에 등록된 canonical 용지 이름을 출력합니다. 긴 결과는 F2로 확인합니다.

```lisp
(vl-load-com)
(setq pdfSetupLayout (vla-get-ActiveLayout (vla-get-ActiveDocument (vlax-get-acad-object))))
(vla-put-ConfigName pdfSetupLayout "DWG To PDF.pc3")
(vla-RefreshPlotDeviceInfo pdfSetupLayout)
(vlax-safearray->list (vlax-variant-value (vla-GetCanonicalMediaNames pdfSetupLayout)))
```

표시된 목록에서 **297×210mm A4**에 해당하는 정확한 이름 하나를 복사해 `preferred_media_names = ["확인한 이름"]`에 넣습니다. 위 예시의 임의 문구를 그대로 넣지 않습니다. 프로그램은 실제 용지 크기를 다시 검사합니다. 빈 도면은 저장하지 않고 닫습니다. 이름이나 크기가 불분명하면 결과와 CAD 버전을 GitHub Issues에 알려주세요. 명령이 정책으로 제한되면 보안 설정을 낮추지 않고 CAD 관리자에게 확인합니다.

이 절차는 Autodesk의 [GetCanonicalMediaNames 및 RefreshPlotDeviceInfo API 안내](https://help.autodesk.com/cloudhelp/2025/ENU/AutoCAD-ActiveX-Reference/files/GUID-BDFDA2F3-63E6-47CD-8185-1793BEEDBCB1.htm)에 따른 수동 조회 방법입니다. 배포 프로그램의 자동 변환 과정에는 이 수동 명령 입력이 필요하지 않습니다.

## 3. GstarCAD

GstarCAD2026과 COM 등록, `DWG To PDF.pc3`, `monochrome.ctb`, A4 가로 용지를 준비합니다. CAD 선택에서 **예: GstarCAD**를 선택합니다. AutoCAD TOML은 선택하지 않습니다. 설치가 하나이면 자동 적용됩니다. 이 배포본의 최신 GstarCAD 실기 회귀는 연기되어 있으므로 기존 정상 실행본을 보존하고 대표 도면으로 먼저 확인합니다. 현지 PC 회귀 절차는 저장소의 `tools/regression/gstarcad/README.md`에 있습니다.

## 4. 평소 사용

**입력 방식 → DWG 파일/폴더 → PDF 출력 폴더 → CAD 종류 → 자동 변환 → 완료 안내**.

기존 PDF는 덮어쓰지 않고 번호를 붙여 새 파일로 저장합니다. 실패·건너뜀은 완료 안내와 콘솔 요약에서 확인합니다. 처음에는 대표 도면1개로 방향·도곽·잘림·글꼴·색상을 확인한 뒤 일괄 작업합니다.

## 5. 무결성 및 실행 확인 (PowerShell, 선택 사항)

다운로드 폴더에서 다음 결과를 Release의 `SHA256SUMS.txt`와 비교합니다.

```powershell
Get-FileHash .\DWG-to-PDF-Windows-x64-20261010.zip -Algorithm SHA256
```

전체 압축 해제한 `DWG-to-PDF` 폴더에서 실행합니다.

```powershell
.\dwg-to-pdf.exe --self-check
.\dwg-to-pdf.exe --list-cad
```

`RUNTIME_SELF_CHECK_OK`는 런타임·프로파일 확인이며 실제 CAD 출력 성공을 보증하지 않습니다. `--list-cad`는 설치 조회이며 CAD를 실행하지 않습니다. 동봉 `files-sha256.csv`는 첫 실행 전 배포 파일 목록입니다. 개인 `AutoCAD.toml`과 복사한 PC3는 목록에 없으며 의도적으로 수정한 설정은 배포 해시와 달라질 수 있습니다.

## 6. 오류와 복구

| 오류/현상 | 조치 |
|---|---|
| EXE 시작 실패 | 전체 압축 해제·`_internal` 유지·보안 프로그램 차단 기록 확인 |
| E220/설치 미발견 | CAD 최초 실행·라이선스·COM 등록 확인; 검색 결과에 없는 ProgID를 임의 입력하지 않기 |
| E001/잘못된 설정 | TOML 문법,PC3 실제 절대 경로,용지297×210,`monochrome.ctb` 확인 |
| E211/A4 모호성 | 현지 PC3에 등록된 canonical A4 이름 하나를 확인해 설정에 지정; 확인이 어려우면 오류 코드와 CAD 버전으로 문의 |
| 플롯/글꼴 누락 | 해당 CAD에서 PC3·CTB·필요 폰트가 사용 가능한지 확인 |
| 변환 실패 | 성공/실패 요약 확인; 오류 코드·버전·재현 절차를 GitHub Issues에 기록 |

자동 적용 설정을 다시 선택하려면 프로그램을 종료하고 `%LOCALAPPDATA%/DWG-to-PDF/autocad-settings.json` 이름을 바꾸어 보존한 뒤 실행합니다. 다른 PC의 캐시를 가져오지 않습니다. 이전 Release ZIP을 별도 폴더에 풀면 이전 버전으로 복구할 수 있습니다. 기존 도면·출력·CAD 설치를 삭제하거나 Windows 보안 정책을 낮출 필요가 없습니다.

승인된13종 축척 밖의 도면은 지원하지 않습니다. native LISP 실행이 정책으로 제한되면 보안 설정을 낮추지 말고 사용 설정의 `[matching]`에 `use_native_extraction=false`를 지정해 기존 COM 방식을 사용합니다. CTB가 바꾸지 못한 색상은 승인된 정책상 허용합니다.
