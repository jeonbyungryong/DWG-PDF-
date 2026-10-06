# GUI-01 탐색기형 파일·폴더 경로 선택 개선 명세 REV01

## 1. 결론과 승인 상태

DWG 다중 파일 선택, DWG 입력 폴더 선택, PDF 출력 폴더 선택을 Windows Common Item Dialog 기반 탐색기형 창으로 통일한다. 주소 표시줄에서 경로를 확인·복사·붙여넣을 수 있도록 한다. 폴더 선택은 폴더만 선택하며 버튼/표시 내용까지 파일 선택창과 동일하게 만들지는 않는다.

사용자는 제안 범위를 승인하고 구현 전에 기획·명세 작성을 요청했다. 이 문서는 구현 전 검토용 REV01이며, 문서 검토 승인 후 구현한다. 기준 소스는 `3edfeae6fcdd41efa561e23429759f202c732542`, 브랜치는 `codex/gstarcad-main-regression`이다. 모델/추론은 요청된6.1 SOL/Medium을 유지하고 필요 변경은 사용자에게 사전 고지한다.

## 2. 근거와 현행 구조

- 사용자 첨부 화면은 주소 표시줄과 파일 목록을 갖춘 DWG 파일 선택창이다. 사용자는 동일한 경로 조작 방식을 모든 파일·폴더 선택에 원한다.
- `desktop_launcher.py`의 파일 선택은 PowerShell/WinForms `OpenFileDialog`, 입력·출력 폴더 선택은 `FolderBrowserDialog`이다.
- 설치된 pywin32 shell 모듈의 `CLSID_FileOpenDialog`/`IID_IFileOpenDialog`와 FOS 관련 상수가 제공되지 않음을 확인했다. 새 외부 패키지 대신 Python 표준 `ctypes`로 Windows COM 공통 선택창을 호출한다.
- 사용자 보고의 문제 DWG와 과거 자동 실행의 선택창 미관측은 별개 근거다. 이 기능의 근거는 사용자 편의 개선이며, 과거 오류의 원인을 확정하거나 자동 해결을 주장하지 않는다.

## 3. 기능 요구사항

| ID | 요구사항 | 수용 기준 |
| --- | --- | --- |
| R1 | DWG 파일 여러 개 선택 | 탐색기형 창, DWG 필터, 다중 선택, 선택 경로 전체를 기존 CLI에 전달 |
| R2 | DWG 입력 폴더 선택 | 탐색기형 창, 기존 폴더1개 선택, 선택값을 기존 CLI에 전달 |
| R3 | PDF 출력 폴더 선택 | R2와 같은 조작 방식, 기존 출력폴더1개 선택, 파일명을 고르도록 요구하지 않음 |
| R4 | 주소 표시줄 사용 | 세 창에서 주소 선택/경로 복사/붙여넣기/이동을 실제 EXE로 확인 |
| R5 | Unicode/공백 | 한글·공백 경로가 문자열 명령 조립이나 로그 디코딩 없이 동일하게 전달 |
| R6 | 취소와 오류 구분 | 취소는 기존처럼 변환 없이 종료. 다른 API 실패는 오류로 보고하며 취소 성공으로 숨기지 않음 |
| R7 | 소유 자원 정리 | 성공/취소/오류에서 COM 인터페이스·결과 메모리 해제와 COM 초기화 수명 균형 확인 |
| R8 | 실행 번들 | 개발 Python 없이 최신 검증용 EXE가 선택창을 표시. 자체검사/도움말 import-safe 유지 |

폴더 창의 새 폴더 생성 기능은 Windows 기본 동작 범위만 사용한다. 앱 자체의 최근 경로 저장·동기화·즐겨찾기는 추가하지 않는다. 네트워크/동기화 드라이브는 해당 PC에서 접근 가능한 실제 파일시스템 경로만 대상으로 한다. 접근 권한·클라우드 다운로드·네트워크 접속을 자동 해결하지 않는다.

## 4. 변경 설계

새 `src/dwg_to_pdf/windows_picker.py`가 Windows 네이티브 호출·오류·자원 수명을 담당한다. 공개 인터페이스는 `pick_dwg_files(title: str) -> tuple[str, ...]`, `pick_folder(title: str) -> str`이다. 각 함수의 취소 결과는 빈 tuple/빈 문자열이다.

