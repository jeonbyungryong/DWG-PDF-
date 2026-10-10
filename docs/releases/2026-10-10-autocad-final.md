# AutoCAD 최종 배포 — 2026-10-10

사용자가 현재 PC AutoCAD 최종 확인·통과와 GitHub Release·최종 배포를 승인했다. 이전 AC04/AC09의 정식 배포 대기는 이 승인 범위에서 갱신된다. GstarCAD 실기 연기는 유지하며,이전 DBMOD17→21 원인이 해결됐다는 주장이나 모든 PC/AutoCAD 버전의 검증 완료를 뜻하지 않는다.

Release: [windows-autocad-final-20261010](https://github.com/jeonbyungryong/DWG-PDF-/releases/tag/windows-autocad-final-20261010). Assets의 Windows 실행 ZIP으로 설치하며 [다른 PC 안내](../INSTALL-KO.md)를 따른다. PC별 설정·플로터는 대상 PC에서 처음 한 번 준비한다.

제품 기준 SHA는 `e86cfcf675c66e0a6ebf63b8d9e800b04bc0a6a0`(AC09)이다. EXE SHA256은 `F59D4D8A3881ED64236B3D9CFB003DB0E924752AC1E614A36821E1AA97419596`로 실제 GUI 검증본을 사용한다. 배포를 위해 README·설정 예시·설치 안내를 새로 동봉하며 제품 EXE·내장 Python 모듈·CAD DLL·13종 템플릿은 유지한다. Release의 체크섬과 `RELEASE-METADATA.json`을 최종 배포 지문으로 사용한다.

실기 근거는 [AC03](../autocad/AC03-READINESS-2026-10-09.md)과 [AC09](../autocad/AC09-STANDARD-GUI-2026-10-10.md)다. AC09 최신 pytest986 PASS/13 SKIP,실제 탐색기 기본 바로가기 파일7·폴더7,14개 PDF A4·비공백·픽셀 비교,원본 SHA/mtime와 기존 실행본·설정 보존을 확인했다. 배포 직전 전체 pytest와 ZIP 추출·self-check·재다운로드 해시는 관리 이슈 #1의 AC10 기록으로 인계한다.

배포에는 고객 도면/출력·개인경로·실사용 TOML·PC3·캐시·private 증거를 포함하지 않는다. canonical13종 기준DWG와 공개 설정 예시만 포함한다. 이전 Release·소스bundle·private 증거는 복구용으로 보존한다. MAIN 병합 SHA·Release 태그 SHA·게시 이후 재다운로드 검사 결과는 관리 이슈 #1과 Release metadata의 실제 기록을 기준으로 한다.
