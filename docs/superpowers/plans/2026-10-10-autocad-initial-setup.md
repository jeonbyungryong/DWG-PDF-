# AC11 AutoCAD Initial Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 사용자 문서 승인 후 현재 담당자가 직접 구현하며, 마지막에 독립 검토를 한 번 수행한다.

**Goal:** 새 PC AutoCAD의 첫 실행과 재실행에서 TOML 선택 없이 기존 변환을 수행한다.

**Architecture:** 새 초기 설정 모듈이 기존 소유권 보호 세션·승인 템플릿 복사 경계·용지 검증을 재사용한다. GUI는 유효 캐시를 우선 사용하고, 없으면 생성한 설정을 기존 CLI에 전달한다. 기존 변환 엔진과 세션 정책은 변경하지 않는다.

**Tech Stack:** 기존 Python3.12 x64·pywin32·pytest·PyInstaller와 표준 라이브러리. 새 의존성 없음.

**Spec:** [기획·명세 REV1](../specs/2026-10-10-autocad-initial-setup-design.md).

## Global Constraints

- Windows x64, 정상 설치·라이선스·최초 초기화를 마친 일반 AutoCAD가 전제다.
- 기존 정책: 승인13종, A4 가로297×210mm, 크기 허용 오차0.20mm, monochrome.ctb, threshold/gap1.0, target saved window false.
- 사용자 CAD에 연결·쓰기·저장·종료하지 않는다. 동시에 존재하는 프로그램 소유 CAD 세션은 하나로 제한한다.
- 개인 설정·PC3·기존 출력·Release·백업을 덮어쓰거나 공개 업로드하지 않는다.
- 새 의존성·관리 화면·설치 서비스·세션/플롯 재설계 없음. GstarCAD 실기는 DEFERRED_USER.
- MAIN 병합·정식 Release 교체·기본 실행본 교체는 검증 결과를 제시한 뒤 추가 승인받는다.

## Review Focus

1. 한국어·공백·읽기 전용 설치 경로: 사용자 저장소에 생성하고 TOML 문자열을 안전하게 인코딩한다 → PART1.
2. PC3 중복 경로·변경 중 파일: 임의 선택/불안정 사본 사용을 거부한다 → PART1.
3. 변환 일부 실패·설정 저장 실패: 성공 캐시로 오인하지 않고 다음 실행에도 TOML을 요구하지 않는다 → PART2.
4. 프로그램 소유 세션의 종료 시차·남은 COM 참조: 정확한 프로세스 핸들로 종료를 확인한다 → PART3.
5. Codex와 일반 Explorer의 AppData 환경 차이: 실제 Explorer 실행과 종료 후 재실행으로 검증한다 → PART3.

---

## PART1: 초기 설정 모듈

권장 모델/추론: **GPT-6.1 Sol / High**. 제품 구현 승인 전에는 시작하지 않는다.

**Files:** 새 `src/dwg_to_pdf/autocad/initial_setup.py`, 새 `tests/unit/test_autocad_initial_setup.py`.

**Interfaces:**

- Consumes: `AutoCADSession(candidate)`, `SourceWorkspace(source)`, `session.working_document(workspace)`, `require_plot_environment(layout, preferred_names, tolerance_mm=0.20)`, `load_config(path)`, `default_profiles_path()`, `ProfileStore(directory, source_root=directory)`의 `load_all()`/`all()` 및 `require_canonical_profiles(profiles)`, 기존 `desktop_settings._settings_path()`.
- Produces: `prepare_autocad_config(candidate: CadCandidate) -> str` — 현지 검증·생성을 마친 TOML의 절대 경로. 오류는 기존 `AppError` 코드로 전달한다.
- Internal: `_inspect_plotter(candidate: CadCandidate) -> tuple[Path, str, str]` — PC3 원본 절대 경로, 조회 전후 일치한 SHA256, 실측 A4 이름. `_write_config(pc3_source: Path, pc3_sha256: str, media: str, candidate: CadCandidate) -> str` — 고유 사용자 폴더에 사본·TOML을 생성하고 재파싱한다.

- [x] 정상 생성, PC3/CTB 누락, 비-A4/NaN/복수 A4, 복수 PC3, 소유권 실패, 쓰기 오류, 원본 PC3 변경, 한국어/공백 경로, 기존 파일 보존 시험을 먼저 작성한다.
- [x] `pytest tests/unit/test_autocad_initial_setup.py -q --basetemp=<fresh>`로 RED를 확인한다. 실패는 미구현 계약 때문이어야 한다.
- [x] 명세4의 규칙을 구현한다. 실제 조회는 승인 프로파일의 해시 검증과 임시 사본 경계에서만 수행한다. JSON 문자열 인코딩으로 TOML 경로·용지 이름을 안전하게 작성한다.
- [x] 테스트에서 생성 결과를 실제 `load_config()`로 확인한다: provider/autocad, PC3 사본 절대 경로, 검증된 preferred media 하나, 고정 정책값. 원본·기존 설정 바이트 유지와 실패 시 생성 중 파일 정리를 검사한다.
- [x] 집중 GREEN을 확인하고 PART1 파일만 의미 단위로 커밋한다.

