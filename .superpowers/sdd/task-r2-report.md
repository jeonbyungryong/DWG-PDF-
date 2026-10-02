# Task R2 Report — Scale Cell State and Closed 13-Profile Fallback

## 결론

Task R2의 상태 모델, 학습된 Scale 값 셀 기하 스키마/저장소 검증, 정확히 13개인
승인 축척 집합, scorer 주입형 구조 fallback 선택기를 구현했다. 실제 13개 기준 DWG의
등록과 구조 점수 산정은 계획대로 Task 5 범위에 남겼으며, 생산 보정값은 추가하지 않았다.

구현 커밋: `9225f70ed35d03279ea49c86e1ce6f8ba5b6b415`

## 구현 내용과 인터페이스 결정

- `ScaleCell(anchor, state, token, handle)`은 `valid`, `blank`, `na` 상태만 표현한다.
- `detect_scale_cell(document, limits, profiles)`은 서버 측 필터 SelectionSet과 기존의
  제한된 anonymous/nested block 탐색 결과만 사용한다. `Scale` 라벨은 정확히 하나여야 한다.
- 값 객체 위치는 프로파일의 `scale_value_offset`을 0/90/180/270도로 회전하여 계산한다.
  전역에서 임의 비율을 찾지 않으며 파일명이나 대상 도면의 저장 Plot Window를 읽지 않는다.
- 학습 위치에 객체가 없거나 빈 문자열이면 `blank`, trim/casefold 결과가 `n/a`이면 `na`,
  정상 비율이면 `valid`, 그 밖의 문자열은 `E305`다. 학습 위치에 여러 객체가 있으면
  `E304`로 닫힌다.
- `TemplateProfile` 및 JSON Schema에 `scale_value_offset`과 양의 유한
  `scale_value_tolerance`를 필수 필드로 추가했다. Boolean, NaN, Infinity, 0 이하 tolerance를
  `E308`로 거부한다.
- `ProfileStore.load_all()`의 기존 원자적 교체 성질을 보존해 reload 검증 실패 후에도 이전
  유효 store가 유지된다. `all()`은 불변 tuple snapshot을 반환한다.
- 계획 예시의 `ProfileStore.all()` 사전식 정렬은 승인 순서와 충돌하므로 적용하지 않았다.
  `structural_fallback`이 명시된 13개 키 순서로 입력을 정규화하며 누락, 중복, 미승인,
  범위 밖 프로파일을 `E300`으로 거부한다.
- 정상 Scale은 승인 집합에 포함된 프로파일 하나만 반환한다. 공란/N/A만 13개 전체를
  사용한다. 13개 키는 `1:1`, `1:2`, `1:5`, `1:10`, `1:20`, `1:50`, `1:100`,
  `2:1`, `5:1`, `10:1`, `20:1`, `50:1`, `100:1`로 닫혀 있다.
- `choose_profile_by_structure`는 보정값을 내장하지 않고 scorer와 임계값을 주입받는다.
  13개 각각의 4회전 후보를 평가하며, 임계값 미달만 `E310`, 동점/최소 gap 미달은
  `E304`, 잘못된 scorer 값/임계값은 안정된 엄격 오류로 유지한다.
- 기존 실제 COM 계약이 사용하는 `detect_scale_candidates()`는 호환용으로 유지했고,
  공통 bounded snapshot 수집만 공유한다.

## TDD RED/GREEN 증거

