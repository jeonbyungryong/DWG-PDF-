# AutoCAD 확장 검증 현황

## 결론

2026-10-03 기준 **개발 브랜치 구현 / 실기·배포 미승인**이다. T1~T6의 오프라인 구현과 T7/T8 시험 장치를 준비했다. AutoCAD 지원 버전은 아직 없다. 기존 main/릴리스 ZIP은 변경하지 않는다.

## 확인된 사실

- 브랜치: `codex/autocad-support`, 기준 main: `de4bc247d7363c440d05aa5c949cc59df3e6f5ca`.
- T1 `00dc3cd`, T2 `5b5c18a`, T3 `365e547`, T4 `32d440c`, T5 `e3c579e`, T6 `de7fd03`.
- 2026-10-03 개발PC-A에서 `python -m dwg_to_pdf --self-check`: `RUNTIME_SELF_CHECK_OK`. CAD 기동 없이 검사했다.
- 읽기 전용 후보 탐지: GstarCAD, 파일 메타데이터 버전 `26.3.0.0`, ProgID 별칭 2개. **실제 COM 버전/라이선스/출력 호환성 증거가 아니다.** AutoCAD 후보 없음.
- 현재 세션에서 고객 도면이나 실제 CAD 출력은 실행하지 않았다. 사용자 소유 CAD 프로세스가 실행 중이지 않아 공존 조건을 충족하지 못했다.

## 검증표

| 게이트/제품 | 버전·커밋 | PC/표본 해시 | native | 명령/결과 | 사용자 검토 |
|---|---|---|---|---|---|
| G2 오프라인 | 위 T1~T6 및 시험 장치 변경 | 개발PC-A / 합성 자료, 기준13종은 기존 JSON의 source.sha256 검증 | on/off mock | `python -m pytest -q`: 756 PASS,10 SKIP (라이브 AutoCAD 3개 추가 전) | 코드 리뷰 별도 |
| G3 GstarCAD 실기 | COM 버전 미확인 / 현재 브랜치 | 승인13종+파생30개 실측 해시 미수집 | NOT_RUN | `python -m pytest -m gstarcad -q`: 6 SKIP. 게이트 미통과 | 사용자 CAD 공존 환경 필요 |
| G4 AutoCAD 실기 | 제품/에디션/버전 미확인 | 검증PC/표본 해시 미수집 | NOT_RUN | `python -m pytest -m autocad -q`: 3 SKIP. 환경 opt-in 없음 | AutoCAD 확보 후 출력 육안 검토 필요 |
| G5 frozen/다른 PC | 새 ZIP 없음 | 새 ZIP SHA256 없음 | NOT_RUN | G3/G4 선행 조건 미충족으로 새 빌드·배포 보류 | 별도 사용자 승인 필요 |

최종 오프라인 재검증과 리뷰 결과는 관리 이슈의 마지막 push SHA 인계가 기준이다. SKIP/모의 성공을 실제 CAD PASS로 간주하지 않는다.

## 분석·한계

- 기존13종의 판정·한도·원본 보호 계약을 공통화했다. 다른 템플릿 양식은 지원 범위가 아니다.
- AutoCAD의 명령·COM 유사성은 호환성을 보장하지 않는다. PC3/CTB/폰트/한글경로/LISP 보안 및 PDF 출력 방향을 실제 환경에서 확인해야 한다.
- 동기 COM 호출 자체를 중단하는 watchdog은 없다. 소유권 증명 실패 시 사용자 CAD 보호를 위해 `Visible`,문서열기,`Quit`,강제종료를 수행하지 않는다. 이때 신규 프로세스가 남으면 사용자가 확인 후 닫아야 한다.
- AutoCAD의 portrait/비정상 회전 PDF는 E420으로 거부한다. GstarCAD 전용 방향 보정을 적용하지 않는다.
- T8의 3개 라이브 시험은 원본/사용자PID 보호,13+30 및 native 비교,실패파일 이후 진행의 출발점이다. LISP 차단·출력잠금·폰트·흑백·선가중치 육안검토와 전체 G4 수용 항목을 모두 대체하지 않는다.
- `benchmark_conversion.py --config`는 이 확장 브랜치의 공통 경계를 대상으로 한다. 과거 제품 기준 측정은 해당 기준 커밋의 원래 harness와 같은 환경으로 별도 수행한다. `--probe-com` 시간은 순수 변환시간이 아니다.

## 다음 실행

1. 현재 개발 브랜치의 독립 코드 리뷰를 완료하고 중요 문제를 수정한다.
2. 사용자가 GstarCAD를 별도로 열고, 승인 표본·기존 파생자료 및 필수 환경변수를 준비한다. G3 필수시험/원본해시/mtime/사용자PID/APP 종료/native on·off/기준 성능을 검증한다.
3. G3 통과 후에만 실험 번들을 로컬 빌드하고 자체검사·실제 GstarCAD 변환을 시험한다. 기존 릴리스는 덮어쓰지 않는다.
4. 실제 Windows 일반 AutoCAD를 확보하여 G4를 수행한다. LT/수직제품이면 범위 변경을 먼저 검토한다.
5. 다른 PC에서 G5와 사용자 출력 검토를 마친 뒤 main 병합·배포 승인을 받는다.

## 근거/기준

[승인 명세](../superpowers/specs/2026-10-02-autocad-support-design.md), [구현 계획](../superpowers/plans/2026-10-02-autocad-support.md), 저장소 테스트의 실제 실행 출력, [관리 이슈 #1](https://github.com/jeonbyungryong/DWG-PDF-/issues/1)을 근거로 한다. 새로운 실측 성능 향상률이나 AutoCAD 지원 버전을 주장하지 않는다.
