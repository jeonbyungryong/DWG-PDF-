# Task 5 Report — Portable 13-Profile Registration and Recovery Verification

## 결론

중단됐던 Task 5 리뷰 수정사항을 보존한 상태에서 복구·검증했다. 기준 복구 커밋은
`8f7ca3d`, 최종 리뷰 수정 구현 커밋은 `8f16ec1`
(`fix: learn scale cells from measured grid geometry`)과 `5fbe788`
(`fix: isolate top-level scale grid geometry`)이다.

승인된 최상위 DWG 13개를 하나의 APP 소유 GstarCAD PID `9256`에서 순차적으로
read-only 등록했다. 생성된 프로파일은 정확히 13개이며, 원본 파일명만 저장하는 휴대형
프로파일, 명시적 `source_root` 해시 검증, 13-scale readiness gate를 모두 통과했다.
등록 종료 후 PID `9256`은 종료됐고 모든 원본 SHA-256과 `st_mtime_ns`는 등록 전후
동일했다. 사전 실행한 테스트 sentinel PID `11876`은 등록·실검증 동안 보존했으며 최종
정리에서 이 추적 PID만 종료했다. profile staging과 backup 디렉터리는 남아 있지 않았다.

생산 자동 승인 임계값은 추가하지 않았다. 구조 점수는 유한한 0–1 값만 제공하며 Task 8
보정 전까지 자동 승인을 활성화하지 않는다.

## 리뷰 지적사항 반영

- Scale 글자가 속한 블록 인스턴스의 실제 수평·수직 격자선에서 바로 아래 값 셀을
  측정하고, 그 셀 내부에는 유효 비율 객체가 정확히 하나만 있어야 한다. 다른 블록의
  교차 선분과 전역 근접 반경은 셀 결정에 사용하지 않는다.
- 최상위 Scale 라벨의 빈 `instance_path`는 와일드카드가 아니다. 최상위 라벨은 빈 경로의
  최상위 선분만 사용하고, 중첩 라벨은 기존처럼 정확히 해당 부모 블록 경로만 사용한다.
- 측정 셀은 기준 등록의 유일성 검증에만 사용한다. 런타임 탐지 좌표·허용치는 실제
  비율 문자의 삽입점과 bbox에서 저장하며, 유효 비율은 동일 축척 프로파일의 위치로
  확정해 다른 축척 위치의 일반 제목 문자와 충돌하지 않게 했다. 같은 셀의 물리 객체
  중복은 계속 `E304`이다.
- 프로파일 세트는 같은 부모에 일반 `Path.mkdir`로 생성한 sibling staging 디렉터리에서
  전부 검증한 뒤 디렉터리 단위로 교체한다. 부모 ACL을 상속하며, 새 세트 swap 실패 시
  이전 세트를 byte-identical하게 복구한다.
- rollback 성공 후 staging과 backup이 남지 않도록 정리한다.
- `scale_value_tolerance`는 실제 Scale 값 bbox에서, `position_tolerance`는 실제 선택 구조
  선분 길이에서 측정한다. A3 크기 기반의 임의 상수는 사용하지 않는다.
- 프로파일 JSON에는 `TEMPLETE_*.DWG` 파일명만 저장한다. 로드 시 명시적
  `source_root` 아래로 안전하게 해석하고 경로 이탈·절대경로·해시 변경을 거부한다.
- 곡률 bulge, elevation, 비평면 normal, 비유한 좌표가 있는 LWPOLYLINE을 직선으로
  오인하지 않고 `E303`으로 실패 처리한다. Elevation/Normal 속성이 없거나 getter가
  실패하는 경우도 기본값으로 대체하지 않고 `E303`이다.
- 실행 중인 `gcad.exe`가 없는 PowerShell의 정상 빈 결과는 빈 PID 집합으로 처리하되,
  stderr가 있는 실제 열거 실패는 계속 `E201`로 처리한다.
- 역전·비유한 reference Window는 계속 fail-closed이며 자동 정규화하지 않는다.

## 프로파일 및 검증 해시

