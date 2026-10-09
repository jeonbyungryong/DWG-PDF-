# AC02 PC-A frozen EXE / GstarCAD validation — 2026-10-07

## 결론

AC02 수정 소스를 별도로 패키징한 새 EXE에서 GstarCAD 변환과 실제 GUI 검증이 통과했다. 제품 코드 수정 없이 기존 AC02 동작을 검증했다. 이 결과는 현재 PC / GstarCAD2026의 검증이며 AutoCAD 실기 검증이나 정식 배포 승인으로 확대 해석하지 않는다.

## 확인된 사실

| 항목 | 결과 | 근거 |
|---|---|---|
| 소스 기준 | c6bb03f8326aa854b753ba8631ec0d8ed11264b8 | 후보 HEAD, src/tests/packaging/config/template_profiles diff 없음 |
| 작업 브랜치 | codex/ac02-gstar-frozen-validation | 별도 후보 worktree |
| 오프라인 회귀 | 947 PASS / 4 SKIP / 9 CAD deselected; 35.27초 | frozen-offline.log / XML, exit0 |
| 새 빌드 | PASS | build.ps1 exit0, RUNTIME_SELF_CHECK_OK, VALIDATION_BUNDLE_OK |
| 새 EXE 43종 | 43/43 성공; 175.014초 | ac02-frozen43.log / results.json, exit0 |
| GUI 파일 다중 선택 | 실제7개 선택 / 7개 성공 / 완료 창 확인 | Computer Use, ac02-gui-files.json |
| GUI 폴더 입력 | 실제 입력·출력 폴더 선택 / 7개 성공 / 완료 창 확인 | Computer Use, ac02-gui-folder.json |
| GUI 경로 입력 | 입력·출력 주소 표시줄 정상 이동 | 한글·공백·괄호 포함 경로 직접 입력 |
| GUI 취소 | 파일 입력 / 폴더 입력 / 출력 폴더 각각 취소 후 창과 launcher 종료 | Computer Use 직접 관측 |
| PDF 구조 | 57/57 정상 단일 페이지, 비암호화, A4 가로, nonblank, /Rotate=0 | PDF 검사, strict PdfReader |
| 출력 비교 | 43종 source 기준과43/43, 실제 도면 이전 GUI 기준과14/14 픽셀 일치 | 전체 페이지144dpi RGB 크기·바이트 비교 |
| 원본 보호 | SHA256와 수정시간 유지 | 각 실행 전후 snapshot |
| 사용자 CAD 공존 | 기존 사용자 CAD 유지; 앱 전용 CAD만 종료 | 각 실행 중0.5초 간격 PID 관측 및 전후 상태; 식별자는 로컬 증거에만 보관 |

43종 배치는 개발용 PYTHONPATH 및 DWG_TO_PDF_TEMPLATE_SOURCE_ROOT를 제거한 자식 환경에서 실행했다. source43의 축척·회전·window 결정은 승인 manifest와43/43 일치한 기존 source audit를 확인하고, 새 frozen 출력의 전체 픽셀 동등성을 별도로 검사했다. frozen CLI의 내부 결정 trace를 새로 수집한 것은 아니다.

## 성능 측정의 범위

43종 배치 wall-clock은175.014초, 단순 평균4.070초/도면이다. 이는 CAD 시작·종료를 포함한 이43종 데이터의 측정값으로 모든 실제 도면의 처리시간을 보장하지 않는다.

GUI 파일 모드의 관측된 앱 소유 CAD 구간은36.682초, 폴더 모드는34.921초였다. 사용자 파일 선택·설정 시간은 제외되며 CLI wall-clock과 동일한 계측 구간은 아니다.

## 보호 범위와 한계

- 사용자 CAD PID 및 생성시각은 유지됐다. 사용자 CAD 안의 미저장 도면 메모리 전체를 비교한 것은 아니다. 사용자 CAD 창에는 입력 작업을 수행하지 않았다. 개인 프로세스 식별값은 공개 요약에서 제외했다.
- 취소 검증은43종 CLI 배치와 병행했다. 세 취소의 개별 PID 로그는 없지만 그 배치 전체에서 신규 CAD는 배치 소유1개만 관측됐으며, 취소한 GUI에서는 변환/완료 단계로 넘어가지 않았다.
- 허용된 잔존 색상과 기존 표제란 텍스트 중첩은 이번 판정의 실패 조건으로 추가하지 않았다.
- 유효 DWG 헤더를 가진 내부 손상 도면의 hang/watchdog, 전체43종 COM fallback 재실행 및 AutoCAD 실기는 이번 frozen/GUI 범위 밖이다.
- 이번 정상 GUI 두 실행에서 첫 도면 E203은 발생하지 않았다. 다른 PC에서의 과거 원인 미확정 현상이 모든 환경에서 해결됐다는 증거는 아니다.

## 산출물 식별

후보 worktree 기준:

- 실행: dist/dwg-to-pdf-validation/dwg-to-pdf.exe
- 다른 PC 전달용 전체 runtime: dist/dwg-to-pdf-validation.zip
- 파일 체크섬: dist/dwg-to-pdf-validation-checksums.csv
- EXE SHA256: 018A4759F3AEF130800D337E6F15FB3508A3811D1483E3CF4CEA6F75BAC1FB8E
- ZIP SHA256: AEEAAD610D5887071A06E011403E7AA26E9E2E23CF5CBA72E1B25837207C9BC2

EXE 단독 복사 대신 runtime 폴더 전체 또는 ZIP을 전달해야 한다. 실제 고객 도면 이름·PDF·원본·로컬 로그는 공개 자료에 포함하지 않는다.

## 유지한 상태 / 다음 단계

기존 MAIN30d6f23996035784154f3c306641488bcd2879bf와 기존 EXE SHA25609883ED375E8EFB43700B5B037BF5D012976666B5CD16AF188B86CCEC44DD85E는 유지됐다. Desktop 설치본 교체, GitHub 게시, MAIN 병합은 수행하지 않았다.

다음은 승인 시 검증 문서와 식별된 배포 후보를 GitHub 전달 체계에 반영하고, AutoCAD 설치 PC에서 동일 후보의 frozen43·실제GUI·사용자 CAD 공존을 최종 확인하는 것이다. 완료 뒤 양 CAD 결과와 최종 배포 체크리스트를 묶어 MAIN/Release 반영을 결정한다.

## 검증 기준 / 로컬 증거

기존 AC02 및 GUI-01 명세를 적용했다. 별도 기능 명세는 불필요하여 검증 계획만 추가했다.

- docs/superpowers/plans/2026-10-07-ac02-gstar-frozen-validation.md
- .pytest-tmp/frozen-offline.log / frozen-offline.xml / ac02-build.log
- .pytest-tmp/ac02-frozen43-results.json / ac02-frozen43.log
- .pytest-tmp/ac02-gui-files.json / ac02-gui-folder.json
- .pytest-tmp/gc2-native43.json.audit.json (source 단계 manifest 증거)
- 공식 Computer Use 실행에서 직접 관측한 각 선택·취소·완료 창

로컬 증거와 실제 도면은 공개 저장소 업로드 대상이 아니다. 위 내용은 검증 당시의 상태다. 이후 사용자 승인에 따른 게시 준비는 [새 frozen 후보 전달 안내](AC02-FROZEN-OTHER-PC-2026-10-07.md)를 따른다.
