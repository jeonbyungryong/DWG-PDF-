# DWG to PDF 시험 보고서

## 2026-10-02 성능 개선 검증

- 13개 승인 템플릿 실제 CAD 변환: 13/13 성공, 평균 파일 처리시간18.09초. 원본 SHA-256/mtime 동일, APP CAD 종료 확인.
- 같은3개 템플릿 기존/개선 비교: 파일당 중앙값22.44초 →18.03초(19.7% 감소), CAD 시작시간 제외. 단일 비교 배치 결과이며 대규모 업무 도면 속도를 보장하지 않음.
- 3개 비교 PDF: 축척·회전·출력영역 동일, Poppler144dpi RGB 렌더 픽셀 동일.
- 현재13종 실측 당시 사전 실행 사용자 CAD는 없었음. 사용자 PID 보호는 자동화 회귀 테스트로 확인하며, 아래 과거 실측과 구분함.
- 이전 고객 도면22개 및 다른 PC/clean-account 재시험은 NOT_RUN(원본D: 경로 없음).
- 등록 bbox, 모든 문자 값(공란/N/A/잘못된 값), 기하 오류 검증, 배치 오류 격리·원본 보호 계약 유지.
- 블록 정의 캐시는 대표 도면29개 정의가 각각1회만 방문되어 추가하지 않음.

### 추가 변형 시험 및 배포 실행 파일

- 전체 자동화 테스트: 628 passed, 10 skipped. 6개 opt-in CAD 테스트와 4개 플랫폼 의존 테스트는 건너뜀. 별도 실제 CAD 시험을 아래와 같이 수행함.
- 평행이동 및 180° 회전: 성공. 비균일 축척: 의도한 E303 실패.
- 90°/270° 회전: E420 실패. 실제 PDF가 A4 세로로 생성됨.
- Scale 공란/N/A: E304 실패. 여러 Scale 값 셀 후보가 검출됨.
- 위 4개 실패 입력은 기존 배포 소스에서도 동일하게 재현됨. 성능 변경 회귀는 아니지만 지원 요구사항의 미해결 오류임.
- frozen EXE: 비균일 축척 파일 실패 후 평행이동 파일 변환 성공, 정상 A4 가로 PDF 확인. 원본 SHA-256/mtime 무변경 및 APP CAD 종료 확인.
- 실행 파일 자체 검사: RUNTIME_SELF_CHECK_OK, VALIDATION_BUNDLE_OK.

상세 측정값·한계·후속 권고는 [성능 개선 보고서](PERFORMANCE_REPORT_20261002.md)를 참조하십시오.

아래는 2026-07-20에 완료된 과거 검증 기록이며 이번 실행 결과가 아닙니다.

## 결론

2026-07-20 두 실제 작업 도면 집합 22개(기존 18개 + 신규 4개)에 대해 자동 템플릿 선택과 PDF 변환이 22/22 성공했습니다. 최초 18개 전건 실패 원인은 배포 설정의 `auto_match_enabled=false`였으며, 이후 변형 주석 블록과 대량 중심표시 블록 처리 문제를 수정했습니다. 신규 4개 전건 실패는 새 DWG 레이아웃에서 Window 좌표보다 PlotType을 먼저 지정해 GstarCAD가 `Invalid input`을 반환한 것이 원인이었습니다.

## 확인된 사실

- 입력: 실제 DWG 22개(기존 회귀 집합 18개 + 신규 집합 4개)
- 성공/실패: 22/0
- PDF: 22개 모두 1페이지, 비공백
- 원본 보호: 변환 전후 SHA-256 및 수정시각 동일
- CAD 세션: one APP-owned PID만 사용 후 종료
- 사용자 CAD: 실행 전후 PID 5872 보존
- 설정: auto-match 활성화, threshold 1.0, score gap 1.0
- 과거 `actual 6` validation 범위를 실제 22개로 확대

## 반영한 수정

1. 유효한 Scale 값과 학습된 값 위치가 템플릿·회전을 유일하게 결정하면 전체 선분 구조 비교 없이 해당 템플릿 Plot Window를 계산합니다.
2. Scale이 blank/N/A이거나 회전 방향이 모호한 경우에는 기존 canonical-13 structural fallback을 유지합니다.
3. 비지원 변환 블록 안의 일반 주석은 Scale 탐색과 분리하되, Scale/N/A/축척비/빈 속성 후보가 있으면 fail-closed를 유지합니다.
4. 속성이 없는 SolidWorks 중심표시 블록을 Scale 및 도곽 구조 root 예산에서 제외했습니다.
5. 동일 윈도우의 기하 스냅샷을 도면 객체에 캐시했습니다.
6. 계산된 Window를 `SetWindowToPlot`으로 먼저 등록한 뒤 `PlotType=Window`를 지정하도록 순서를 변경해, 저장 플롯 모드가 다른 신규 DWG의 `Invalid input` 오류를 제거했습니다.

## 리스크와 한계

- 22개 실제 도면은 문제 재현 및 validation 집합이며 독립 held-out calibration 집합은 아닙니다.
- 13개 승인 축척 외 도면은 지원하지 않습니다.
- blank/N/A 구조 판정은 완전 일치 기준이므로 도곽 구조가 변형되면 해당 파일은 보수적으로 실패합니다.
- `SW_CENTERMARKSYMBOL_*` 예외는 속성이 없는 SolidWorks 중심표시 블록에만 적용됩니다.
- production 배포 전 신규 도면 표본과 clean-account 환경에서 재검증해야 합니다.

## 검증 기준

- 전체 자동화 테스트 통과
- frozen bundle `--self-check` 성공
- 13개 프로파일 JSON과 템플릿 DWG SHA-256 일치
- 실제 PDF page_count=1 및 nonblank=true
- 원본 SHA-256/mtime 불변, APP PID 종료, 사용자 PID 보존