| Scale | Profile JSON SHA-256 | Source DWG SHA-256 | Portable source | Position tolerance | Value tolerance |
|---|---|---|---|---:|---:|
| 1:100 | `D7203AFCBC391EF90A78488333596BF747ADCED5F3117E354AA5DE9311EFC9BE` | `F58283F20C16BBBC8FB10682CAE99B7AB26314B94748F489305C7F10C59B6A32` | `TEMPLETE_1대100.DWG` | `0.3` | `150` |
| 1:50 | `83FAA8B2DDFAD7A7EFA4D045D2C00888CF3E5938AEB16D9AC706D28BA678219A` | `4E0B38F20F1E600A59FD95BC776B98BC2ACCCE68FA0621013EE164001C7E80BF` | `TEMPLETE_1대50.DWG` | `0.15` | `75` |
| 1:20 | `891433E6E470EAB5907C15AF660F30F1954BFCE3E449DACB10407C6676241A63` | `03442D0391FCC3AF242A7B6F1CB8507EC7A4B171C303FCDBD7AB4E5E1909C297` | `TEMPLETE_1대20.DWG` | `0.06` | `30` |
| 1:10 | `2C8F531C127A7EFEF3E225E98D6FD7ED6CEF3112C7BFA0C4BB53D78FC471435A` | `DCC5B938173453CFA458F633D00064DF6C7F527AE79DB3B7126CF2E3487C6DBA` | `TEMPLETE_1대10.DWG` | `0.03` | `15` |
| 1:5 | `762A86DC0746F954B07CACA20476CDB324EDD2FA058E2720580F5BD1A110CF66` | `C5370EEA268414604E5A43B7C9810157A9A2925BF96EFCAC698D6ECA48FDBC16` | `TEMPLETE_1대5.DWG` | `0.015` | `7.4468085106382205` |
| 1:2 | `92D6755F33119322878AE69E01DCCB5091E0D117A20F183BDA0F0C5FF3F76104` | `F2BD4A5A4B8AC83787BD93E81CC8C40D8AEB0C57B149F95F5850D7F226B12E5F` | `TEMPLETE_1대2.DWG` | `0.006` | `2.9787234042553337` |
| 1:1 | `E3BFE4DD997C6FD5FAB72E54686BFAADF2C63857510627E0767273A91D203224` | `BEEBDF8F0D246CE623E637E7D1A4B3325199035B55DE7D1CC05EBE9D6A1BC281` | `TEMPLETE_1대1.DWG` | `0.003` | `1.1914893617021391` |
| 2:1 | `B500381BBCA457EAA9DDE3DA5362D0B48EACD8444A66D98C53F47C9786E0BB8C` | `29F1EAA99261D262653DB21B6483D336E7F0339D09F186D5D548CFE1E3906E88` | `TEMPLETE_2대1.DWG` | `0.0015` | `0.7446808510638334` |
| 5:1 | `A1A685A17A554B8304484F120998C424AF3309594C015BEA1E8518E3344BD1C8` | `00B5E797E3256C2FD7E53A14C3E49AFAEDC8FF37AF92E23BA7B4E974996A3F8C` | `TEMPLETE_5대1.DWG` | `0.0006` | `0.2978723404255348` |
| 10:1 | `14F6C77558C600AF0267F1AB3C30B2DB507731ED283E8013D43A1E53ABD09DAF` | `7DC8CFC49AE54E23EED10D391FDF539756679704A559252733C86A103999555B` | `TEMPLETE_10대1.DWG` | `0.0003` | `0.15` |
| 20:1 | `1BFD6F2AA19BD37F8088A42972E4F61AE1EAA6CF89B61F9B38612A1456FD7810` | `CDDF702592A56A3EC6339D6A6D2D0AA780A91B5561144D0B41DE31D703A46018` | `TEMPLETE_20대1.DWG` | `0.00015` | `0.075` |
| 50:1 | `0414186BFCDAFFC19632F80853302B3E1BF83BD4F580BDEA9E8EA1DA271A8D63` | `5A4D7E9BBB09897DAD4F74E73B84AD6D0A7C11DD8E39F7B7E3BCCA5CE420C2DD` | `TEMPLETE_50대1.DWG` | `0.00006` | `0.03` |
| 100:1 | `61A0C794423FB8DEEE2061C2F9D78F6779320EBAE7C033DF10CABBF50C242FF0` | `83673B33511C3B10F54295BA681C359FDEE6948B34A0259C98A8589ED2BB3C6A` | `TEMPLETE_100대1.DWG` | `0.00003` | `0.015` |

각 프로파일은 4개 frame-edge feature와 28개 title/asymmetric feature, 총 32개
구조 선분을 저장한다. source 경로의 절대경로 개수는 `0`이었다.

## TDD 및 자동시험 증거

- 최종 리뷰 집중시험(등록기·탐지기·등록 도구): `60 passed in 0.13s`.
- 최종 탐지기 단위시험: `47 passed in 0.09s`.
- 최종 전체 suite: `212 passed, 4 skipped in 0.83s`.
- atomic rollback/store 보존 집중시험: `2 passed in 0.12s`.
- staging 정리 회귀는 기존 구현에서 `assert not staging.exists()`가 실패하는 RED를
  확인한 뒤 정리 로직을 추가했고, GREEN `1 passed in 0.17s`를 확인했다.
- 격자 셀 내부의 비중첩 유효 비율 2개, 다른 블록 선분에 의한 5:1 셀 오판,
  LWPOLYLINE 속성 누락, ACL 상속 staging, 다른 축척 위치의 일반 문자 충돌을 각각
  RED로 재현한 뒤 수정했다.
- 최상위 Scale 라벨과 더 가까운 외부 중첩 블록 격자를 함께 둔 테스트에서 기존
  와일드카드 분기가 `E303`으로 실패하는 RED를 확인했다. 정확한 빈 경로 비교로 수정 후
  등록기 전체 `11 passed in 0.13s`를 확인했다.
