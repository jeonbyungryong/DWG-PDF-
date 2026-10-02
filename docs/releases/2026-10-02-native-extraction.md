# 2026-10-02 네이티브 추출 개선 배포

대상 저장소: https://github.com/jeonbyungryong/DWG-PDF-

사용자가 추가 개선의 main 업로드, 직전 main의 브랜치 백업, 나머지 브랜치 정리를 승인했다.

## 포함한 변경

- CAD 내부 LISP 일괄 추출 및 기존 기하 검증 재사용. 정상 Scale 입력의 COM 왕복 조회 축소.
- Scale 공란/N/A 구조 우선 판정, 회전 선분 끝점 오차 대응, 벡터 PDF 가로 방향 정규화.
- WCS 경계상자 및 현재 출력 Layout 소유 객체로 후보 제한. 다른 Layout·화면 밖 보기·이동/회전 UCS 영향 방지.
- 설정 `matching.use_native_extraction=false`로 기존 COM 경로 사용 가능. 보안 정책을 자동 변경하지 않음.
- 코드·테스트·진단 도구·사용자 문서·검증된 Windows 실행 ZIP 포함. 고객 DWG/파생 PDF/개인 설정은 추가 업로드하지 않음.

## 배포 파일

Release 태그: `windows-native-extraction-20261002`

파일: `releases/windows/dwg-to-pdf-validation.zip`

SHA-256: `E98EA569C8EE6F99184512E7DD589F3C6F25850149BE026836C7A44D1664C39D`

ZIP은 실제 검증한 로컬 배포본과 바이트 단위로 동일하다. ZIP 내부 문서의 로컬 검증본/미게시 문구는 제작 당시 상태이며, GitHub 게시 상태와 최신 안내는 저장소 README 및 이 배포 기록을 기준으로 한다. EXE와 `_internal`을 포함한 폴더 전체를 압축 해제해 사용한다. Python 별도 설치는 불필요하지만 GstarCAD 2026·라이선스·PC3·CTB는 대상 PC에 필요하다.

## 검증 근거

- 13개 기준 템플릿: 파일당 중앙값18.037초 →3.121초(82.70% 감소), CAD 시작/종료 제외.
- 13개 PDF: 축척·회전 동일, Window 오차≤1e-9,144dpi RGB 픽셀 동일.
- 공란/N/A·회전 파생30개: 모두 예상 축척·회전으로 변환 성공.
- 최종 EXE 실기: 정상7개 성공, 비균일1개 예상 실패 후 나머지 계속 처리. 총41.85초(CAD 시작/종료 포함).
- 원본 DWG 해시/mtime 보존, APP CAD 종료. 자기 검사와 ZIP CRC 검증 통과.
- 전체 소스 테스트660passed/10skipped. main 통합 트리에서도660passed/10skipped(24.80초)로 재확인했다.
- 고객 도면22개(D:원본 경로 없음), 다른 PC/clean-account 및 동시 사용자 CAD 실기는 이번 검증 NOT_RUN.
- 동기 COM 무응답을 강제 중단하는 watchdog은 별도 후속 범위.

## 백업과 브랜치 정리

- 직전 main: `bff5bdd2407d00c864bd73245c8a85f61f3f9ca7`
- 보존 브랜치: `backup/main-before-native-extraction-20261002`
- 정리 브랜치: `release/windows-20261002` (`2b81fc2a0292e1f276609bb4549fd905adfe2075`)
- 정리 전 해당 브랜치가 main의 조상이고 고유 미병합 커밋0개, 열린 PR0개임을 확인했다.
- main과 이번 백업은 유지하며 이전 Release 및 태그는 삭제하지 않는다. 다른 프로젝트 로컬 브랜치/작업트리는 정리 대상이 아니다.
