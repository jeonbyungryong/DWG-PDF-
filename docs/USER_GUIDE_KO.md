# DWG to PDF 사용자 가이드

## 적용 범위

APP은 승인된 13개 축척(1:1, 1:2, 1:5, 1:10, 1:20, 1:50, 1:100, 2:1, 5:1, 10:1, 20:1, 50:1, 100:1) 도면만 처리합니다. DWG 파일명에 축척 표기는 필요하지 않습니다.

## 자동 판단 방식

- 유효한 `Scale` 값은 대응 템플릿을 직접 선택합니다.
- `Scale` 라벨과 값의 학습된 상대 위치로 이동과 0/90/180/270도 회전을 판단하고 템플릿 Plot Window를 대상 도면 좌표로 변환합니다.
- `Scale` 값이 blank 또는 N/A이면 canonical-13 structural fallback으로 도곽 구조를 비교하며, score와 gap이 모두 1.0일 때만 승인합니다.
- 비균일 축척, mirror, 지원하지 않는 회전, 여러 Scale 라벨은 해당 파일만 실패 처리합니다.
- 속성이 없는 SolidWorks `SW_CENTERMARKSYMBOL_*` 블록은 Scale/도곽 탐색에 기여하지 않는 중심표시 기하로 제외합니다. 속성이 있거나 사용자 정의 이름이면 이 예외를 적용하지 않습니다.

## 실행 방법

EXE를 더블클릭하면 입력 DWG/폴더와 출력 폴더를 선택하는 창이 열립니다. 명령행에서는 다음과 같이 실행합니다.

```powershell
dwg-to-pdf.exe 'D:\input' --output 'D:\output' --conflict copy
dwg-to-pdf.exe 'D:\input\part.dwg' --output 'D:\output' --config 'D:\operator\config.toml' --profiles 'D:\operator\profiles' --template-source-root 'D:\template-source' --conflict overwrite
dwg-to-pdf.exe --self-check
```

충돌 정책은 `ask`, `overwrite`, `copy`, `skip`입니다. `copy`는 기존 PDF를 보존하고 번호가 붙은 새 파일을 만듭니다.

## GstarCAD와 오류 처리

정상 batch는 one APP-owned GstarCAD session을 열어 모든 도면을 순차 처리하고 완료 후 그 프로세스만 종료합니다. 사용자가 별도로 열어 둔 GstarCAD는 종료하지 않습니다. APP 세션이 비정상 상태일 때만 APP 소유 프로세스를 교체하며, 한 파일의 실패가 나머지 파일을 중단시키지 않습니다.

완료 후 성공·실패·건너뜀을 한 번에 요약합니다. 사용자 창에는 파일명과 간단한 사유를 표시하고 COM 세부정보는 로그에만 남깁니다.

## 검증 범위와 제한

2026-07-20 기준 두 실제 도면 집합 22개(기존 18개 + 신규 4개)가 모두 변환되었고 PDF 22개는 1페이지·비공백으로 확인되었습니다. 저장된 PlotType이 Window가 아닌 신규 DWG도 계산된 Window 좌표를 먼저 등록한 뒤 Window 플롯 모드로 전환하므로 처리됩니다. 원본 DWG는 변경되지 않았고 사용자 GstarCAD PID도 보존되었습니다. 다만 이 22개는 독립 held-out 표본이 아니므로 production 적용 전 신규 도면 및 clean-account 검증이 추가로 필요합니다. 과거 `actual 6` validation gate는 이번 22개 사례로 확대되었습니다.
