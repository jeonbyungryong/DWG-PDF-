# DWG to PDF 자동변환 프로그램

AutoCAD 또는 GstarCAD를 사용해 승인된 13개 축척의 DWG를 PDF로 변환하는 Windows 프로그램입니다. 도면의 Scale 표기와 도곽으로 축척·위치·회전을 판단합니다.

## 다운로드하고 실행하기

1. [Windows 실행 ZIP 다운로드](https://github.com/jeonbyungryong/DWG-PDF-/releases/download/windows-autocad-final-20261010/DWG-to-PDF-Windows-x64-20261010.zip)를 받습니다. [Release 페이지](https://github.com/jeonbyungryong/DWG-PDF-/releases/tag/windows-autocad-final-20261010)에서 사용 안내와 SHA256도 확인할 수 있습니다.
2. ZIP을 로컬 폴더에 **전체 압축 해제**합니다. `DWG-to-PDF` 폴더의 `dwg-to-pdf.exe`와 `_internal`을 함께 유지합니다. Python이나 Git은 설치하지 않아도 됩니다.
3. 사용할 PC에 라이선스가 있는 CAD가 설치되어 있어야 합니다. AutoCAD의 새 PC 첫 설정은 [설치 안내](docs/INSTALL-KO.md)를 따릅니다.
4. EXE를 더블클릭합니다: **입력 방식 → DWG 파일/폴더 → PDF 출력 폴더 → CAD 종류 → 변환 → 완료 안내**.
5. 먼저 대표 도면1개의 출력 방향·잘림·글꼴을 확인한 뒤 일괄 작업합니다.

GitHub의 초록색 Code 버튼의 Download ZIP이나 Release의 Source code는 소스입니다. 실행하려면 위 이름의 **Windows 실행 ZIP**을 받으세요.

## 이번 정식 배포의 확인 범위

사용자가 2026-10-10 현재 PC AutoCAD 최종 검증 통과와 최종 배포를 승인했습니다. AutoCAD2021 실기 확인 및 새 기본 바로가기 파일7종·폴더7종 변환을 통과했습니다. 최신 전체 자동화 시험은 **986 PASS /13 SKIP**이며 별도 CAD 실기와 심볼릭 링크 권한 제외를 포함합니다.

GstarCAD 경로는 포함되어 있지만 **이번 변경의 GstarCAD 실기 회귀는 사용자 요청으로 연기**했습니다. 다른 PC나 다른 AutoCAD 버전의 실기 성공을 뜻하지 않습니다. [최종 GUI 검증](docs/autocad/AC09-STANDARD-GUI-2026-10-10.md), [앞선 AutoCAD 실기](docs/autocad/AC03-READINESS-2026-10-09.md), [배포 기록](docs/releases/2026-10-10-autocad-final.md)을 참조하세요.

## 사용하는 동안

- CAD 종류는 직접 선택합니다. 설치가 하나이면 자동 적용하고, AutoCAD 설치가 여러 개여도 유효한 저장 설정이 있는 설치가 하나이면 자동 적용합니다.
- 새 PC의 AutoCAD는 PC3·용지 설정을 처음 한 번 준비하고 TOML을 선택합니다. 성공한 설정은 해당 Windows 사용자에게 저장되어 다음부터 자동 적용됩니다. 설정·PC3·CAD 설치가 바뀌면 다시 선택합니다.
- 승인 축척: 1:1,1:2,1:5,1:10,1:20,1:50,1:100,2:1,5:1,10:1,20:1,50:1,100:1. 파일명에 축척 표기는 필요하지 않습니다.
- A4 가로297×210mm, `DWG To PDF.pc3`, `monochrome.ctb`를 사용합니다. CTB가 흑백으로 바꾸지 못하는 색상은 허용하며 별도 RGB 보정은 하지 않습니다.
- 원본 DWG를 수정하지 않고 작업 사본을 변환합니다. 기존 PDF는 번호가 붙은 새 파일로 보존합니다. 사용자 CAD 보호와 프로그램 소유 CAD 종료 절차를 유지합니다.
- 실제 오류와 공통 완료 안내는 표시합니다. 설치·플로터·용지 검증을 생략하지 않습니다.

## 필요한 자료

| 내용 | 링크 |
|---|---|
| 다른 PC 설치·첫 AutoCAD 설정 | [설치 안내](docs/INSTALL-KO.md) |
| 사용 방법과 실패 처리 | [사용자 가이드](docs/USER_GUIDE_KO.md) |
| AutoCAD 새 PC용 설정 예시 | [AutoCAD.example.toml](config/AutoCAD.example.toml) |
| 검증과 개발 인계 | [AutoCAD 개발 허브](docs/autocad/README.md) |
| 소스 실행·빌드 | [개발 안내](docs/DEVELOPMENT.md) |
| 문제 보고 | [GitHub Issues](https://github.com/jeonbyungryong/DWG-PDF-/issues) |

CAD 프로그램·라이선스·PC3·CTB·폰트는 대상 PC에서 준비합니다. 실행 ZIP에는 런타임과 승인된 기준 템플릿이 포함되며 고객 도면·출력·개인 설정은 포함하지 않습니다. 이전 Release와 백업은 복구용으로 보존합니다.
