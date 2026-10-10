# AC11 초기 설정 자동화 — REV2 최소 보완 제안

상태: **추가 명세 검토 대기 / 이 보완의 제품 구현 미착수**. 2026-10-10.

## 1. 확인된 문제

- REV1 구현의 단위/회귀 시험은1003 PASS/13 SKIP. 실제 현지 자동 준비는 PC3·CTB·실측 A4 조회와 정확한 소유 CAD 종료 확인을 지나 TOML 생성까지 수행했다.
- 그 설정으로 실제 변환했을 때 PDF가 Acrobat에 자동으로 열렸고 임시 파일 정리 E421로 실패했다. 전체 실기 PASS가 아니다.
- 기본 PC3 원본/자동 사본 SHA256은 `cdf9040f4e69c9189845e854f57b5b4eb1d29e354ec95cabd095e683215dd553`. 이전 현재 PC 검증 PC3는 `25951a9d0fe38910dc52f665ade57fa83500b82c4796656b135f705c8f5b8eb0`.
- 두 파일은 길이·checksum 검사를 통과하며, 압축 해제한 설정의 차이는 `View_New_File`의 TRUE→FALSE 하나다. 이전 실기용 사본도 이 변경으로 준비되었다.
- 이후 이전 설정으로 한 추가 시험은 문서 열기 E203으로 중단했다. 이번 A/B 실기 성공으로 기록하지 않는다. 원인 계측을 별도로 진행하고 공유 세션을 추측으로 수정하지 않는다.

Autodesk는 PC3 custom properties의 “Open in PDF viewer when done” 옵션이 출력 PDF의 뷰어 자동 열기를 제어함을 설명한다. [공식 안내](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/PDF-does-not-open-automatically-in-viewer.html). 이번 파일 잠금과 옵션의 관계는 위 현지 관찰 및 이전 사본 비교에 근거한다.

## 2. 추가 승인 대상

기존 신규 `initial_setup.py`의 생성 단계에서만 다음을 추가한다:

1. 원본 PC3의 해시·mtime 보존과 복사 원본 신원 확인은 유지한다.
2. 프로그램이 새로 만든 사본에서 **뷰어 자동 열기만 OFF**로 설정한다. PDF 용지·품질·레이어·폰트 등 다른 설정은 유지한다.
3. 현재 확인한 PC3 형식의 header·길이·checksum·압축 구조와 단일 설정 항목을 검사한다. 손상/불명확/지원하지 않는 형식은 E210으로 거부한다. 원본을 덮어쓰거나 불명확한 bytes를 임의 수정하지 않는다.
4. 원본과 생성 사본의 지문은 별도로 기록한다. 변경 뒤에는 사본=원본 SHA 일치를 요구하지 않고, 압축 해제 전후 설정에서 허용한 한 항목 외 차이가 없음을 확인한다. FALSE였으면 원본 bytes를 그대로 보존한다.
5. 기존 성공 후 설정 기억·사본 지문 검증, 오류 처리·CLI·공통 GUI는 유지한다.

새 의존성·공유 플롯/세션/형상/보안 정책·개인 CAD 환경 변경은 없다. 설치된 PC3·사용자 CAD·기존 TOML/PC3·출력·Release·백업을 보존한다.

## 3. 필요한 검증

- TRUE/FALSE, 누락·중복 항목, 손상 header/길이/checksum/압축, 변경 중 원본과 쓰기 실패의 RED→GREEN 시험. 바뀐 원본/사본 SHA assertion은 REV2 계약으로 갱신한다.
- 현지 기본 PC3에서 자동 준비 → 실제 PDF 변환 → 원본 SHA/mtime·승인 DWG 보호·소유 CAD 종료 확인. E203이 재현되면 상세 원인부터 분리하고 별도 변경 필요 여부를 판단한다.
- frozen GUI의 빈 저장소 최초 실행·완전 종료 후 재실행, PDF 구조/크기/비공백, 전체 회귀와 ZIP/백업·독립 검토는 기존 PART3을 그대로 완료한다.

REV1의 4.2 사본 해시 동일 조건과 PART1 관련 assertion만 이 승인으로 갱신한다. MAIN·정식 배포·기본 실행본 변경은 결과 제시 후 별도 승인 대상이다.
