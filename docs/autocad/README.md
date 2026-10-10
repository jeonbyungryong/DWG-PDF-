# AutoCAD 확장 개발 허브

2026-10-10 최신: [AC09 공통 GUI 절차](AC09-STANDARD-GUI-2026-10-10.md). 사용자 현재 PC AutoCAD 개발완료 승인과 GUI 흐름 승인에 따라 실험적 표시·추가 확인을 제거하고 단일 설치/유효 설정을 자동 적용했다. 986 PASS/13 SKIP, 새 frozen 실행본 자체 점검·실제 탐색기 바로가기 파일7종/폴더7종·PDF/원본/복구 검증을 기록한다. GstarCAD 실기는 사용자 요청으로 연기했다. 아래 AC08의 사용자 승인 대기 표기는 이 후속 승인 기록으로 갱신된다.

2026-10-10 최신 후속: [AC08 기본 바로가기 자동 설정 검증](AC08-EXPLORER-AUTO-CONFIG-2026-10-10.md). 사용자 TOML 재선택 보고를 실제 탐색기 실행에서 재현했다. Codex의 AppData 가상화로 일반 사용자 캐시가 없었던 배포 문제를 복구했고, 원본 기본 바로가기 파일7종·완전 종료 후 폴더7종 모두 TOML 선택 없이 변환·완료창·PDF 검증 PASS. 제품 EXE·설정·PC3·바로가기 해시 유지. 사용자 새 후보 재수용·GstarCAD·다른 PC·MAIN 승인·정식 배포 게이트는 유지한다.

2026-10-09 이전 GUI 후속: [AC07 AutoCAD 설정 자동 적용](AC07-AUTO-CONFIG-2026-10-09.md). 이전 검증본의 사용자 실사용 수용 후 매번 TOML 선택을 생략하도록 개발했다. 당시979 PASS/13 SKIP, 로컬 새 실행본 준비. 사전 설정 전달 문제의 복구와 실제 GUI 검증은 위 AC08을 따른다.

2026-10-09 이전 후속: [AC04 조사·통합·배포 판단](AC04-INTEGRATION-2026-10-09.md), [AC03 현재 PC 검증](AC03-READINESS-2026-10-09.md). AutoCAD 수정 후보의 CLI43종·GUI각7·취소4·소스3시험 통과. 과거 DBMOD17→21 원인은 미확정이며 최신 GstarCAD 실기는 사용자 요청으로 연기했다. 사용자 요청에 따라 소스 통합과 검증용 prerelease를 진행하며 정식 stable Release·공식지원은 보류한다. 실제 원격 결과는 관리 이슈#1 AC04 인계를 따른다.

2026-10-07 PC-A 새 AC02 frozen 후보: GstarCAD43종 및 실제GUI 파일/폴더 각7개 검증 완료. 다른 PC는 [새 EXE·ZIP 전달 안내](AC02-FROZEN-OTHER-PC-2026-10-07.md)와 [검증 결과](AC02-PC-A-FROZEN-VALIDATION-2026-10-07.md)를 따른다. 전달 브랜치는 `codex/ac02-gstar-frozen-validation`이며 이전 GUI-01 실행본과 구분한다. AutoCAD 최종 실기·MAIN 병합·정식지원은 별도다.

2026-10-07 AC02 GitHub 인계: [다른 PC의 검증·이전 MAIN 복귀 안내](AC02-OTHER-PC-GITHUB-2026-10-07.md)를 따른다. 정확한 시험 SHA와 원격 복구 태그를 지정한 인계이며 타PC 수용은 대기다.

2026-10-07 AC02 추가 검증과 복구: 현재 PC AutoCAD2021 소스 OFF43/ON43·일반 실행파일43종·일반 GUI7종 및 원본/사용자 CAD 보호 통과. 최신 오프라인947 PASS/4 SKIP/9 CAD 별도. 우측 하단 표제란 겹침은 사용자 수용으로 무시. 과거 GUI E203 원인 미확정. [로컬 MAIN 복구·다른 PC 인계](AC02-MAIN-ROLLBACK-2026-10-07.md)를 우선 확인한다. 공식지원·타PC 수용·GitHub 게시 완료를 뜻하지 않는다.


2026-10-07 최신 상태: [GUI-01 검증 인계](GUI-01-HANDOFF-2026-10-07.md)에 현재 PC 선택 창 실기와 파일/폴더 입력 각7개 변환,931 PASS/13 SKIP을 정리했다. CAD 회귀는 [GC-02 검증 인계](GC-02-HANDOFF-2026-10-07.md), 후속 검증은 [다른 PC 검증 패키지](PC-VALIDATION-KIT-2026-10-07.md)를 따른다. 로컬 MAIN 병합과 GitHub 게시·공식 배포는 [통합 기록](../releases/2026-10-07-local-main-integration.md)에서 구분한다. G3/G5 미완료 표기는 전체 수용 게이트이며 완료한 현재 PC 시험을 NOT_RUN으로 되돌리는 뜻이 아니다.

