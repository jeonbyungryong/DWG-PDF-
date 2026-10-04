# PC-A MAIN 검토 및 GstarCAD 회귀 — 2026-10-04

## 결론

PC-B의 MAIN 병합 및 AutoCAD 2021 실기 증거를 검토하고 원래 PC에서 후속 GstarCAD 검증을 수행했다. 기본 native 설정의 승인 43종 변환과 기대값은 통과했다. 배포 실패 전파와 명백한 비-DWG 사전 차단을 수정했다. 잔존 색상 수용/보정 판단과 나머지 회귀가 남아 G3 전체 및 G5 완료나 새로운 공식 릴리스를 주장하지 않는다.

## 확인된 사실

- 검토 기준 MAIN: `c951b818035ac6a06dce7b9a464cadb050bdc808`; 기존 작업을 보존한 전용 새 checkout.
- PC-B 근거: [관리 이슈 인계](https://github.com/jeonbyungryong/DWG-PDF-/issues/1#issuecomment-5978311541), [현재 PC-B 인계](HANDOFF-2026-10-04.md), [공개 증거](../../validation/autocad-2021-pc-b/README.md).
- PC-B는 AutoCAD 2021 실기 3 PASS, 86개 출력/기대값, OFF/ON 43쌍 픽셀 일치를 기록했다. 이는 PC-B의 결과이며 PC-A에서 AutoCAD를 실행한 결과가 아니다.
- PC-A 실제 공급자: GstarCAD 2026, `GStarCAD.Application.26`, COM Version `26.00`.
- 최종 변경 후 PC-A 오프라인: **841 PASS / 4 SKIP / 9 실기 제외**, 실패 0. 4 SKIP은 심볼릭 링크 생성 권한 제한이다.
- 런타임 자체검사: `RUNTIME_SELF_CHECK_OK`.
- 단일 도면 실기: **1 PASS**, native 추출 성공, 원본 hash/mtime 보존, 기존 CAD PID 보존, APP 소유 CAD 종료 확인.
- 수정 후 실패 격리 실기: **1 PASS**, 명백한 비-DWG는 E203 실패 후 같은 배치의 정상 도면 변환 성공; native 성공과 획득 CAD 종료 확인.
- 기본 native 설정 43종 benchmark: **43/43 변환 성공**, 전체 배치 **185.23초**. 원본 hash/mtime, 기존 CAD PID 보존 및 APP 소유 CAD 종료 확인.
- 별도 출력 감사: 43건 축척·회전·출력 창 기대값 일치(창 오차0.001 미만), 엄격 PDF 파싱·비암호화 단일 A4가로±0.2mm·Rotate0·비공백 확인. 완료된 OFF 출력17쌍과 ON 출력은144dpi 픽셀 동일.
- 43개 출력 모두 일부 컬러 선이 있어 엄격 완전 흑백 기준은 미충족. 이전 `a546c4f`와 동일 엔진·동일 설정의 1:1 샘플은 판정과144dpi 픽셀이 동일하여 그 샘플의 색상은 새 통합 회귀가 아님을 확인했다. 전체 이전 버전 비교로 확대 해석하지 않는다.
- 최초 제한된 실행의 COM 시작 실패 1건과 후속 실제 CAD 연동 실행 성공은 구분해 보존했다. 제한된 실행 실패는 제품 회귀로 단정하지 않는다.

## 수정 및 검증

| 항목 | 변경/근거 | 결과 |
|---|---|---|
| 배포 실패 전파 | `verify_bundle.ps1` 호출 직후 실행 성공/종료코드를 확인하고 실패 시 ZIP 생성 전에 중단 | 수정 전 2 FAIL/2 PASS → 수정 후 실제 검증기 누락 파일 사례 포함 6 PASS |
| PowerShell 호환 | 실제 `build.ps1 -File` 진입점, PowerShell 7.6.5와 Windows PowerShell 5.1 | 두 엔진의 정상/exit1/실제 누락 파일 실패 확인 |
| 독립 리뷰 | 배포 수정 및 시험의 읽기 전용 리뷰 | Critical/Important 없음; 실제 검증기 연동 시험 보강 권고 반영 |
| 이전 코드 비교 절차 | BEFORE는 이전 checkout의 benchmark 스크립트를 사용 | 새 검증 API 인자를 이전 코드에 전달하는 혼용 방지 |
| 명백한 비-DWG 차단 | 승인된 임시 복사본의 첫6바이트가 `AC`+ASCII숫자4개인지 Open 전에 검사 | 5개 실패 재현 → 읽기 오류/동일 세션 후속 입력 포함10 PASS, 실제 실패 격리1 PASS |

검증 실패 시 이번 실행에서 새 ZIP을 생성하거나 성공 표시를 하지 않는다. 이전 성공 빌드의 ZIP이 이미 있으면 그 파일은 보존될 수 있으므로 실패 로그 이후 기존 ZIP을 이번 빌드 산출물로 오해하지 않는다.

## 진행 중인 검증과 제한

- OFF 전체 회귀는17개 출력 후 빈 SCALE의 구조 판정 단계에서 오래 걸렸고, 색상 감사 차이가 확인되어 통제 중단했다. 이어진 손상 입력 Open 대기도 통제 중단했다. 해당 pytest 결과 **1 PASS/2 FAIL**은 의도적인 APP 소유 CAD 종료로 생긴 RPC 오류를 포함하므로 자연 완료나 제품 PASS로 기록하지 않는다. 최초 실패 증거를 보존하고 새 native43/실패격리 실행과 분리했다.
- 종료 대상은 각 시험에서 생성·소유 확인된 CAD만이며 PID·정확한 생성 시각·실행 파일을 재확인한 핸들로 종료했다. 최종 프로세스 조회에서 시험 전 기존 CAD2개만 남아 있음을 확인했다.
- GstarCAD 잔존 색상은 기존 출력 유지 수용 또는 임시 도면만 완전 흑백으로 보정할지 사용자 판단이 필요하다. 흑백 PASS나 전체 G3 PASS로 단정하지 않는다.
- 서명 검사는 명백한 비-DWG 차단일 뿐 무결성 검사/지원 버전 인증이 아니다. 정상 서명 뒤 손상된 파일의 modal/hang, 매우 오래된 비-`ACdddd` 형식 및 다른 PC AutoCAD의 변경 후 실기는 미검증이다.
- 원래 고객 도면 4개는 현재 지정 경로에 없다. 기존 실제 도면 release 시험을 일반 템플릿으로 바꿔 통과 처리하지 않는다.
- 전체 폰트·선굵기 사용자 육안 검토, 기존 특수 시험, 동일 엔진 전체 BEFORE/AFTER, frozen EXE 및 Python 없는 다른 PC의 G5는 완료되지 않았다.
- 현재 수정은 `codex/gstarcad-main-regression` 개발 브랜치에 게시했다. MAIN/기존 ZIP/릴리스는 변경하지 않았다.

## 실행 증거 위치와 재개 기준

원시 PC별 경로·로그는 로컬 ignored `.pytest-tmp`에 보존한다. 외부 게시에는 이 비식별 요약을 사용한다.

- `offline-publish-final.xml`: 최종 전체 오프라인 결과.
- `g3-single-20261004/gstar-live.xml`: 제한된 실행의 최초 실패.
- `g3-single2-20261004/gstar-live.xml`, 하위 `single-session.json` 및 `extraction-evidence.json`: 실제 단일 도면 성공.
- `g3-matrix-20261004`: 통제 중단한 OFF 및 손상 파일 시험 원시 증거.
- `g3-failure-fixed-20261004/gstar-live.xml`: 사전 차단 수정 후 실제 실패 격리 성공.
- `g3-native43-20261004.json`, `native43-audit.json`:43종 기본 경로 변환/기대값/색상/17쌍 비교 결과.
- `g3-before-one-20261004.json`, `before-one-comparison.json`:이전 버전 동일 샘플1개 비교.
- 재개 절차: [GstarCAD 회귀 README](../../tools/regression/gstarcad/README.md). 완료된 출력과 실패 로그를 보존하고 G3 검토 전 새 frozen 배포를 하지 않는다.

시그니처 근거: [ODA DWG 사양 §3.2.1](https://www.opendesign.com/files/guestdownloads/OpenDesign_Specification_for_.dwg_files.pdf), [Autodesk 버전 코드](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/drawing-version-codes-for-autocad.html), 2026-10-04 확인. 외부 코드/SDK를 복사하거나 설치하지 않았다.
