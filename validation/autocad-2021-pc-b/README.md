# AutoCAD 2021 PC-B 검증 증거 — 2026-10-04

제품은 Windows 일반 AutoCAD 2021, 실제 COM 버전은 `24.0s (LMS Tech)`다.
86건 실기 행렬의 제품 코드 기준은 `4a62a384ea12c760106015605fd67c2f9e5a9916`다. 이후 MAIN 병합 전에는 CLI 선택 설정과 검증 도구를 보완하고 아래 추가 시험을 실행했다.

| 실행 | 결과 |
|---|---|
| 최종 병합 후보 관리자 전체 회귀 | **829 PASS / 9 SKIP**, 34.02초 |
| 실제 AutoCAD 통합 | **3 PASS**, 1696.80초 |
| 승인 13종 + 변형 30종, OFF/ON | **86 PDF / 86 기대 축척·회전·출력창 대조 PASS** |
| 추가 144dpi 렌더 비교 | OFF/ON **43쌍 동일** |
| 링크 4개 개별 시험 | **4 PASS / 0 SKIP**, 0.18초 |
| 변경 후 CLI 명시 CAD 선택 적용 | **1 성공 / 0 실패** |
| 변경 후 benchmark 및 진단 PDF 보존 옵션 | **1 성공 / 0 실패** |
| 변경 후 집중 회귀 / 독립 검토 집중 회귀 | **42 PASS / 35 PASS** |

9 SKIP는 GstarCAD 실기 6개(미설치)와 오프라인 AutoCAD 3개(별도 실기로 통과)다. 링크 4개는 시험 프로세스만 관리자 권한으로 실행했다. 영구 보안·권한 정책은 변경하지 않았다.

`evidence/`의 실제 XML·감사 JSON에서 호스트명과 개인 경로를 비식별화했다. `pdfs/off,on`에는 승인 도면에서 나온 최종 86개 출력이 있다. `previews/`에는 13종 접촉판 및 1:1 네 회전 표본이 있다. `checksums.json`으로 파일 무결성을 확인한다. 원본 hash/mtime와 사용자 CAD를 보존했으며, 작업용 CAD 종료 및 손상 DWG 이후 정상 파일 진행을 확인했다.

## 실패 기록과 한계

추가 benchmark 첫 실행은 문서 열기에서 COM 호출 거부 `-2147418111`로 E203이었다. 원본과 사용자 CAD는 유지됐고 작업용 PID는 종료됐다. 이 기록을 `main-merge-autocad-benchmark-busy-failed.json`에 보존했다. 같은 조건의 새 세션 재확인은 성공했으며 첫 실패를 PASS에 합산하지 않는다. CAD 변경 명령을 자동 재시도하지 않는다. 일시적인 COM busy가 파일 실패로 남을 수 있다.

최초 180도 방향 실패, PDF 뷰어 잠금, CTB를 우회하는 RGB, 속성 RGB 누락을 재현·수정했다. 중단용 출력 충돌 및 기본 pytest 임시 폴더 WinError5 실행도 최종 PASS에 합산하지 않았다.

AutoCAD ON은 SECURELOAD=1/미신뢰 LISP에서 COM fallback이었다. 직접 LISP 성공, GstarCAD 실기, 전체 폰트·선가중치 엔진 비교, frozen EXE 및 공식 지원·배포 승인은 미완료다. 현재 MAIN 병합은 원래 PC 회귀를 위한 사용자 승인이다.

## 설정

`plotter/DWG To PDF.pc3`는 자동 PDF 뷰어만 끈 전용 복사본이다. 설치 PC3를 덮어쓰지 않는다. `autocad.example.toml`의 절대 경로를 해당 PC의 저장소 경로로 바꾼다. 이 PC3는 GstarCAD 회귀에 사용하지 않는다.

수정 내용은 [검증 현황](../../docs/autocad/VALIDATION.md), 다음 실행은 [MAIN 인계](../../docs/autocad/HANDOFF-2026-10-04.md)를 따른다. 고객 도면·개인 원시 로그·토큰·라이선스 정보는 공개 증거에 포함하지 않는다.