# AutoCAD 확장 개발 허브

**현재 단계: G1 승인 / 개발 브랜치 구현 / 두 번째 PC의 AutoCAD 2021 소스 통합 실기 3 PASS / G3·G5 및 배포 미완료.**

다른 PC에서는 `codex/autocad-support`와 관리 이슈의 마지막 push SHA를 확인한다. 현재 배포 실행 파일은 GstarCAD용이며 AutoCAD 지원 기능이 추가된 것이 아니다. 소스의 실험적 구현과 검증 상태는 [검증 현황](VALIDATION.md)을 참조한다.

2026-10-04 현재 PC에서 확인한 수정은 로컬 격리 브랜치 `codex/autocad-pc-validation`에 있다. GitHub 게시 또는 공식 지원 승인과 구분한다. AutoCAD 전용 플로터 복사본/설정과 검증 범위는 위 검증 현황의 추가 기록을 따른다.

| 자료 | 역할 |
|---|---|
| [기획·명세 REV01](../superpowers/specs/2026-10-02-autocad-support-design.md) | 범위,요구사항,설계 제안,검증/승인 게이트 |
| [상세 구현 계획](../superpowers/plans/2026-10-02-autocad-support.md) | T1~T9 파일·인터페이스·실패시험·완료 기준 |
| [작업 로드맵](ROADMAP.md) | AC-00~07 산출물·의존성·완료 기준 |
| [PC 간 협업·인계](COLLABORATION.md) | 시작/동기화/소유권/PR/인계 규칙 |
| [개발 환경 준비](../DEVELOPMENT.md) | Python·의존성·현재 시험/빌드 절차 |
| [통합 관리 이슈 #1](https://github.com/jeonbyungryong/DWG-PDF-/issues/1) | 최신 담당·상태·승인·차단 사유·인계 SHA |

설계 문서는 Git으로 버전 관리하고, 최신 담당/진행/차단 사유는 [관리 이슈 #1](https://github.com/jeonbyungryong/DWG-PDF-/issues/1)에서 관리한다. 이슈 상태와 구현 PR 링크를 확인한 후 작업을 이어간다.

## 다음 결정

G1/Native 실행과 Antigravity 없는 직접 작업트리 방식은 승인되었다. 다음 게이트는 독립 코드 리뷰 및 GstarCAD 실제 회귀다. AutoCAD 실기,타PC 검증,main 병합/릴리스 승인은 별도다. 다른 템플릿 양식 지원은 이번 범위에서 제외한다.

## 지원 상태 해석

- `EXPERIMENTAL`: 소스 개발 브랜치에서 명시 opt-in으로 사용하는 미검증 상태다. 공식 지원이 아니다.
- `NOT_RUN`: 실행하지 않음. PASS나 지원 완료가 아니다.
- `BLOCKED_ENVIRONMENT`: 실제 AutoCAD/라이선스/검증 PC가 없어 실기 단계 진행 불가.
- `VERIFIED`: 향후 특정 제품·버전·환경의 검증과 사용자 승인 근거가 갖춰진 경우에만 표시한다.