사용 런타임:
`C:\Users\dknbtech\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

테스트 의존성은 `requirements.lock`의 hash를 검증하여 워크트리 로컬 `.testdeps`에만
임시 설치했다. 최초 명령은 pytest 부재라는 환경 선행조건을 드러냈으며 RED로 세지 않았다.

- RED detector/fallback: 신규 테스트 수집에서 `ScaleCell`과 `detect_scale_cell` 부재로
  예상 ImportError가 발생했다.
- RED profile: `3 failed, 23 passed`; 새 필드가 기존 schema의 `additionalProperties: false`에
  의해 거부되고 `ProfileStore.all()`이 없는 상태를 확인했다.
- 최초 GREEN focused: `74 passed in 0.31s`.
- 독립 리뷰 후 RED: `8 failed, 74 passed`. 균일 2배/45도 block transform,
  attribute definition 중복, aggregate traversal limit, duplicate/out-of-universe store,
  잘못된 public valid token 사례가 예상대로 실패했다.
- 리뷰 수정 GREEN focused: `82 passed in 0.31s`.
- 최종 fresh GREEN full: `155 passed, 1 skipped in 0.60s`.

신규 테스트는 valid/blank/N/A/invalid, 라벨 0/2개, 네 회전의 학습 위치, 값 객체 다중,
비유한 offset/tolerance, 실패 reload 보존, 정확히 13개, 범위 밖/누락, 입력 순서 독립성,
동점, gap 부족, 저점수, 잘못된 scorer 값을 검증한다. 기존 테스트는 서버 측 SelectionSet,
bounded nested/anonymous traversal, 비균일/비유한 block transform 거부를 계속 검증한다.

## 실제 GstarCAD 2026 안전 회귀

기존 사용자 GstarCAD PID `10068`이 실행 중인 상태에서 opt-in COM 테스트를 실행했다.
리뷰 수정 후 별도 APP 소유 PID `30648`가 다음 정상 Scale 템플릿 3개를 한 번에 하나씩 read-only로
열고 닫았으며, 실행 중 동일 PID를 유지했다. 종료 후 APP 소유 PID만 사라지고 사용자
PID는 유지되었다. 결과는 `1 passed in 49.28s`다.

| 입력 | 실행 직전/후 동일 SHA-256 | 실행 직전/후 동일 mtime_ns |
|---|---|---:|
| `TEMPLETE_1대1.DWG` | `15F65A792E68FD3A079F8104DDCC2A19DB001CF200CE309F6D3BC8D8753EFEF0` | `1784163568833450800` |
| `TEMPLETE_1대50.DWG` | `A57715DD338BF99240481E2CA67A3F8E43CACDC5AE3E861E37B33D61B4A8FA85` | `1784163594158690400` |
| `TEMPLETE_5대1.DWG` | `00B5E797E3256C2FD7E53A14C3E49AFAEDC8FF37AF92E23BA7B4E974996A3F8C` | `1784108478235191000` |

이 회귀는 기존 정상 Scale/세션/원본 보호 계약의 비회귀 확인이다. 실제 13-profile store와
실제 구조 scorer가 아직 Task 5 범위이므로 새 fallback을 실도면으로 보정하거나 승인하는
시험은 수행하지 않았다.

## 리스크와 후속 범위

- fixture의 offset/tolerance는 합성 테스트 데이터이며 생산 승인 또는 보정값이 아니다.
- 실제 등록기는 각 기준 DWG에서 라벨 anchor와 값 객체 insertion point의 차이로 새 필드를
  계산해야 한다. 운영자에게 좌표를 숫자로 입력받아서는 안 된다.
- 실제 도곽/표제란 feature 추출, 13개 기준 프로파일 등록, `verify_rotation` scorer 및 임계값
  보정은 원래 Task 5에서 구현·검증해야 한다.
- blank/N/A 실제 작업 복사본과 out-of-universe 실제 회귀는 R4의 필수 승인 시험으로 남는다.

## Independent Review Follow-up

후속 수정 커밋은 `ca33ad4`다. definition Handle 중복을 막기 위해 root INSERT handle부터
이어지는 `instance_path`를 물리 객체 identity에 포함했고, 한 detector 호출이 공유하는
`TraversalBudget`이 모든 root, 방문 block definition, 스캔 entity(미반환 객체 포함)를 센다.
INSERT는 값 객체에서 제외한다. valid/blank/N/A 모두 canonical 13-profile readiness gate를
통과해야 하며, 잘못된 gap/scorer 결과·일반 예외는 E303, 실제 ambiguity만 E304다.
`SystemExit` 등 BaseException은 가리지 않는다.

- RED: `10 failed, 55 passed`
- focused GREEN: `65 passed`
- full GREEN: `166 passed, 1 skipped in 0.71s`
- 실제 COM: `1 passed in 48.81s`, owned PID `28360`, user PID `10068` 보존 및 원본 3개 불변

## 최종 검증

- 독립 코드 리뷰: 최초 High 2건/Medium 3건과 후속 Important 4건/Minor 1건을 모두
  RED 회귀로 재현한 뒤 수정했고, 최종 재검토에서 승인됐다.
- 실제 13개 프로파일의 설치 자체는 Task 5 범위이므로 store는 승인 축척의 부분집합을
  허용하되 중복/범위 밖 축척을 원자적으로 거부한다. 생산 선택 진입점은 valid·blank·N/A
  모두 정확한 canonical 13-profile readiness gate를 통과해야 한다.
- fresh full pytest: `166 passed, 1 skipped in 0.71s`.
- fresh real COM: `1 passed in 48.81s`.
- `git diff --check`: 최종 커밋 직전 재검증.
- 생성 cache와 `.testdeps`는 커밋에서 제외한다.
