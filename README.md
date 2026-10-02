# DWG to PDF 자동변환 APP

등록된 13개 축척 템플릿을 기준으로 GstarCAD에서 DWG를 PDF로 변환하는 Windows APP입니다. 파일명에 축척이 없어도 도면 우측 하단의 `Scale` 라벨과 값으로 템플릿, 위치, 0/90/180/270도 회전을 결정합니다.

## 먼저 읽을 문서

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
| 최신 성능 개선 배포 | [2026-10-02 성능 개선 배포 기록](docs/releases/2026-10-02-performance.md) |

## 현재 상태 요약

2026-10-02 성능 개선을 반영했습니다. CAD 객체 종류·좌표·블록 이름의 중복 조회를 줄이고, 변환 탐색에서 미사용 문자 경계정보와 비문자 객체의 문자 속성 조회를 생략합니다. 선호 A4 용지는 실제 치수를 먼저 확인합니다. 등록용 데이터와 기존 기하 검증은 유지합니다.

동일한 3개 템플릿의 소스 실행 비교에서 파일 처리시간 중앙값은 22.44초에서 18.03초로 약 19.7% 감소했습니다(CAD 시작 제외). 승인 템플릿 13개 변환 성공, 비교 PDF의 축척·회전·출력영역·144dpi 렌더 일치를 확인했습니다. 자동화 테스트는 628개 통과/10개 건너뜀입니다. PC/도면에 따라 처리시간은 달라집니다.

주의: 추가 시험에서 90°/270° 회전은 E420, Scale 공란/N/A는 E304로 실패했습니다. 기존 배포 소스에서도 재현되는 미해결 오류입니다. 과거 고객 도면 22개는 원본 경로가 없어 이번에 재시험하지 못했습니다. 자세한 내용은 [성능 개선 보고서](docs/PERFORMANCE_REPORT_20261002.md)를 참조하십시오.

## Windows 설치

1. [성능 개선 배포 다운로드](https://github.com/jeonbyungryong/DWG-PDF-/releases/tag/windows-performance-20261002) 또는 [배포 폴더](releases/windows/)에서 `dwg-to-pdf-validation.zip`을 받습니다.
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

`src/`, `tests/`, `tools/`, `packaging/`에는 구현·검증·빌드 도구가 있습니다. `template_profiles/`에는 13개 프로파일과 기준 DWG를, `docs/`에는 요구사항·설계·계획·검증 자료를 보관합니다. `.superpowers/sdd/`의 기존 tracked 개발 보고서도 유지합니다. 배포 ZIP과 SHA-256은 `releases/windows/`에 있습니다. 고객 작업 DWG와 변환 테스트 PDF는 포함하지 않습니다. 이전 로컬 작업 브랜치는 보존합니다.

## 꼭 지킬 사항

- `_internal`과 기준 템플릿을 삭제하거나 변경하지 마세요. 템플릿 해시가 달라지면 검증에서 거부됩니다.
- GstarCAD 설치 파일·라이선스·폰트는 별도 준비합니다. COM·PC3·CTB·폰트 환경 차이로 출력이 달라질 수 있습니다.
- 13개 승인 축척 외 도면은 지원하지 않습니다. Scale blank/N/A는 구조 비교를 사용합니다.
- `--self-check`는 런타임·프로파일 검사이며 실제 CAD 출력 성공을 보증하지 않습니다.