정상 생성 시험의 핵심 assertion (`candidate`, `pc3_source`, `media`는 검증된 모의 조회 fixture):

```python
def test_prepare_config_roundtrips_fixed_policy(candidate, pc3_source, media):
    before = pc3_source.read_bytes()
    config_path = Path(prepare_autocad_config(candidate))
    config = load_config(config_path)
    assert config.cad_provider == "autocad"
    assert config.prog_id == candidate.prog_id
    assert config.allow_experimental_autocad is True
    assert config.auto_match_enabled is True
    assert config.use_native_extraction is True
    assert (config.matching_threshold, config.minimum_score_gap) == (1.0, 1.0)
    assert (config.media_width_mm, config.media_height_mm) == (297.0, 210.0)
    assert config.style_sheet == "monochrome.ctb"
    assert config.preferred_media_names == (media,)
    assert config.autocad_pc3_path.is_absolute()
    assert config.autocad_pc3_path != pc3_source
    assert config.autocad_pc3_path.read_bytes() == before
    assert pc3_source.read_bytes() == before
```

실패 시험은 parameterize하여 기존 오류 코드를 그대로 검증한다: `test_missing_or_distinct_pc3_candidates_fail` → E210, `test_missing_ctb_fails` → E212, `test_invalid_or_ambiguous_a4_fails` → E211. `test_duplicate_paths_to_same_pc3_are_deduplicated`는 정상 생성한다. `test_pc3_change_during_preparation_is_rejected`와 `test_failed_write_removes_only_owned_partial_files`는 성공 반환/캐시 등록 없음 및 원본·기존 파일의 바이트/mtime 유지가 assertion이다. 기존 소유권 실패 코드도 그대로 전파한다.

## PART2: GUI 연결과 저장 정책

권장 모델/추론: **GPT-6.1 Sol / High**.

**Files:** `src/dwg_to_pdf/desktop_launcher.py`, `tests/unit/test_desktop_settings.py`, `tests/unit/test_cad_desktop.py`, `tests/unit/test_desktop_launcher.py`.

**Interfaces:**

- Consumes: PART1 `prepare_autocad_config(candidate) -> str`, 기존 캐시 조회·snapshot·성공 후 기억 API.
- Produces: 기존 `run_desktop(run_cli, ui=...) -> int` 계약 유지. CLI에는 기존 `--config <path>`를 전달한다.

- [x] 최초 실행에서 생성 함수를 한 번 호출하고 TOML picker를 호출하지 않는 시험을 먼저 작성한다. 재실행·별칭·복수 설치에서 유효 캐시는 생성 함수를 호출하지 않아야 한다.
- [x] 초기 준비 실패/취소는 CLI를 시작하지 않는지, GstarCAD는 준비 함수와 TOML picker를 호출하지 않는지 RED로 확인한다.
- [x] 기존 `cached_config or choose_autocad_config()`를 `cached_config or prepare_autocad_config(candidate)`로 연결한다. 사용하지 않는 AutoCAD TOML picker 계약·호출은 제거한다. 공통 입력/CAD/결과 UI는 유지한다.
- [x] 기존 전체 성공 후 기억과 전후 파일 지문 검증을 유지한다. exit1/2, 저장 실패, 변경/삭제/손상 설정의 시험은 '재선택' 대신 '다음 초기 준비'를 검증하도록 수정한다. CLI 수동 `--config`의 유효/불량 설정 회귀는 유지한다.
- [x] `pytest tests/unit/test_autocad_initial_setup.py tests/unit/test_desktop_settings.py tests/unit/test_cad_desktop.py tests/unit/test_desktop_launcher.py -q --basetemp=<fresh>` GREEN 후 PART2 파일만 커밋한다.

GUI 정상 시험은 기존 UI fixture의 TOML picker를 `pytest.fail("No TOML picker")`로 바꾸고, 준비 함수를 `generated_config` 반환 및 호출 기록으로 대체한다:

```python
def test_fresh_gui_prepares_once_then_reuses_successful_cache(setup):
    # setup: 빈 캐시·유일한 candidate·검증 가능한 generated_config·UI/호출 기록
    assert run_desktop(record_cli_success, ui=ui) == 0
    assert prepare_calls == [candidate]
    assert cli_calls[-1][-2:] == ["--config", generated_config]
    assert run_desktop(record_cli_success, ui=ui) == 0
    assert prepare_calls == [candidate]
    assert cli_calls[0] == cli_calls[1]
```

`test_failed_conversion_does_not_remember_generated_config`는 exit1/2에서 캐시 없음, 다음 실행의 준비 호출 증가를 검사한다. `test_preparation_failure_never_starts_cli`는 CLI 호출0/결과2, `test_cancel_before_preparation_does_not_start_cad`는 준비 호출0, `test_gstarcad_never_prepares_autocad_config`는 준비 호출0을 검사한다. 기존 cache-write-failure 시험은 현재 변환 결과 유지/다음 실행 자동 준비를 검사한다. 별칭·복수 설치·손상 캐시는 기존 시험을 수정해 같은 선택 규칙과 준비 호출 여부를 고정한다.

