# 다른 PC에서 이어서 개발하는 방법

## 공유 원칙

- GitHub main의 명세/로드맵이 설계 기준이다. 작업 상태·담당·다음 행동은 관리 이슈가 기준이다. 채팅 기억이나 PC별 메모를 기준으로 덮어쓰지 않는다.
- GitHub는 미저장 편집 내용을 실시간 동기화하지 않는다. **코드:commit/push/pull, 진행상태:이슈 업데이트**로 공유한다. 자동 동기화 서비스나 스케줄러는 이번에 만들지 않는다.
- 검토/재현/문서화와 제품 구현을 구분한다. G0 승인 전에는 명세 검토까지만, G0 승인 후에는 AC-01 상세 계획 작성까지 진행한다. 제품 구현은 G1 승인 후 시작한다.
- 이미 존재하는 `backup/main-before-native-extraction-20261002` 및 릴리스 태그를 보존한다. 다른 프로젝트·로컬 작업트리는 정리하지 않는다.

## 새 PC 시작 절차

```powershell
git clone https://github.com/jeonbyungryong/DWG-PDF-.git
cd DWG-PDF-
git status --short
git log -1 --oneline
```

기존 clone이면 먼저 `git status --short`를 확인한다. 변경이 없는 main에서만 `git pull --ff-only origin main`을 수행한다. 변경이 있으면 상태를 보고하고 별도 보존한다. 자동 reset/clean/stash로 작업을 숨기지 않는다.

1. [허브](README.md),명세,로드맵,루트 `AGENTS.md`,관리 이슈의 최근 인계 내용을 읽는다.
2. G0/G1 승인 여부와 작업 담당을 확인한다. 이슈가 closed라고 기능 전체가 승인됐다고 가정하지 않는다.
3. 작업을 맡기 전에 이슈에 작업ID·개발자/PC별명·브랜치·소유 파일·시작 기준SHA를 적는다. 담당 배정 충돌은 해소한 뒤 시작한다. 동시 요청이면 선착순을 추측하지 말고 조정한다.
4. 프로젝트 지침에 따라 `antigravity_prepare_worktree`로 만든 `agy/*` 격리 작업트리에서 구현한다. 다른 PC에 이 도구가 없으면 읽기/검토/문서 작업까지만 진행하고, 구현 환경 준비 또는 대체 작업 방식에 대한 사용자 승인을 받는다. 일반 branch 생성으로 이 규칙을 우회하지 않는다.
5. 원격 브랜치 이름은 작업ID와 목적을 포함한다(예:`agy/ac-02-cad-discovery`). 사람/PC가 바뀌어도 같은 작업의 브랜치를 이어받을 수 있게 한다.
6. Python3.12 x64와 의존성은 [개발 안내](../DEVELOPMENT.md)에 따라 준비한다. 설치 전 사용자 권한/네트워크 정책을 확인한다. 라이선스/토큰은 Git에 저장하지 않는다.
7. CAD 없는 시험은 아래 명령을 사용할 수 있다. AutoCAD가 없으면 실기 PASS를 기록하지 않는다.

```powershell
$env:PYTHONPATH = "$PWD\src"
$env:DWG_TO_PDF_TEMPLATE_SOURCE_ROOT = "$PWD\template_profiles"
.\.venv\Scripts\python.exe -m pytest -m 'not gstarcad'
```

위 명령은 현재 저장소 기준이다. 향후 AutoCAD 표식이 도입되면 해당 구현 PR에서 명령도 함께 갱신한다. 기존 `gstarcad` 외 표식을 현재 있다고 가정하지 않는다. 일부 pytest 통합 테스트는 모의 객체를 사용하므로 폴더 이름만으로 실기 시험이라고 판단하지 않는다.

## 충돌 방지와 인계

- 한 작업/공유 파일군에는 한 명의 활성 작성자만 둔다. 세션·설정·변환서비스처럼 겹치는 파일은 AC-01 계약을 먼저 확정하고 순차 통합한다.
- 작은 의미 단위로 커밋하고 작업 종료/PC 변경 전에 `git push -u origin HEAD`한다. push 실패 시 공유 완료로 보고하지 않는다.
- 미완료 코드는 작업 브랜치에 보관하고 이슈에 WIP와 실패한 테스트를 적는다. main으로 미검증 코드를 직접 밀지 않는다.
- 다른 PC는 인계 SHA를 fetch해 확인한다. 로컬 변경이 없을 때 작업 브랜치를 fast-forward로 동기화한다. 충돌은 작성자와 조정하며 force-push/rebase로 다른 사람의 이력을 임의 교체하지 않는다.
- 구현 변경은 PR로 검토하며 사용자 main 반영 승인 후 병합한다. PR에 작업ID·명세REV·테스트·NOT_RUN·위험을 포함한다. 이 문서 게시 승인은 향후 모든 구현 PR의 자동 병합 승인이 아니다.
- 정상 작업 완료는 테스트+리뷰+반영 증거가 있는 경우에만 표시한다. 소유자는 자리 이동/중단 시 상태를 PAUSED 또는 HANDOFF_READY로 바꾸고 다음 행동을 명시한다.

## 이슈 인계 템플릿

```text
작업ID:
상태: SPEC_REVIEW / READY / IN_PROGRESS / BLOCKED / REVIEW / DONE / HANDOFF_READY
담당/PC별명: (사용자명·개인경로 대신 비식별 별명)
명세REV / 기준 main SHA:
작업 브랜치 / 마지막 push SHA / PR:
소유 파일:
완료 내용:
검증 명령과 결과:
NOT_RUN과 사유:
남은 문제/다음 한 단계:
필요한 사용자 결정:
갱신 시각: ISO 8601, +09:00 또는 Z 명시
```

모의 테스트 성공·연결 성공·PDF 성공·타PC 성공은 서로 다른 결과다. 원시 고객 DWG/PDF,토큰,라이선스정보,절대 개인경로를 이슈/PR에 첨부하지 않는다. 실제 표본 공유가 필요하면 해당 파일과 업로드 위치에 대해 사용자 승인을 먼저 받는다.