- `git diff --check`는 whitespace 오류 없이 통과했다. CRLF 변환 안내만 있었다.

## 실제 GstarCAD 검증

### 13개 실제 등록

- 등록 전 기존 GstarCAD PID 집합: 테스트 sentinel `11876`.
- 한 APP 소유 PID: `9256`.
- 결과: records 13, profiles 13, approved scale universe readiness `True`.
- source SHA-256/mtime mismatch: `0`.
- 등록 종료 후 PID: sentinel `11876`만 유지, APP PID `9256` 종료.
- staging/backup count: `0`.

### 기존 사용자 PID 보존 경로

테스트가 직접 생성한 hidden sentinel PID `9172`를 사전 실행 상태로 두고 검증했다.
별도 APP 소유 PID `23072`에서 1:1, 1:50, 100:1 세 파일을 순차 처리했다.

- 실제 통합시험: `1 passed in 62.58s`.
- sentinel PID `9172`는 시험 중·후 유지됐다.
- APP 소유 PID `23072`만 종료됐다.
- 세 원본의 SHA-256/mtime은 모두 동일했다.
- 모든 검증 종료 후 테스트 소유 sentinel PID `9172`는 테스트가 종료했고, 최종
  `gcad.exe` 프로세스는 없다.

### 대표 구조 서명

등록된 1:1, 1:50, 100:1을 실제 bounded SelectionSet과 reached blocks만으로 검사했다.
세 프로파일 모두 exact score `1.0`을 만족했다.

- 실제 통합시험: `1 passed in 103.53s`.
- 원본 SHA-256/mtime 보존 및 APP 소유 PID 종료 assertion 통과.

### 실제 Scale 셀 탐지

등록된 1:1, 5:1, 100:1 도면에서 13개 프로파일을 동시에 제공한 상태로 내부 Scale
비율을 판정했다. 세 도면 모두 해당 파일의 기준 축척과 일치했고, 다른 프로파일 위치의
일반 문자는 값 객체로 오인하지 않았다.

- 실제 통합시험: `1 passed in 57.79s`.
- 원본 SHA-256/mtime 보존, APP 소유 PID 종료, sentinel 보존 assertion 통과.

### 최상위 경로 수정의 기존 프로필 영향 확인

대표 기준 1:1, 5:1, 100:1을 등록 로직으로 다시 추출해 확인했다. 세 도면의 Scale 라벨은
모두 중첩 경로 `('135', '12C', '112')`에 있어 수정된 최상위 전용 분기를 사용하지 않았다.
재생성한 세 프로필 데이터는 저장된 JSON과 정확히 동일했고 원본 SHA-256/mtime도 보존됐다.
따라서 13개 프로필 전체 재등록은 수행하지 않았으며, APP 소유 PID `23512`만 종료되고
테스트 sentinel은 유지됐다.

### 저장 Window 독립성

- window-learning 1:1: 계산 `420 × 297`, 저장 약 `148.082758621 × 98.317241379`.
- window-learning 1:50: 계산 `21000 × 14850`, 저장 약
  `37280.038146552 × 31994.978421336`.
- 실제 통합시험: `1 passed in 42.09s`.
- 두 원본 SHA-256/mtime 보존, APP 소유 PID `11364` 종료, sentinel 보존 assertion 통과.

## 확인된 환경 리스크

GstarCAD를 실행하지 않은 상태에서 COM 자동화 서버를 연속 재시작하는 과정 중 두 번,
`DispatchEx`가 약 120초 후 `server execution failed`로 종료됐다. 같은 시각 Windows System
로그에 `DistributedCOM` 이벤트 ID `10010`(서버가 제한시간 내 DCOM 등록 실패)이 남았다.
두 실패 모두 파일을 열기 전 발생했고, 실패 후 `gcad.exe`는 남지 않았다.

다음 clean 재시도에서는 빈 기존 PID 상태에서 실제 13개 등록이 성공했다. 또한 사전 실행
sentinel이 있는 경우 세 차례의 실제 COM 시험이 모두 성공했다. 따라서 프로파일/형상 오류가
아닌 GstarCAD 2026 자동화 서버의 간헐적 시작 환경 문제로 분류한다. Task 5에서 안전하지
않은 PID 추정·강제 종료나 무제한 재시도를 추가하지 않았다. 향후 배치 계층은 이 시작 실패를
`E201`으로 명확히 보고하고, 승인된 세션 복구 정책 범위에서만 제한적으로 재시도해야 한다.

## 남은 범위

- 실제 이동·회전된 held-out DWG 전체 세트의 false-approval 보정은 Task 8 범위다.
- production minimum score/gap은 아직 보정되지 않았으며 활성화하지 않는다.
- 결과는 이 PC의 GstarCAD 2026과 현재 승인된 13개 DWG에 한정된다.