2026-10-06 PC-A의 최신 COM 형상 재사용 개선과 검증은 [GC-01 인계](GC-01-HANDOFF-2026-10-06.md)를 따른다. 개발 브랜치 게시와 MAIN·실행파일 배포를 구분한다. 아래 AutoCAD 실기/지원 게이트는 별도다.

**현재 단계: G1 승인 / 로컬 MAIN 통합 / 현재 PC GUI·GstarCAD 검증 완료 / 이전 AutoCAD 2021 실기3 PASS / 최신 AutoCAD·타PC·공식 배포 게이트 미완료.**

2026-10-04 사용자는 현재 소스와 검증 자료의 MAIN 병합을 승인했다. [최신 인계·복구점](HANDOFF-2026-10-04.md), [원래 PC GstarCAD 회귀](../../tools/regression/gstarcad/README.md), [PC-B 실제 출력 증거](../../validation/autocad-2021-pc-b/README.md)를 따른다. 병합 후에도 G3/G5와 공식 지원은 미완료다.

원래 PC에서는 최신 MAIN을 별도 폴더에 내려받고 위 회귀 절차를 실행한다. 현재 배포 실행 파일은 GstarCAD용이며 새 소스 확장이 포함된 배포본이 아니다. 소스의 실험적 구현과 검증 상태는 [검증 현황](VALIDATION.md)을 참조한다.

PC-A의 당시 검토·수정은 [2026-10-04 회귀 기록](PC-A-REGRESSION-2026-10-04.md)에 보존한다. 당시 기본43종 통과 이후 색상 정책은 MC-02로 변경됐다. 현재 통합·검증 상태는 이 페이지 상단의 최신 기록을 우선한다.

2026-10-06 최신 사용자 결정은 **monochrome.ctb 플롯 유지/변환되지 않는 색상 허용/추가 RGB 보정 제거**다. [MC-02 적용·검증 인계](MC-02-HANDOFF-2026-10-06.md)를 따른다. 이전 [MC-01 보정 기록](MC-01-HANDOFF-2026-10-06.md)과 [완전 흑백 수정 명세](../superpowers/specs/2026-10-06-monochrome-amendment.md)는 역사적 기록이며 현재 색상 수용 기준이 아니다. CAD 내부 일괄 보정은 개발하지 않는다. GitHub 게시·공식 배포 및 이번 AutoCAD 실기 검증은 별도다.

소스 통합과 공식 지원 승인을 구분한다. AutoCAD 전용 플로터 복사본/설정과 검증 범위는 검증 현황의 추가 기록을 따른다.

| 자료 | 역할 |
|---|---|
| [기획·명세 REV01](../superpowers/specs/2026-10-02-autocad-support-design.md) | 범위,요구사항,설계 제안,검증/승인 게이트 |
| [흑백 보정 수정 명세 REV01](../superpowers/specs/2026-10-06-monochrome-amendment.md) | 역사적 기록; 현재 색상 기준은 MC-02이며 RGB 보정은 적용하지 않음 |
| [상세 구현 계획](../superpowers/plans/2026-10-02-autocad-support.md) | T1~T9 파일·인터페이스·실패시험·완료 기준 |
| [작업 로드맵](ROADMAP.md) | AC-00~07 산출물·의존성·완료 기준 |
| [PC 간 협업·인계](COLLABORATION.md) | 시작/동기화/소유권/PR/인계 규칙 |
| [개발 환경 준비](../DEVELOPMENT.md) | Python·의존성·현재 시험/빌드 절차 |
| [통합 관리 이슈 #1](https://github.com/jeonbyungryong/DWG-PDF-/issues/1) | 최신 담당·상태·승인·차단 사유·인계 SHA |

설계 문서는 Git으로 버전 관리하고, 최신 담당/진행/차단 사유는 [관리 이슈 #1](https://github.com/jeonbyungryong/DWG-PDF-/issues/1)에서 관리한다. 이슈 상태와 구현 PR 링크를 확인한 후 작업을 이어간다.

## 다음 결정

G1/Native 실행과 Antigravity 없는 직접 작업트리 방식은 승인되었다. 현재 PC 독립 검토·GstarCAD 회귀·GUI 검증 이후 남은 게이트는 최신 변경의 AutoCAD 실기,타PC 검증 및 공식 릴리스 승인이다. 다른 템플릿 양식 지원은 이번 범위에서 제외한다.

## 지원 상태 해석

- `EXPERIMENTAL`: 소스 개발 브랜치에서 명시 opt-in으로 사용하는 미검증 상태다. 공식 지원이 아니다.
- `NOT_RUN`: 실행하지 않음. PASS나 지원 완료가 아니다.
- `BLOCKED_ENVIRONMENT`: 실제 AutoCAD/라이선스/검증 PC가 없어 실기 단계 진행 불가.
- `VERIFIED`: 향후 특정 제품·버전·환경의 검증과 사용자 승인 근거가 갖춰진 경우에만 표시한다.