Windows COM을 STA로 초기화하고 `IFileOpenDialog`를 만든다. 기본 옵션을 먼저 읽고 파일 모드에는 다중 선택·실제 파일시스템·존재 경로/파일, 폴더 모드에는 `FOS_PICKFOLDERS`·실제 파일시스템·존재 경로 옵션을 적용한다. 파일은 DWG 필터와 다중 결과, 폴더는 단일 결과의 실제 경로를 Unicode 문자열로 반환한다. `HRESULT_FROM_WIN32(ERROR_CANCELLED)`만 취소로 해석하고 다른 실패는 `OSError`로 전달한다.

DLL/COM 호출은 실제 선택 동작 시 로드하며 모듈 import만으로 UI·CAD를 실행하지 않는다. COM 객체와 메모리를 해제한 뒤 초기화에 성공한 호출에 대해서만 `CoUninitialize`한다. COM 초기화 실패를 임의 재시도하거나 다른 스레드 모델로 바꾸지 않는다.

`WindowsDesktopUI.choose_files`/`_choose_folder`만 새 함수를 사용하도록 연결한다. 기존 `DesktopUI` 계약과 `run_desktop`의 CLI 인수/선택 순서는 유지한다. CAD 설치 목록용 `_run_picker`는 이번 파일·폴더 변경 범위가 아니므로 그대로 둔다.

## 5. 보호 규칙과 제외 범위

- 축척 판정,13종 템플릿,출력창 이동·90도 회전 계산,플롯 설정,CTB-only 색상 정책은 변경하지 않는다.
- 원본DWG 보호,한 배치 한 APP소유CAD,사용자CAD 보존,파일별 실패 격리는 유지한다.
- CAD 엔진/변환 성능/AutoCAD 지원/새 템플릿 지원/최종 오류 보고 형식은 변경하지 않는다.
- 바탕화면 기존 설치본 자동 교체,GitHub MAIN 병합,공식 릴리스는 이번 승인 범위에 포함하지 않는다.
- 기존 검증 ZIP/구성/결과를 보존한 후 새 검증용 번들을 만든다. 원본 고객 도면·개인 로그는 게시하지 않는다.

## 6. 검증과 완료 기준

1. 신규 단위 테스트를 먼저 실패시키고 구현 후 통과시킨다. UI 자체의 자동 시험 대신 네이티브 경계의 제어된 응답을 사용하되 실제 선택·취소 화면은 별도 실기로 검증한다.
2. 옵션 모드,Unicode 결과,다중 결과,취소,실패전파,성공/실패 자원 정리,COM초기화 실패,기존 CLI 전달을 시험한다. 단순 mock 존재 여부를 수용 근거로 쓰지 않는다.
3. 전체 pytest를 새 workspace 임시 경로에서 실행한다. SKIP와 실기 PASS를 구분한다.
4. 실제 새 EXE로 세 창의 주소 표시줄 경로 붙여넣기와 선택을 확인한다. 파일/폴더 단계 취소가 CAD를 시작하지 않는지 확인한다.
5. 기존 정상 ESS7개로 새 EXE 실제 변환과 원본/사용자CAD/소유CAD 정리를 확인하고 PDF 구조·렌더를 확인한다. 폴더 모드와 다중 파일 모드를 각각 검증한다.
6. 다른 PC 검증은 별도 NOT_RUN으로 유지한다. 모의 시험이나 현재 PC 성공만으로 다른 PC/공식 배포 완료를 주장하지 않는다.

## 7. 예상 작업과 리스크

사전 견적2~4시간: 설계15~30분,구현45~90분,기능/회귀30~60분,빌드/실기30~60분. 확정 일정이나 완료 보장이 아니다. COM ABI·자원 정리·frozen 환경이 주요 검토 지점이다. 접근 불가 네트워크 경로와 다른 PC 실기는 추가 시간이 필요할 수 있다. 인터페이스 계약 변경이나 새 런타임 의존이 필요해지면 범위를 재검토한다.

## 8. 공식 참고자료

2026-10-07 확인:

- [Microsoft Common Item Dialog](https://learn.microsoft.com/en-us/windows/win32/shell/common-file-dialog): 공통 파일/폴더 UI,STA,기본 옵션 유지,파일시스템 결과,취소 HRESULT,메모리 해제.
- [Microsoft FILEOPENDIALOGOPTIONS](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/ne-shobjidl_core-_fileopendialogoptions): 폴더/다중 선택/파일시스템 옵션.

구현 계획은 [GUI-01 계획](../plans/2026-10-07-explorer-path-picker.md)을 따른다.
