# 2026-10-02 성능 개선 배포

대상: https://github.com/jeonbyungryong/DWG-PDF-

기존 main의 설치·개발 안내와 13개 기준 템플릿을 유지하면서 성능 개선 코드, 테스트, 진단 도구, 보고서를 반영한다. 개발 작업트리의 변경 기준은 7fadde02이며 전용 저장소에 변경 커밋만 통합했다.

## 변경 결과

- 동일 3개 템플릿 파일 처리시간 중앙값 22.44초 → 18.03초, 19.7% 감소(CAD 시작 제외).
- 승인 템플릿 13/13 변환 성공.
- 비교 PDF의 축척·회전·출력영역 및 144dpi 렌더 픽셀 동일.
- 기존 90°/270° 회전 E420, Scale 공란/N/A E304 오류는 미해결. 기존 배포 소스에서 동일 재현.
- 이전 고객 도면 22개 및 다른 PC 재시험은 NOT_RUN.

## 실행 파일

releases/windows/dwg-to-pdf-validation.zip에 검증된 성능 개선 EXE와 런타임, 설정, 13개 프로파일·기준 DWG를 보관한다. ZIP 전체를 압축 해제해 사용한다.

ZIP SHA-256: B28A97FBB2D21302E722AB269C3003269DD14A9CB19B511855440FA3E5BF56B2

기존 windows-validation-20261002 배포는 과거 버전으로 보존하고 새 검증 배포는 windows-performance-20261002를 사용한다.

## 검증 근거

성능 개선 작업트리 전체 자동화 테스트는 628 passed, 10 skipped였다. 실제 frozen EXE의 1:1 변환은 종료코드 0, 1페이지 A4 가로·비공백 PDF, 원본 SHA-256/mtime 무변경, APP CAD 종료를 확인했다. 실패+성공 2개 파일 배치에서는 첫 파일 실패 후 다음 파일의 정상 변환을 확인했다.

통합 main 전체 자동화 테스트도 628 passed, 10 skipped(27.12초)로 통과했다. 배포 ZIP SHA-256은 검증된 로컬 ZIP과 동일하다. 세부 시험 범위와 한계는 [성능 개선 보고서](../PERFORMANCE_REPORT_20261002.md)와 [시험 보고서](../TEST_REPORT.md)를 참조한다.
