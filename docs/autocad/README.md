# AutoCAD 확장 개발 허브

**현재 단계: 명세 REV01 검토 대기 / 제품 구현 미착수 / AutoCAD 실기 NOT_RUN.**

이번 게시물은 다른 PC에서도 동일한 설계와 상태를 확인하기 위한 개발 기준이다. 현재 배포 실행 파일은 GstarCAD용이며 AutoCAD 지원 기능이 추가된 것이 아니다.

| 자료 | 역할 |
|---|---|
| [기획·명세 REV01](../superpowers/specs/2026-10-02-autocad-support-design.md) | 범위,요구사항,설계 제안,검증/승인 게이트 |
| [작업 로드맵](ROADMAP.md) | AC-00~07 산출물·의존성·완료 기준 |
| [PC 간 협업·인계](COLLABORATION.md) | 시작/동기화/소유권/PR/인계 규칙 |
| [개발 환경 준비](../DEVELOPMENT.md) | Python·의존성·현재 시험/빌드 절차 |
| [통합 관리 이슈 #1](https://github.com/jeonbyungryong/DWG-PDF-/issues/1) | 최신 담당·상태·승인·차단 사유·인계 SHA |

설계 문서는 Git으로 버전 관리하고, 최신 담당/진행/차단 사유는 [관리 이슈 #1](https://github.com/jeonbyungryong/DWG-PDF-/issues/1)에서 관리한다. 이슈 상태와 구현 PR 링크를 확인한 후 작업을 이어간다.

## 다음 결정

사용자가 REV01을 검토/승인하면 정확한 파일·인터페이스·테스트를 포함한 상세 구현 계획(AC-01)을 작성한다. 그 계획의 실행 승인 전에는 제품 코드를 변경하지 않는다. 다른 템플릿 양식 지원은 이번 범위에서 제외한다.

## 지원 상태 해석

- `EXPERIMENTAL`: 향후 추가할 개발 검증용 상태이며 현재 구현되지 않았다.
- `NOT_RUN`: 실행하지 않음. PASS나 지원 완료가 아니다.
- `BLOCKED_ENVIRONMENT`: 실제 AutoCAD/라이선스/검증 PC가 없어 실기 단계 진행 불가.
- `VERIFIED`: 향후 특정 제품·버전·환경의 검증과 사용자 승인 근거가 갖춰진 경우에만 표시한다.
