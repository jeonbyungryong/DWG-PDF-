# DWG to PDF 자동변환 APP

등록된 13개 축척 템플릿을 기준으로 GstarCAD에서 DWG를 PDF로 변환하는 Windows APP입니다. 파일명에 축척이 없어도 도면 우측 하단의 `Scale` 라벨과 값으로 템플릿, 위치, 0/90/180/270도 회전을 결정합니다.

## 먼저 읽을 문서

다른 PC의 Codex 검증 시작: [GitHub 키트·작업 지시](docs/autocad/OTHER-PC-CODEX-2026-10-07.md). [GUI-01 검증용 ZIP](https://github.com/jeonbyungryong/DWG-PDF-/releases/tag/windows-gui1-pc-validation-20261007)은 공식 릴리스가 아닌 타PC 수용 검증용 사전 배포입니다.

2026-10-07 현재 PC의 최신 GUI 검증은 [GUI-01 검증 인계](docs/autocad/GUI-01-HANDOFF-2026-10-07.md), CAD 회귀는 [GC-02 검증 인계](docs/autocad/GC-02-HANDOFF-2026-10-07.md), 다른 PC 검증 절차는 [검증 패키지 안내](docs/autocad/PC-VALIDATION-KIT-2026-10-07.md)를 따릅니다. 로컬 MAIN 통합과 GitHub 게시·공식 배포는 구분합니다. [통합·백업 기록](docs/releases/2026-10-07-local-main-integration.md)을 참조하세요.

후속 개발: [AutoCAD 확장 개발 허브](docs/autocad/README.md) — 소스 개발·검증 상태와 실행파일 배포 상태를 구분합니다. 현재 실행 파일의 AutoCAD 지원을 의미하지 않습니다.

최신 소스 색상 정책: 두 CAD 모두 `monochrome.ctb` 플롯을 유지하며,이에 의해 흑백으로 바뀌지 않는 색상은 허용합니다. 추가 RGB 보정은 하지 않습니다. [MC-02 검증·인계](docs/autocad/MC-02-HANDOFF-2026-10-06.md)를 참조하세요. 공식 실행파일 배포 및 AutoCAD 이번변경 실기는 별도입니다.

| 알고 싶은 내용 | 문서 |
| --- | --- |
| 다른 PC 설치와 실행 | [설치·실행 안내](docs/INSTALL-KO.md) |
| 사용 방법과 오류 처리 | [사용자 가이드](docs/USER_GUIDE_KO.md) |
| 현재 상태와 검증 범위 | [시험 보고서](docs/TEST_REPORT.md) |
| 성능 개선 및 남은 오류 | [성능 개선 보고서](docs/PERFORMANCE_REPORT_20261002.md) |
| 개발자가 소스를 실행·빌드하는 방법 | [개발 작업 안내](docs/DEVELOPMENT.md) |
| 전체 개발 자료 위치 | [문서 안내](docs/README.md) |
| 최초 사용자 개발 지침 | [REV02 개발 지침](docs/reference/CODEX_DWG_TO_PDF_개발지침_260715_REV02.md) |
| 배포 구성과 기준 버전 | [2026-10-02 배포 기록](docs/releases/2026-10-02-github-handoff.md) |
| 최신 성능 개선 배포 | [2026-10-02 네이티브 추출 배포 기록](docs/releases/2026-10-02-native-extraction.md) |

## 기존 공개 배포본 상태 요약 (2026-10-02)

2026-10-02 추가 성능 개선을 반영했습니다. CAD 내부에서 문자·블록·후보 기하를 일괄 추출하여 외부 COM 왕복 호출을 줄입니다. 기존 검증 경로와 원본 보호, 단일 APP 소유 CAD 운영은 유지합니다.

동일한 13개 템플릿 비교에서 파일 처리시간 중앙값은 **18.04초 → 3.12초, 약82.7% 감소**했습니다(CAD 시작/종료 제외). 13개 PDF의 축척·회전·출력영역(좌표오차≤1e-9)·144dpi 렌더 픽셀 일치를 확인했습니다. 공란/N/A·회전 파생30개도 모두 예상 축척·회전으로 변환됐습니다. 자동화 테스트는 660개 통과/10개 건너뜀입니다. PC/도면에 따라 처리시간은 달라집니다.

기존 90°/270° PDF 방향 오류와 Scale 공란/N/A 판정 오류를 수정했습니다. 화면 밖 도곽, 이동·회전 UCS, 다른 Layout 객체 혼입도 보완했습니다. 최종 EXE에서 정상7개 성공/비균일1개 예상 실패 후 계속 처리를 확인했습니다. 과거 고객 도면22개는 원본 경로가 없어 이번에 재시험하지 못했으며, 다른 PC 검증도 남아 있습니다. 자세한 내용은 [성능 개선 보고서](docs/PERFORMANCE_REPORT_20261002.md)를 참조하십시오.

## Windows 설치

1. [최신 배포 다운로드](https://github.com/jeonbyungryong/DWG-PDF-/releases/tag/windows-native-extraction-20261002) 또는 [배포 폴더](releases/windows/)에서 `dwg-to-pdf-validation.zip`을 받습니다.
2. 대상 PC에 정식 GstarCAD 2026을 설치하고 한 번 실행합니다. `DWG To PDF.pc3`, A4 297×210 mm 용지, `monochrome.ctb` 사용 가능 여부를 확인합니다.
3. ZIP을 로컬 폴더에 **전체 압축 해제**합니다. EXE와 `_internal` 폴더를 함께 유지합니다. Python 별도 설치는 필요하지 않습니다.
4. `dwg-to-pdf.exe`를 더블클릭해 입력 DWG/폴더와 출력 폴더를 선택합니다.
5. 먼저 대표 도면 1개를 변환해 도곽·방향·잘림·흑백 출력을 확인한 뒤 일괄 작업합니다.

GitHub의 **Download ZIP**은 소스 다운로드이며 실행 ZIP과 다릅니다. 자세한 절차는 [설치 안내](docs/INSTALL-KO.md)를 참조하세요.

## 기본 사용 흐름

EXE를 열고 입력 DWG/폴더 → PDF 출력 폴더 → 충돌 정책을 선택합니다. 완료 요약에서 실패 파일과 사유를 확인하고 출력 PDF를 검토합니다. 명령행 실행도 지원합니다.

`dwg-to-pdf.exe 입력폴더 --output 출력폴더 --conflict copy`

기본 `config.toml`은 strict calibrated matching을 활성화하며 `matching_threshold=1.0`, `minimum_score_gap=1.0`을 사용합니다. 설정·프로파일·원본 템플릿 위치를 바꿀 때는 `--config`, `--profiles`, `--template-source-root`를 명시합니다.

정상 batch는 one APP-owned GstarCAD session에서 모든 DWG를 순차 처리하고, 사용자가 미리 열어 둔 GstarCAD 프로세스는 종료하지 않습니다. 파일 하나가 실패해도 나머지 파일은 계속 처리합니다.

## 기존 고객 도면 검증 이력 (2026-07-20)

- canonical 13개 프로파일과 원본 템플릿 SHA-256 검증
- 두 실제 도면 집합 22개(기존 18개 + 신규 4개) 변환 성공, PDF 22개 모두 1페이지·비공백
- 원본 DWG SHA-256 및 수정시각 무변경
- 단일 APP 소유 PID 사용·종료 및 사용자 PID 보존
- 과거 문서의 `actual 6` gate를 22개 실제 사례로 확대 검증

22개는 현재 고객 도면 집합에 대한 validation 근거이며 독립적인 held-out calibration 집합은 아닙니다. production 배포 전 새 도면 표본과 clean-account 환경에서 추가 검증을 권장합니다. 자세한 내용은 [사용자 가이드](docs/USER_GUIDE_KO.md)와 [시험 보고서](docs/TEST_REPORT.md)를 참조하십시오.

## 자료와 백업

`src/`, `tests/`, `tools/`, `packaging/`에는 구현·검증·빌드 도구가 있습니다. `template_profiles/`에는 13개 프로파일과 기준 DWG를, `docs/`에는 요구사항·설계·계획·검증 자료를 보관합니다. 배포 ZIP과 SHA-256은 `releases/windows/`에 있습니다. 고객 작업 DWG와 변환 테스트 PDF는 포함하지 않습니다.

직전 main은 [backup/main-before-native-extraction-20261002](https://github.com/jeonbyungryong/DWG-PDF-/tree/backup/main-before-native-extraction-20261002)에 보존합니다. 기존 Release와 태그도 유지합니다.

## 꼭 지킬 사항

- `_internal`과 기준 템플릿을 삭제하거나 변경하지 마세요. 템플릿 해시가 달라지면 검증에서 거부됩니다.
- GstarCAD 설치 파일·라이선스·폰트는 별도 준비합니다. COM·PC3·CTB·폰트 환경 차이로 출력이 달라질 수 있습니다.
- 13개 승인 축척 외 도면은 지원하지 않습니다. Scale blank/N/A는 구조 비교를 사용합니다.
- `--self-check`는 런타임·프로파일 검사이며 실제 CAD 출력 성공을 보증하지 않습니다.
- 네이티브 추출은 동봉 LISP를 사용합니다. 사내 정책으로 LISP 실행이 제한되면 보안 설정을 낮추지 말고 `[matching]`의 `use_native_extraction=false`로 기존 COM 방식을 사용하십시오(느려질 수 있음).
