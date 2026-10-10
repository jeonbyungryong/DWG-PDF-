# AC08-PC-B-EXPLORER-AUTO-CONFIG — 2026-10-10

상태: **현재 PC의 TOML 반복 선택 문제 복구 / 실제 기본 바로가기 GUI 검증 PASS / HANDOFF_READY**.

담당: Codex / PC-B. 기존 브랜치 `codex/autocad-auto-config-20261009`, Draft PR #4를 이어서 사용한다. 기준 소스 `bbb549ee30f5842c51f4bb54175e12fe3e6805c4`, MAIN `911c1919823d8758f6519e5025053bf446ec66b1`. 이번 소유 파일은 이 기록·허브·AC07 후속 안내다. 제품 Python 코드와 실행 파일은 변경하지 않았다.

## 원인과 복구

사용자가 새 기본 바로가기를 실행한 것이 맞았다. Computer Use로 탐색기에서 그 바로가기를 더블클릭하고 파일 입력을 선택하자 실제 TOML 선택창이 재현됐다.

직접 원인은 **탐색기 실행 환경에 사용자 설정 캐시가 없었던 것**이다. 원본 frozen 모듈을 그대로 보존한 비공개 진단본에서 일반 사용자 캐시 읽기 `FileNotFoundError`를 확보했다. 같은 논리 경로·설치 키의 조회가 Codex에서 성공한 것과 대조됐다. 캐시는 Codex 패키지의 `LocalCache/Local`에 존재했고, 실제 사용자 저장소에는 없었다. 사전 저장 및 같은 환경의 조회 성공을 사용자 배포 성공으로 판단한 검증이 부족했다.

이 차이는 [Microsoft의 MSIX AppData 가상화 설명](https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-behind-the-scenes#appdata-operations-on-windows-10-version-1903-and-later)과 일치한다. 새 AppData 파일은 패키지별 위치로 저장되고, 패키지 실행 환경에는 원래 경로에 있는 것처럼 보일 수 있다.

탐색기에서 실행한 비공개 도구가 두 AutoCAD 설치 별칭과 기존 정상 사용 TOML·PC3의 지문을 재확인한 뒤, 기존 제품 저장 API로 실제 사용자 설정을 저장했다. 두 후보 조회 및 캐시 SHA 일치가 확인됐다. 제품 EXE·바로가기·TOML·PC3·Windows 보안 정책은 유지했다. 이전 실행본과 백업도 보존했다. 도구는 설정 저장만 수행했으며 CAD를 시작하지 않았다.

## 실제 검증

| 검증 | 결과 |
|---|---|
| 복구 전 기본 바로가기·파일 입력 | 실제 TOML 선택창 재현 |
| 복구 후 같은 바로가기·파일 입력 | TOML 선택 없이 실제 AutoCAD 변환 **7/7 PASS**, 완료창 확인 |
| 완전 종료 후 같은 바로가기·폴더 입력 | TOML 선택 없이 실제 AutoCAD 변환 **7/7 PASS**, 완료창 확인 |
| PDF 구조·출력 | 각 7개 단일 페이지·비암호화·A4 가로·비어 있지 않은 출력 확인 |
| PDF 비교 | 두 탐색기 실행과 Codex 제어 실행의 7개 렌더링, **144dpi 픽셀 동일** |
| 원본 보호 | 승인된 시험 DWG7개 SHA256 전후 동일 |
| 전달본 무결성 | runtime259개 및 기존/현재 EXE·바로가기·설정·PC3 해시 유지 |
| 종료 | 완료 확인 후 변환기·AutoCAD·진단 도구가 남지 않음 |
| 집중 회귀 | `pytest tests/unit/test_desktop_settings.py tests/unit/test_desktop_launcher.py -q --tb=short --basetemp=<fresh workspace directory>`: **23 PASS, 0.26초, exit0** |

집중 회귀의 최초 sandbox 실행은 임시 폴더 생성 제한으로 8 PASS/15 fixture setup error였다. 새 전용 임시 경로의 정상 native Windows 실행을 위 PASS 근거로 사용했다. 제한·정책·경로 검증을 완화하지 않았다. AC07 전체979 PASS/13 SKIP은 과거 결과이며 AC08에서 전체를 다시 실행한 결과가 아니다.

이번 목적은 캐시 전달과 실제 실행 경로의 재현/복구다. 기존 승인7종으로 파일/폴더 경로를 각각 확인했으며 전체13종·43표본 회귀를 새로 수행한 것은 아니다. 실제 사용자 CAD가 열려 있지 않았으므로 공존 시험은 이번에 NOT_RUN이다. 최신 GstarCAD 실기는 사용자 지시대로 **DEFERRED_USER**. 이번 PASS는 Codex 실기 검증이며 새 후보의 사용자 재수용은 대기다. 다른 PC 수용·MAIN 반영·정식 stable Release·공식지원은 기존 게이트를 유지한다.

## 다음 PC 인계

설정 사전 배포 시 저장 프로세스와 사용자가 실제로 실행하는 프로세스의 환경을 확인한다. Codex 등 패키지 앱의 AppData 조회 성공만으로 일반 사용자 캐시가 존재한다고 판단하지 않는다. 최종 증거는 **탐색기에서 원본 기본 바로가기를 실행하고, 완전 종료 후 재실행해 TOML 생략과 실제 출력을 확인하는 것**이다.

다른 PC의 AutoCAD 플로터·용지·설치를 추측하지 않는다. 그 PC에서 정상 검증한 설정을 최초 선택하거나 동일 지문을 확인한 현지 설정만 사전 등록한다. 성공한 설정 저장 및 변경 시 재선택 기능은 유지된다. 개인 설정·절대 사용자 경로·고객 파일·PID·원시 진단 기록은 비공개 로컬 증거에만 보존한다.