## PART3: 현재 PC 검증·후보 배포 준비

실행 권장 **GPT-6.1 Sol / High**, 최종 독립 검토 권장 **GPT-6 Astra / Xhigh**. 모델 권장은 실제 모델 변경을 의미하지 않는다. 구현은 현재 담당자가 직접 순차 수행하고, 추가 구현 워커를 만들지 않는다.

**Files:** `README.md`, `docs/INSTALL-KO.md`, `docs/USER_GUIDE_KO.md`, 새 `docs/autocad/AC11-INITIAL-SETUP-2026-10-10.md`. 필요 시 배포에 동봉하는 동일 안내를 갱신한다. private 원시 증거는 workspace 증거 폴더에만 저장한다.

**Interfaces:** 기존 PyInstaller spec·승인 번들 assets·검증 도구와 이전 Release/백업. CLI `--self-check`, `--list-cad` 계약 유지.

- [x] 전체 `pytest -q -ra --basetemp=<fresh>`를 실행하고 PASS/SKIP/NOT_RUN을 실제 원인별로 기록한다. baseline986/13을 새 결과로 재사용하지 않는다.
- [ ] 사전 API 시험의 종료 확인 실패를 먼저 분리 조사한다. 제품 종료 정책은 추측으로 수정하지 않는다. 소유 프로세스의 정확한 조회/동기화 핸들 대기와 읽기 전용 재확인으로 준비 세션 종료를 입증한다.
- [ ] 실제 AutoCAD에서 별도 새 사용자 저장소 조건의 초기 준비를 수행하고 PC3·TOML 지문, 임시 기준 DWG 보존, 세션 종료를 확인한다. 그 설정으로 대표 도면의 실제 PDF를 확인한다.
- [ ] 기존 spec·의존성으로 새 frozen 후보를 만든다. ZIP 전체 해시/CRC, 추출 self-check·설치 조회, 템플릿13종 해시를 검사한다.
- [ ] Explorer로 새 사용자 저장소 조건의 후보를 실행해 최초 TOML 선택 없이 실제 변환을 확인한다. 현재 사용자 캐시는 백업·복원하거나 별도 검증 사용자 환경으로 분리하며, Codex 가상화 저장소만 확인한 것을 실사용 증거로 삼지 않는다.
- [ ] 완전 종료 후 같은 실행 경로 재실행. 최초 설정 추가 준비 없이 변환, PDF A4/단일 페이지/비공백, 기존 기준 출력과 비교, 사용자 CAD/원본/기존 설정 보호, 소유 CAD 종료를 확인한다.
- [ ] 한국어 GitHub-only 사용 안내를 갱신하고 새 ZIP·체크섬·복구 백업을 준비한다. 타PC 실기가 없으면 NOT_RUN으로 표시하고 최초 실행·재실행 현지 확인 절차를 동봉한다.
- [ ] 구현 전체를 한 번 독립 검토하고 지적을 필요한 범위에서 수정·재검증한다. 추가 범위가 필요하면 승인받는다.
- [ ] 개발 브랜치 인계/PR과 구체적인 검증 결과·후보를 제시한다. **MAIN 병합·정식 Release 교체·기본 실행본 교체 승인**을 받은 뒤 해당 작업과 게시 후 다운로드 검증을 진행한다.

## 중단·추가 승인 조건

명세 밖 기능, 새 의존성, 타 CAD/버전 확대, 사용자 파일·CAD 환경 변경, 공유 세션/플롯/형상/보안/timeout 수정이 필요하면 이유·최소 변경·영향을 제시하고 승인을 받는다. 처음 제시한 짧은 설계 질문은 이 명세/계획 검토로 대체한다.

## 문서 자체 검토

명세3→PART2, 명세4→PART1/PART2, 명세6→PART3에 대응한다. Review Focus5항목의 시험을 해당 PART에 넣었다. 초기 API 시험 전체 PASS나 타PC 검증 완료를 주장하지 않는다. 제품 구현·배포 교체는 승인 전 미착수다.

## 실행 상태 — 2026-10-10

PART1 commit2a26507, PART2 commit2279280. 전체1003PASS/13SKIP42.45초; 최종 집중54PASS2.92초. 최초 현지 설정 생성/정확한 소유 CAD 종료 확인은 진행했으나 실제 변환이 PC3 뷰어 자동 열기 후 E421로 실패했다. 추가 이전설정 시험 E203도 별도 조사 중이다. [REV2 최소 보완 제안](../specs/2026-10-10-autocad-initial-setup-rev2.md) 승인 후 해당 계약만 수정한다. frozen GUI/ZIP/독립 최종 검토/MAIN/정식 배포는 아직 미완료.

원래 예외를 계측한 이전 설정 재실행은 실제 PDF 변환 PASS·원본15파일 SHA/mtime 보존·소유 CAD 잔류 없음이다. E203은 이번에는 재현되지 않아 최초 원인 미확정으로 기록하고 공유 세션을 수정하지 않는다. 최초 기본 PC3 자동 준비의 E421 실패와 구분한다.
