# CODEX 개발 지침서 - 로컬 DWG TO PDF 변환 프로그램

- 문서 목적: CODEX가 Windows 로컬 환경에서 동작하는 DWG → PDF 자동 변환 프로그램을 설계·개발·검증하도록 지시한다.
- 작성 기준일: 2026-07-15
- 문서 버전: Rev.02
- 목표 운영체제: Windows 10/11 64-bit
- 기준 CAD: GstarCAD Windows 버전
- 프로그램 형태: GUI 없는 콘솔형 로컬 실행 프로그램

## 변경 이력

| 버전 | 반영 내용 |
|---|---|
| Rev.01 | GstarCAD COM 기반 DWG→PDF 변환, A4 플롯 조건, 다중 템플릿, 파일 충돌 처리, 독립 실행 배포 구조 정의 |
| Rev.02 | 축척별 기준 템플릿 등록·매칭, 기준 DWG에 저장된 플롯 창 재사용, `1대1`·`2대1` 등 각각 축척별 파일명 축척 라벨 해석, 혼합 축척 도면 처리, GitHub 후보 기술의 채택·보류·제외 판단, 의존성 해시·라이선스·저우선순위 실행·파일 안정화 검증 추가 |

---

## 1. CODEX의 역할

CODEX는 다음 역할을 수행한다.

1. 사용자 요구사항을 임의로 확장하거나 축소하지 않는다.
2. 먼저 대상 PC와 기준 DWG를 조사하여 자동화 가능성을 검증한다.
3. GstarCAD의 화면 좌표를 클릭하거나 키보드 입력을 흉내 내는 GUI 매크로 방식보다 COM/API 기반 자동화를 우선한다.
4. 외부 서버, 클라우드, LLM, 텔레메트리, 온라인 파일 변환 서비스를 사용하지 않는다.
5. 원본 DWG를 손상하거나 사용자 작업 중인 GstarCAD 문서에 간섭하지 않는다.
6. 확인되지 않은 GstarCAD 객체명, COM ProgID, 플로터명, 용지의 Canonical Media Name을 추정하여 하드코딩하지 않는다.
7. 개발 전에 아래의 **Phase 0 사전 검증 보고서**를 작성하고 사용자의 승인을 받은 후 구현을 시작한다.

---

## 2. 최종 목표

사용자가 한 개 이상의 DWG 파일을 프로그램 실행 파일에 드래그하거나 콘솔에 파일 경로를 입력하면 다음 작업을 수행한다.

1. 매 실행 시 사용자가 지정한 출력 폴더에 PDF를 저장한다.
2. 사용자가 제공한 축척별 기준 템플릿 DWG를 로컬 템플릿 라이브러리에 등록한다.
3. 기준 템플릿 DWG에 이미 저장된 플롯 창 영역과 도곽 형상 정보를 축척별 프로파일로 저장한다.
4. 기준 템플릿 파일명의 `1대1`, `2대1`등등의 형식을 각각 `1:1`, `2:1`등등의 축척 라벨로 해석한다.
5. 변환 대상 DWG 안의 각 도곽을 기준 템플릿 프로파일과 비교하여 가장 일치하는 축척과 플롯 영역을 결정한다.
6. 템플릿이 한 개이면 PDF 한 개를 생성한다.
7. 템플릿이 두 개 이상이거나 서로 다른 축척의 템플릿이 혼재하면 템플릿별로 PDF를 각각 생성한다.
8. GstarCAD의 PDF 플롯 기능을 사용하고 지정된 플롯 조건을 정확히 적용한다.
9. 원본 DWG 파일명과 동일한 PDF 파일명을 우선 사용한다.
10. 기존 PDF와 충돌하지 않는 파일은 먼저 저장하고, 충돌 파일만 사용자에게 처리 방법을 묻는다.
11. 프로그램 종료 전 성공·실패·건너뜀·템플릿 매칭 결과를 콘솔과 로컬 로그로 제공한다.

---

## 3. 핵심 설계 결론

### 3.1 권장 자동화 방식

**권장안: 축척별 기준 템플릿 등록 엔진 + Python Windows 콘솔 프로그램 + GstarCAD COM 자동화 + pypdf 결과 검사 + PyInstaller 독립 실행 파일 배포**

권장 이유:

- GstarCAD 공식 개발자 자료는 COM, GRX, LISP, C/C++, VB/VBA, .NET 등을 지원한다고 명시한다.
- COM 자동화는 GstarCAD의 실제 플롯 엔진을 사용하므로 폰트, 선종류, 선가중치, CTB, 외부참조와 DWG 호환성 측면에서 별도 변환 엔진보다 유리하다.
- 기준 템플릿에 저장된 실제 플롯 창을 읽어 축척별 프로파일로 등록하면 도곽 크기가 달라도 사용자가 미리 조정한 출력 범위를 재사용할 수 있다.
- 템플릿 매칭은 외부 LLM이나 온라인 학습이 아니라 로컬의 결정론적 형상 프로파일 비교로 수행한다.
- 화면 클릭 방식이 아니므로 클래식/리본 UI 배치나 해상도에 대한 의존성을 줄일 수 있다.
- pypdf를 사용하면 생성 PDF의 페이지 수, 페이지 크기, 파싱 가능 여부를 로컬에서 확인할 수 있다.
- PyInstaller로 Python 인터프리터와 종속 모듈을 함께 묶으면 대상 PC에 Python을 별도로 설치할 필요가 없다.

### 3.2 금지하는 기본 방식

다음 방식은 기본 구현안으로 사용하지 않는다.

- 마우스 좌표 클릭, 키보드 매크로, 이미지 인식에 의존한 GstarCAD 조작
- AutoHotkey만을 이용한 플롯 자동화
- Windows 기본 PDF 프린터를 이용한 우회 출력
- 온라인 DWG 변환 서비스
- LibreCAD, FreeCAD 등으로 무조건 대체한 뒤 동일 출력이라고 가정하는 방식
- 원본 DWG를 직접 수정·저장하는 방식
- 플로터나 CTB가 없는데 임의의 대체 옵션으로 계속 진행하는 방식

### 3.3 무료 대체 프로그램에 대한 개발 원칙

현재 요구조건은 `DWG To PDF.pc3`, `monochrome.ctb`, 객체 선가중치, 플롯 스타일, 기준 창 영역 등 CAD 플롯 호환성이 중요하다. 영구 무료 프로그램이 동일 출력을 보장한다고 확인되지 않은 상태에서 무료 대안을 기본 채택하지 않는다.

GstarCAD는 공식적으로 30일 평가판을 제공하지만 상용/지속 사용은 라이선스가 필요하다. Stand-alone 라이선스는 설치 PC마다 필요하고 Network 라이선스는 동시 사용자 수 기준으로 운영된다.

따라서 개발 기본안은 **사용자 PC에 정상 설치·활성화된 GstarCAD를 활용**하는 것이다. 다른 CAD 또는 무료 프로그램을 검토할 때는 동일 DWG 샘플의 PDF 결과를 기준 출력과 픽셀/벡터 비교한 후 사용자 승인을 받아야 한다.

### 3.4 첨부 검토자료 및 GitHub 후보 기술 적용 판단

검토 기준일은 2026-07-15이다. GitHub 저장소의 README, 라이선스, 공개 릴리스 정보를 기준으로 판단하며 실제 회사 도면 검증 전에는 변환 정확도를 확정하지 않는다.

| 후보 | 확인된 내용 | 적용 판단 | 반영 범위 |
|---|---|---|---|
| `orcastor/cad2x-converter` | DWG/DXF→PDF·PNG·SVG·DXF CLI, Windows x64 바이너리 링크, 흑백·용지 맞춤·중앙 정렬·축척·코드페이지·폰트 옵션, LGPL-2.1. GitHub 정식 Release는 게시되지 않은 상태 | **조건부 보류** | 주 변환 엔진으로 교체하지 않는다. 임의 Plot Window와 `monochrome.ctb` 적용 옵션이 README에서 확인되지 않으므로 기준 출력 재현용으로 확정할 수 없다. 별도 PoC 또는 비상 진단용 후보로만 둔다. |
| `gorakhargosh/watchdog` | Windows `ReadDirectoryChangesW` 지원 파일 이벤트 감시 라이브러리, Apache-2.0 | **현재 MVP 제외 / 향후 적용 가능** | 현재 요구는 수동 드래그·경로 입력이므로 감시 폴더 기능을 기본 포함하지 않는다. 향후 자동 감시 기능 승인 시 파일 안정화 검사와 함께 적용한다. |
| `py-pdf/pypdf` | 순수 Python PDF 파서, 페이지 수·페이지 크기·메타데이터 확인 가능, 허용적 3-Clause 계열 라이선스 | **적용** | PDF 존재, 파싱, 페이지 수, A4 크기, 방향 확인에 사용한다. 빈 페이지·도면 객체 누락을 pypdf만으로 확정하지 않는다. |
| `pyinstaller/pyinstaller` | Python 인터프리터와 의존성을 폴더 또는 단일 실행 파일로 묶을 수 있으며 Windows 빌드는 Windows에서 수행 | **적용** | Python 자동 설치 대신 `onedir` 독립 실행 배포본을 기본으로 한다. |
| `LibreDWG/libredwg` | GPL-3.0, 모든 DWG 버전 읽기를 목표로 하지만 저장소 설명상 일부 고급 R2010+ 객체는 건너뛸 수 있음 | **주 경로 제외** | 외부 배포 라이선스와 객체 누락 위험이 있으므로 GstarCAD 플롯 대체 엔진으로 사용하지 않는다. 제한된 진단·연구용 PoC만 별도 승인 후 검토한다. |
| `mozman/ezdxf` | MIT, DXF 읽기·수정·쓰기와 PDF 렌더링 add-on 제공, DWG 직접 입력은 지원하지 않음 | **보조 진단용** | GstarCAD 또는 승인된 도구가 생성한 DXF를 분석하는 보조 경로에만 사용한다. DWG 직접 플롯 엔진으로 사용하지 않는다. |

#### 3.4.1 cad2x-converter를 주 변환 엔진으로 채택하지 않는 이유

`cad2x-converter`의 공개 README에서 다음 기능은 확인된다.

- DWG/DXF 입력
- PDF 출력
- A4 등 사용자 지정 용지 크기
- 자동 방향
- 흑백
- 용지 맞춤과 중앙 배치
- 출력 축척
- 코드페이지와 TTF/TTC 폰트 디렉터리

그러나 현재 프로젝트의 핵심 조건인 다음 항목은 공개 옵션에서 확인되지 않는다.

- 사용자가 기준 DWG에 저장해 둔 개별 Plot Window의 직접 재사용
- `monochrome.ctb`의 정확한 적용
- GstarCAD의 객체 선가중치·플롯 스타일과 동일한 처리
- 각 도곽을 형상 프로파일로 인식한 뒤 서로 다른 플롯 창을 적용하는 기능
- GstarCAD 전용 객체, Proxy 객체, Layout Viewport의 동일 재현

따라서 `cad2x-converter`는 무료·무창 실행이라는 장점은 인정하되, **출력 정확도 우선인 본 프로젝트에서는 GstarCAD COM 방식의 대체재가 아니라 비교용 PoC 후보**로만 유지한다.

#### 3.4.2 GitHub 바이너리 및 의존성 공급망 원칙

- 실행 중 GitHub에서 파일을 내려받지 않는다.
- 개발 시 승인된 버전 또는 Commit SHA를 고정한다.
- 외부 실행 파일과 Python wheel의 SHA-256을 기록한다.
- GitHub README에 연결된 사전 빌드 바이너리는 정식 Release가 아닐 수 있으므로 무검증 자동 배포하지 않는다.
- `THIRD_PARTY_NOTICES.md`, 라이선스 원문, 사용 버전, 출처, 해시를 배포본에 포함한다.
- 외부 배포 시 LGPL/GPL/Apache/MIT/3-Clause 계열 의무를 법무 또는 라이선스 담당자가 재검토한다.


---

## 4. 중요한 요구사항 해석 및 정정

### 4.1 Python 자동 설치 요구의 처리

사용자는 신규 PC에서 Python 등이 없으면 자동 설치되기를 요구했다. 그러나 프로그램의 외부 접속을 제한하면 온라인 자동 다운로드·설치는 서로 충돌한다.

따라서 다음 방식으로 구현한다.

- 배포본은 PyInstaller `onedir` 방식으로 우선 제작한다.
- Python 인터프리터와 필요한 Python 패키지를 배포본에 포함한다.
- 대상 PC에 Python이 없어도 실행되어야 한다.
- 프로그램이 Python을 시스템 전역에 설치하거나 PATH를 변경하지 않는다.
- `onefile`은 백신 오탐, 임시 압축 해제, 시작 지연이 발생할 수 있으므로 검증 완료 후 선택 옵션으로만 고려한다.
- GstarCAD는 라이선스와 관리자 권한이 관련되므로 프로그램이 임의로 자동 설치·활성화하지 않는다.
- GstarCAD 미설치 시 공식 설치 파일의 로컬 경로가 별도로 제공된 경우에만 오프라인 설치 보조 기능을 검토하며, 관리자 승인과 사용자 확인 없이 실행하지 않는다.

### 4.2 클래식 인터페이스 요구의 처리

COM/API 기반 구현에서는 클래식 UI의 버튼 위치를 사용하지 않으므로 클래식 인터페이스가 필수 조건이 아니다.

- COM/API 방식이 정상 동작하면 UI 모드와 무관하게 개발한다.
- COM/API가 불가능하여 명령 스크립트 방식을 사용해야 할 때만 클래식 인터페이스를 기준으로 한다.
- 화면 클릭 방식은 최후의 수단이며 별도 승인 없이 사용하지 않는다.

### 4.3 원본 DWG 보존

`Save Changes to Layout`에 해당하는 플롯 설정은 **임시 작업용 DWG 복사본**에 적용하고 저장한다.

- 원본 DWG는 읽기 전용으로 취급한다.
- 임시 작업 폴더에 DWG를 복사한다.
- 임시 복사본의 레이아웃/모델 설정에 플롯 변경 사항을 저장한다.
- PDF 생성 완료 후 임시 DWG와 관련 임시 파일을 정리한다.
- 비정상 종료 시 다음 실행에서 오래된 임시 폴더를 정리한다.

### 4.4 축척별 템플릿 ‘학습’의 정확한 의미

본 프로젝트에서 ‘학습’은 LLM, 클라우드 AI 또는 확률적 머신러닝 모델을 의미하지 않는다. 다음의 **로컬 기준 템플릿 등록 및 형상 프로파일 매칭**을 의미한다.

1. 사용자가 축척별 기준 템플릿 DWG를 제공한다.
2. 기준 템플릿에는 사용자가 각 축척과 도곽 비율에 맞춰 Plot Window를 미리 저장해 둔다.
3. 프로그램은 기준 DWG에서 저장된 Plot Window, 도곽 형상, 블록·레이어·엔티티 구성을 읽는다.
4. 위치와 절대 크기에 영향을 덜 받도록 형상을 정규화한 프로파일을 로컬 파일로 저장한다.
5. 변환 대상 DWG의 각 도곽 후보를 기준 프로파일과 비교한다.
6. 일치한 프로파일의 저장된 Plot Window를 대상 도곽의 위치·회전·균일 축척에 맞게 변환하여 플롯한다.
7. 일치도가 기준 미만이거나 두 후보가 비슷하면 자동 추정하지 않고 해당 도곽을 보류한다.

기준 템플릿 파일명의 기본 규칙은 다음과 같다.

```text
1대1.dwg  → scale_label = "1대1", scale_ratio = 1:1
2대1.dwg  → scale_label = "2대1", scale_ratio = 2:1
```

파일명에서 확장자를 제거하고 공백을 정리한 후 다음 기본 패턴으로 해석한다.

```regex
^(?P<numerator>\d+(?:\.\d+)?)대(?P<denominator>\d+(?:\.\d+)?)$
```

중요 구분:

- `1대1`, `2대1`은 **기준 템플릿 프로파일의 축척 라벨**이다.
- 이 라벨을 최종 PDF 파일명에 임의로 추가하지 않는다.
- 최종 PDF 파일명은 기존 요구대로 원본 DWG 파일명을 기준으로 한다.
- 동일 축척의 서로 다른 도곽 형식이 필요하면 사용자의 승인 후 별도 명명 규칙과 명시적 매핑 파일을 추가한다.


---

## 5. Phase 0 - 구현 전 필수 사전 검증

CODEX는 소스코드를 작성하기 전에 아래 항목을 조사하고 `PHASE_0_FEASIBILITY_REPORT.md`로 보고한다. 사용자의 승인 전에는 본 구현을 시작하지 않는다.

### 5.1 대상 PC 조사

- Windows 버전 및 64-bit 여부
- 설치된 GstarCAD 정확한 제품명, 연도 버전, Edition
- 설치 경로
- 라이선스 활성화 상태
- 다중 인스턴스 실행 가능 여부
- GstarCAD가 이미 실행 중일 때 새 COM 인스턴스 생성 가능 여부
- 사용 가능한 COM ProgID 목록
- `DispatchEx` 또는 동등한 별도 인스턴스 생성 가능 여부
- 설치된 PDF 플로터 목록
- `DWG To PDF.pc3`의 정확한 존재 여부
- 설치된 Plot Style Table 목록
- `monochrome.ctb`의 정확한 존재 여부와 실제 경로
- A4 가로 용지의 표시 이름과 Canonical Media Name
- GstarCAD 언어가 한국어/영어일 때 플로터·용지 이름 차이

### 5.2 샘플 파일 조사

사용자에게 다음 자료를 받아 분석한다.

1. 축척별 기준 템플릿 원본 DWG
   - 예: `1대1.dwg`, `2대1.dwg`
   - 각 파일에는 사용자가 조정 완료한 Plot Window가 저장되어 있어야 한다.
2. 각 기준 템플릿을 GstarCAD에서 수동 출력한 기준 PDF
3. 템플릿이 한 개 포함된 실제 DWG
4. 동일 축척 템플릿이 두 개 이상 포함된 실제 DWG
5. `1:1`, `2:1` 등 서로 다른 축척의 템플릿이 한 DWG에 혼재한 실제 DWG
6. 템플릿 위치가 이동된 DWG
7. 템플릿이 회전되거나 균일 확대·축소된 DWG
8. 레이어 표시·동결 상태가 다른 DWG
9. 외부참조·폰트·이미지·해치·동적 블록·Proxy 객체가 포함된 대표 DWG
10. 잘못된 템플릿 또는 등록되지 않은 축척이 포함된 실패 검증용 DWG

### 5.3 축척별 기준 템플릿 등록 및 식별 규칙 확정

기준 템플릿의 절대 크기는 축척별로 다르므로 단순 폭·높이만으로 템플릿을 결정하지 않는다. 사용자가 제공한 기준 DWG를 먼저 등록하고, 저장된 플롯 영역과 도곽 형상을 함께 프로파일링한다.

#### 5.3.1 기준 템플릿 등록 순서

1. 파일명에서 `1대1`, `2대1` 등의 축척 라벨을 해석한다.
2. 원본 기준 DWG의 SHA-256과 수정일을 기록한다.
3. 임시 복사본을 GstarCAD 전용 세션에서 연다.
4. 기준 도면의 활성 Layout 또는 합의된 Model 탭을 확인한다.
5. 저장된 플롯 형식이 Window인지 확인한다.
6. 저장된 Plot Window 좌하단·우상단 좌표를 읽는다.
7. 용지, 방향, Fit to Paper, Center Plot, CTB, 선가중치 옵션을 검사한다.
8. Plot Window 내부와 경계 주변의 도곽 형상을 추출한다.
9. 형상 특징을 위치·크기 정규화하여 프로파일을 생성한다.
10. 등록 결과와 미리보기 PDF를 기준 PDF와 비교한다.
11. 사용자가 승인한 프로파일만 운영 라이브러리에 반영한다.

저장된 Plot Window를 COM/API로 읽을 수 없는 GstarCAD 버전에서는 임의로 도면 외곽을 추정하지 않는다. 이 경우 기준 템플릿에 별도의 비출력 Plot Boundary Polyline 또는 Named Block을 추가하는 방안을 보고하고 승인받는다.

#### 5.3.2 형상 프로파일에 포함할 정보

프로파일은 최소 다음 정보를 포함한다.

- 프로파일 ID와 스키마 버전
- 축척 라벨: `1대1`, `2대1`
- 수치 축척: numerator, denominator
- 원본 DWG 파일명과 SHA-256
- GstarCAD 버전과 DWG 버전
- 기준 Layout/Model 이름
- 기준 Plot Window 좌표
- Plot Window 대비 도곽 경계의 상대 위치
- 도곽 종횡비
- 주요 Block Reference 이름과 상대 삽입 위치
- 주요 Layer 이름과 엔티티 수
- Line, Polyline, Arc, Circle, Text, MText, Dimension 등 엔티티 유형별 개수
- 닫힌 Polyline의 정규화된 꼭짓점
- 제목란·외곽선 등 기준 Anchor 형상의 상대 좌표
- 허용 회전과 허용 변환 유형
- 승인 일자와 승인 상태

프로파일 예시:

```json
{
  "schema_version": 1,
  "profile_id": "scale_1_to_1_a4_001",
  "scale_label": "1대1",
  "scale_ratio": {
    "numerator": 1.0,
    "denominator": 1.0
  },
  "source": {
    "file_name": "1대1.dwg",
    "sha256": "<SHA256>",
    "gstarcad_version": "<DETECTED_VERSION>"
  },
  "reference_plot_window": {
    "lower_left": [0.0, 0.0],
    "upper_right": [0.0, 0.0]
  },
  "fingerprint": {
    "aspect_ratio": 0.0,
    "entity_histogram": {},
    "block_names": [],
    "layer_names": [],
    "normalized_anchors": []
  },
  "approval": {
    "status": "approved",
    "approved_at": "<ISO-8601>"
  }
}
```

실제 좌표와 임계값을 예시 값으로 하드코딩하지 않는다.

#### 5.3.3 대상 DWG의 템플릿 매칭

각 DWG에서 다음 순서로 처리한다.

1. 등록된 프로파일을 사용해 도곽 후보 영역을 탐색한다.
2. 종횡비, 외곽선, 주요 블록·레이어, 엔티티 분포로 1차 후보를 좁힌다.
3. 정규화된 Anchor와 도곽 형상으로 2차 유사도를 계산한다.
4. 가장 높은 점수와 두 번째 점수의 차이를 함께 평가한다.
5. Phase 0 샘플로 승인된 최소 점수와 최소 점수 차이를 모두 만족할 때만 자동 확정한다.
6. 기준 Plot Window를 대상 도곽에 맞춰 변환한다.
7. 변환된 Window가 도곽을 벗어나거나 다른 도곽과 비정상적으로 겹치면 실패 처리한다.

생산 환경의 임계값은 실제 회사 도면으로 교정하며 문서 작성 단계에서 임의의 수치를 확정하지 않는다.

#### 5.3.4 허용 변환

기본적으로 다음 변환만 허용한다.

- X/Y 이동
- 균일 축척
- 0°, 90°, 180°, 270° 회전
- 샘플 검증으로 승인된 미러

다음은 기본적으로 자동 허용하지 않는다.

- X/Y 비균일 축척
- Shear
- 도곽 일부 삭제
- 외곽선이 끊어진 변형
- 제목란 또는 Anchor가 기준과 다른 개정 형식

비균일 변형이 검출되면 기준 Plot Window를 억지로 적용하지 않고 새로운 기준 템플릿 등록을 요청한다.

#### 5.3.5 매칭 실패 정책

다음 상황에서는 도면 전체 Extents, 가장 큰 사각형 또는 가까운 축척으로 임의 대체하지 않는다.

- 등록된 프로파일과 일치하지 않음
- 두 개 이상의 프로파일 점수가 유사함
- 저장된 Plot Window가 없음
- 파일명 축척 라벨을 해석할 수 없음
- 기준 프로파일의 SHA-256 또는 승인 상태가 유효하지 않음
- 대상 도곽이 비균일 변형됨

프로그램은 가장 가까운 후보명과 비교 점수를 로컬 로그에 남기되, 사용자가 확인하기 전에는 PDF를 생성하지 않는다.

### 5.4 Phase 0 승인 보고서 결론 형식

보고서는 다음 순서로 작성한다.

1. 결론: 구현 가능 / 조건부 가능 / 현재 불가
2. 확인된 사실
3. 확인되지 않은 항목
4. 권장 자동화 방식
5. 축척별 기준 템플릿 파일명과 저장 Plot Window 확인 결과
6. 형상 프로파일 구성과 템플릿 매칭 방식
7. 기준 프로파일별 수동 PDF 비교 결과
8. 플로터·CTB·용지 이름 검증 결과
9. GitHub 후보 기술 채택·보류·제외 판단
10. GstarCAD 라이선스 및 배포 영향
11. 사용자 PC 간섭 가능성
12. 개발 전 사용자 승인 필요 항목

---

## 6. 사용자 실행 방식

### 6.1 기본 실행

프로그램 이름 예시:

```text
DWG_TO_PDF.exe
```

입력 방식은 두 가지를 모두 지원한다.

#### 방식 A - 드래그 앤 드롭

- DWG 한 개 또는 여러 개를 `DWG_TO_PDF.exe` 위로 드래그한다.
- 폴더를 드래그한 경우 기본적으로 해당 폴더의 최상위 `.dwg`만 대상으로 한다.
- 하위 폴더 재귀 검색은 기본 비활성화한다.

#### 방식 B - 콘솔 경로 입력

```text
DWG 파일 또는 폴더 경로를 입력하십시오:
> "D:\Project\Drawing A.dwg"

PDF 저장 폴더 경로를 입력하십시오:
> "D:\Project\PDF Output"
```

Windows 탐색기의 주소 표시줄에서 복사한 경로와 `Shift + 우클릭 → 경로로 복사` 형식을 처리한다.

### 6.2 명령행 직접 실행

```powershell
DWG_TO_PDF.exe "D:\DWG\A.dwg" --output "D:\PDF"
DWG_TO_PDF.exe "D:\DWG\A.dwg" "D:\DWG\B.dwg" --output "D:\PDF"
DWG_TO_PDF.exe "D:\DWG" --output "D:\PDF"
```

지원 인자:

```text
--output <folder>                출력 폴더
--config <file>                  config.toml 경로
--template-dir <folder>          승인된 기준 템플릿 DWG 폴더
--register-template <dwg>        기준 템플릿 1개를 검증·등록
--rebuild-template-library       기준 템플릿 프로파일 전체 재생성
--list-template-profiles         등록된 축척·프로파일·승인 상태 표시
--dry-run                        PDF를 생성하지 않고 매칭·플롯 창만 표시
--verbose                        상세 로컬 로그
--keep-temp                      개발/고장 분석용 임시 파일 보존
--version                        프로그램 버전 표시
--help                           사용법 표시
```

충돌 처리 방식은 사용자 승인이 필요하므로 `--overwrite`를 기본 제공하지 않는다. 향후 무인 자동화가 필요할 때 별도 승인 후 추가한다.

---

## 7. 정확한 플롯 사양

각 템플릿 영역별로 아래 조건을 적용한다.

| 항목 | 고정값/동작 |
|---|---|
| 프린터/플로터 | 사용자 지정 기대값: `DWG To PDF.pc3` |
| 용지 | ISO A4, 297.00 × 210.00 mm |
| 방향 | 가로 방향 |
| 플롯 영역 | 식별된 기준 템플릿의 정확한 경계 Window |
| 플롯 축척 | Fit to Paper / 용지에 맞춤 |
| 플롯 간격 | Center the Plot / 플롯 중심 |
| 플롯 스타일 | `monochrome.ctb` |
| 객체 선가중치 플롯 | 사용 |
| 플롯 스타일로 플롯 | 사용 |
| 변경 사항을 배치에 저장 | 사용, 단 임시 DWG에만 적용 |
| 백그라운드 플롯 | 사용하지 않음 |
| 용지 공간을 마지막에 플롯 | 사용하지 않음 |
| 용지 공간 객체 숨기기 | 사용하지 않음 |
| 플롯 스탬프 | 사용하지 않음 |
| 상하 반전 | 사용하지 않음 |
| 기타 미지정 옵션 | 사용하지 않음 |

### 7.1 플로터명 검증

`DWG To PDF.pc3`를 문자열로 바로 적용하지 않는다.

1. 설치된 Plot Configuration 목록을 API로 열거한다.
2. 대소문자를 무시한 정확 일치 항목을 찾는다.
3. 정확 일치하지 않으면 자동 대체하지 않는다.
4. 사용 가능한 플로터 목록을 오류 메시지와 로그에 표시한다.
5. GstarCAD 설치본에서 실제 명칭이 다를 경우 Phase 0에서 사용자 승인을 받아 설정값만 변경한다.

### 7.2 용지명 검증

표시 문자열은 버전과 언어에 따라 달라질 수 있다.

1. 선택된 플로터의 Canonical Media Name 목록을 가져온다.
2. 폭 297 mm, 높이 210 mm 또는 회전 전 210 mm × 297 mm와 일치하는 항목을 찾는다.
3. 허용 오차는 기본 ±0.20 mm로 한다.
4. A4 후보가 여러 개면 ISO 계열을 우선하되 자동 확정하지 말고 Phase 0에서 검증한다.
5. 용지를 선택한 후 최종 방향을 Landscape로 설정한다.

### 7.3 CTB 검증

1. `monochrome.ctb`의 존재 여부를 GstarCAD Plot Style 경로에서 확인한다.
2. STB 모드 도면인지 CTB 모드 도면인지 확인한다.
3. 도면이 STB 모드여서 `monochrome.ctb`를 적용할 수 없으면 변환을 중단하고 원인을 보고한다.
4. CTB가 없으면 임의 생성하거나 다른 CTB로 대체하지 않는다.

### 7.4 플롯 창 좌표

- 플롯 창의 기준값은 사용자가 축척별 기준 템플릿 DWG에 저장한 Plot Window이다.
- 기준 Plot Window 좌표는 기준 도곽의 로컬 좌표계에 대한 상대 좌표로 변환하여 프로파일에 저장한다.
- 대상 도곽과 프로파일이 일치하면 Anchor를 이용해 이동·균일 축척·회전 변환을 계산한다.
- 기준 Plot Window의 네 모서리를 동일한 변환으로 대상 좌표에 매핑한다.
- GstarCAD Window Plot API가 축 정렬된 두 점만 허용하는 경우 회전 도곽 처리 가능 여부를 Phase 0에서 검증한다.
- Block Reference일 경우 삽입점, 축척, 회전, 미러를 반영한다.
- 단순 `GeometricExtents`만으로 Plot Window를 대신하지 않는다.
- 저장 Plot Window를 읽을 수 없을 때만 사용자 승인 후 전용 비출력 Plot Boundary Polyline을 사용한다.
- 좌표 변환 후 좌하단과 우상단을 정규화한다.
- 경계가 0, 비정상 종횡비, 다른 도곽과 과도한 겹침 또는 도곽 외부 이탈이면 해당 템플릿을 실패 처리한다.

### 7.5 축척 프로파일 적용 원칙

- `1대1` 프로파일에는 `1대1.dwg`에서 읽은 Plot Window를 사용한다.
- `2대1` 프로파일에는 `2대1.dwg`에서 읽은 Plot Window를 사용한다.
- 축척 라벨이 같아도 형상이 다른 도곽을 자동 동일 프로파일로 취급하지 않는다.
- 하나의 DWG 안에 `1:1`과 `2:1` 템플릿이 함께 있어도 각 인스턴스를 독립적으로 매칭한다.
- PDF는 모든 경우 A4 가로, Fit to Paper로 출력한다. 축척 라벨은 기준 도곽 형상과 Plot Window 선택을 위한 정보이며 PDF Plot Scale을 임의로 `1:1` 또는 `2:1` 고정하는 지시가 아니다.
- 사용자가 저장해 둔 Plot Window가 변경되면 기준 DWG SHA-256 차이를 감지하고 프로파일 재등록을 요구한다.

---

## 8. 다중 템플릿 처리

### 8.1 출력 파일명

입력:

```text
A.dwg
```

템플릿 1개:

```text
A.pdf
```

템플릿 3개:

```text
A.pdf
A_2.pdf
A_3.pdf
```

### 8.2 템플릿 정렬 순서

번호 부여가 실행마다 바뀌지 않도록 기하학적 순서를 고정한다.

기본 정렬:

1. Y 좌표가 큰 템플릿부터 작은 템플릿 순서
2. 동일 행으로 판단되는 경우 X 좌표가 작은 템플릿부터 큰 템플릿 순서
3. 동일 좌표일 경우 Entity Handle 또는 내부 고유 ID 순서

행 판정 허용 오차는 템플릿 높이의 10%를 기본값으로 하고 설정 파일에서 조정 가능하게 한다.

샘플 도면의 실제 배열이 가로 일렬인 경우 결과는 자연스럽게 좌→우 순서가 된다.

### 8.3 축척 라벨과 출력 파일명 구분

예를 들어 `ASSY-001.dwg` 안에 `1대1` 프로파일과 `2대1` 프로파일이 각각 한 개씩 검출되더라도 출력 파일명은 다음과 같다.

```text
ASSY-001.pdf
ASSY-001_2.pdf
```

다음과 같이 축척 라벨을 임의로 파일명에 추가하지 않는다.

```text
ASSY-001_1대1.pdf    # 금지
ASSY-001_2대1.pdf    # 금지
```

축척별 결과 식별은 로그의 `template_profile_id`와 `scale_label`로 제공한다.

### 8.4 다중 페이지 PDF 여부

사용자 요구는 템플릿마다 개별 PDF 저장이다. 하나의 다중 페이지 PDF로 합치지 않는다.

---

## 9. 기존 파일 충돌 처리

### 9.1 처리 순서

1. 전체 예상 출력 파일명을 먼저 계산한다.
2. 출력 폴더에 존재하지 않는 PDF는 즉시 순차 저장한다.
3. 기존 파일과 충돌하는 항목은 별도 목록에 보류한다.
4. 비충돌 파일 처리가 끝난 후 충돌 목록을 한 번에 표시한다.
5. 각 파일 또는 전체에 대해 사용자의 승인을 받는다.

### 9.2 콘솔 선택지

```text
동일한 파일명이 이미 존재합니다.
[1] D:\PDF\A.pdf
[2] D:\PDF\B_2.pdf

O : 덮어쓰기
C : 복사본 이름으로 저장
S : 건너뛰기
A : 전체 작업 중단

각 파일에 적용하려면 번호와 선택값을 입력하십시오. 예: 1:C, 2:O
전체에 적용하려면 ALL:C 형식으로 입력하십시오.
```

### 9.3 복사본 이름 규칙

기존 PDF 충돌에 따른 복사본은 다중 템플릿 번호 규칙과 구분한다.

```text
A.pdf
A - 복사본.pdf
A - 복사본 2.pdf
A - 복사본 3.pdf
```

다중 템플릿 파일에서 충돌한 경우:

```text
A_2.pdf
A_2 - 복사본.pdf
A_2 - 복사본 2.pdf
```

파일 존재 검사는 저장 직전 다시 수행하여 경쟁 조건을 방지한다.

### 9.4 덮어쓰기 안전성

- 사용자가 승인한 파일만 덮어쓴다.
- 새 PDF를 임시 파일명으로 먼저 생성한다.
- PDF 유효성 검사 통과 후 기존 파일을 교체한다.
- 변환 실패 시 기존 PDF를 유지한다.

---

## 10. GstarCAD 세션 및 사용자 간섭 방지

### 10.1 기본 원칙

- `GetObject`로 사용자가 작업 중인 인스턴스에 무조건 연결하지 않는다.
- 가능하면 별도 COM 인스턴스를 생성한다.
- GstarCAD 창은 숨김 또는 최소화 상태로 운영하되, 해당 버전의 COM 안정성을 샘플로 확인한다.
- 사용자 GstarCAD 문서의 활성 문서, 선택 상태, 시스템 변수, 작업공간을 변경하지 않는다.
- 백그라운드 플롯은 비활성화한다.
- 동시에 여러 프로그램 인스턴스가 같은 GstarCAD를 제어하지 못하도록 프로세스 Mutex를 사용한다.

### 10.2 GstarCAD가 이미 실행 중인 경우

Phase 0에서 아래 세 가지 중 실제 가능한 방식을 확정한다.

1. 별도 COM 인스턴스 생성
2. 별도 프로세스 실행 후 COM 연결
3. 동일 인스턴스밖에 불가능한 경우 사용자에게 작업 중인 문서 저장 및 종료 요청

사용자의 활성 GstarCAD 세션에 간섭할 가능성이 있으면 무단 실행하지 않고 변환을 중단한다.

### 10.3 타임아웃과 복구

- DWG 열기 기본 타임아웃: 120초
- 템플릿 1개 플롯 기본 타임아웃: 180초
- GstarCAD 응답 대기: 짧은 Polling과 상태 확인 사용
- 강제 종료 전 프로그램이 소유한 전용 GstarCAD 프로세스인지 확인
- 사용자가 실행한 GstarCAD 프로세스를 종료하지 않는다.

### 10.4 사용자 작업 방해 최소화

- 동시 GstarCAD 플롯 작업은 기본 1개로 제한한다.
- 프로그램이 소유한 보조 프로세스는 Windows `BELOW_NORMAL_PRIORITY_CLASS`를 우선 검토한다.
- CPU·메모리 사용량이 기준을 넘으면 다음 작업 시작을 지연한다.
- 입력 DWG의 크기와 수정 시간이 연속 확인에서 안정된 후 임시 복사한다.
- 파일 공유 잠금 또는 `.dwl`/`.dwl2` 상태만으로 저장 완료를 단정하지 않고 실제 읽기·복사 가능 여부를 함께 확인한다.
- 수동 입력 파일도 GstarCAD가 저장 중일 수 있으므로 파일 안정화 검사를 생략하지 않는다.
- 폴더 감시는 현재 MVP 범위에 넣지 않으며 향후 승인 시 `watchdog`를 사용한다.


---

## 11. 로컬 보안 및 네트워크 차단

### 11.1 금지 사항

- HTTP/HTTPS 요청
- 클라우드 저장
- 원격 로그 전송
- 사용 통계 또는 텔레메트리
- LLM API 호출
- 온라인 라이선스 우회
- DWG/PDF 파일 내용의 외부 전송

### 11.2 네트워크 무사용 검증

- 소스 코드에서 `requests`, `urllib`, `httpx`, `socket` 등 네트워크 모듈의 업무 사용을 금지한다.
- 의존성 설치는 개발 PC에서만 수행하고 배포본에는 고정된 종속성을 포함한다.
- 대상 PC 실행 중 네트워크 연결이 없어도 모든 변환 기능이 동작해야 한다.
- Windows Resource Monitor 또는 TCPView를 이용해 실행 중 외부 연결이 없음을 확인한다.

### 11.3 외부 프로세스 및 공급망 보안

GstarCAD 실행 파일 또는 승인된 보조 도구를 호출할 때 다음을 지킨다.

- `shell=True`를 사용하지 않는다.
- 명령 문자열을 조합해 셸에 전달하지 않고 인자 배열을 사용한다.
- 입력 확장자를 `.dwg`로 제한한다. 진단 도구가 필요한 경우 승인된 `.dxf`만 추가한다.
- 각 작업은 고유 임시 폴더에서 수행한다.
- 프로세스별 시간 제한을 둔다.
- 승인된 실행 파일 경로와 SHA-256을 확인한다.
- 런타임 자동 다운로드와 자동 업데이트를 금지한다.
- Python 의존성은 잠금 파일과 해시를 사용한다.
- 배포본에 `THIRD_PARTY_NOTICES.md`와 라이선스 원문을 포함한다.
- 외부에서 받은 DWG는 원본 폴더에서 직접 실행·변환하지 않고 임시 격리 복사본으로 처리한다.

### 11.4 선택 기능의 라이선스 경계

- pypdf, watchdog, ezdxf, PyInstaller는 실제 채택 버전의 라이선스를 배포 시 다시 저장한다.
- cad2x-converter는 LGPL-2.1 조건과 포함된 Qt·LibreCAD 파생 코드의 의무를 별도 확인한다.
- LibreDWG는 GPL-3.0이므로 외부 배포 프로그램에 결합하기 전에 법적 검토 없이 포함하지 않는다.
- 사내 전용 사용과 고객·협력사 EXE 배포를 구분하여 검토한다.
- 생성된 PDF만 외부 제공하는 경우와 프로그램 바이너리를 제공하는 경우를 구분한다.


### 11.5 로컬 로그

기본 로그 위치:

```text
%LOCALAPPDATA%\DwgToPdf\logs\
```

로그 포함 항목:

- 프로그램 버전
- 실행 시각
- 입력 파일 경로
- 출력 폴더
- GstarCAD 버전 및 ProgID
- 선택된 PC3, 용지, CTB
- 탐지된 템플릿 개수와 경계 좌표
- 적용된 `template_profile_id`와 `scale_label`
- 최고·차순위 매칭 점수와 승인 임계값
- 기준 Plot Window와 변환된 대상 Plot Window
- 기준 DWG SHA-256 및 프로파일 버전
- 출력 파일명
- 성공/실패/건너뜀
- 예외 코드와 원인

로그 제외 항목:

- DWG 내부 텍스트 전체
- 개인정보로 추정되는 도면 내용
- 라이선스 키
- 불필요한 시스템 정보

---

## 12. 권장 프로젝트 구조

```text
dwg-to-pdf/
├─ README.md
├─ DEVELOPMENT_RULES.md
├─ pyproject.toml
├─ requirements.lock
├─ config.example.toml
├─ src/
│  └─ dwg_to_pdf/
│     ├─ __init__.py
│     ├─ __main__.py
│     ├─ cli.py
│     ├─ bootstrap.py
│     ├─ configuration.py
│     ├─ input_resolver.py
│     ├─ output_planner.py
│     ├─ conflict_resolver.py
│     ├─ naming.py
│     ├─ logging_setup.py
│     ├─ security_guard.py
│     ├─ temp_workspace.py
│     ├─ file_stability.py
│     ├─ process_priority.py
│     ├─ dependency_audit.py
│     ├─ pdf_validator.py
│     ├─ templates/
│     │  ├─ scale_label.py
│     │  ├─ profile_schema.py
│     │  ├─ profile_store.py
│     │  ├─ reference_registrar.py
│     │  ├─ geometry_fingerprint.py
│     │  ├─ template_candidate.py
│     │  ├─ template_matcher.py
│     │  └─ plot_window_transform.py
│     └─ gstarcad/
│        ├─ discovery.py
│        ├─ com_session.py
│        ├─ document.py
│        ├─ template_detector.py
│        ├─ media_resolver.py
│        ├─ plot_settings.py
│        └─ plotter.py
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ fixtures/
│  └─ golden/
├─ reference_templates/
│  ├─ 1대1.dwg
│  └─ 2대1.dwg
├─ template_profiles/
│  └─ README.md
├─ third_party/
│  ├─ THIRD_PARTY_NOTICES.md
│  └─ licenses/
├─ tools/
│  ├─ inspect_gstarcad.py
│  ├─ inspect_plot_devices.py
│  ├─ register_reference_templates.py
│  ├─ inspect_template_profile.py
│  ├─ verify_dependency_hashes.py
│  └─ compare_pdf_renders.py
├─ packaging/
│  ├─ dwg_to_pdf.spec
│  ├─ build.ps1
│  ├─ verify_bundle.ps1
│  └─ checksums.txt
└─ docs/
   ├─ PHASE_0_FEASIBILITY_REPORT.md
   ├─ USER_GUIDE_KO.md
   ├─ TEST_REPORT.md
   └─ RELEASE_NOTES.md
```

각 파일은 하나의 책임만 가진다. `cli.py` 또는 `plotter.py` 하나에 모든 기능을 몰아넣지 않는다.

---

## 13. 설정 파일 예시

```toml
[application]
name = "DWG TO PDF"
locale = "ko-KR"
log_level = "INFO"
keep_temp_on_error = true
network_access = false

[gstarcad]
preferred_versions = ["2027", "2026", "2025", "2024"]
preferred_prog_ids = []
visible = false
use_separate_instance = true
open_timeout_sec = 120
plot_timeout_sec = 180

[template_library]
reference_dwg_directory = "reference_templates"
profile_directory = "template_profiles"
method = "reference_geometry_profile"
filename_scale_pattern = '^(?P<numerator>\d+(?:\.\d+)?)대(?P<denominator>\d+(?:\.\d+)?)$'
use_saved_plot_window = true
allow_unapproved_profiles = false
allow_unknown_template = false
require_uniform_transform = true
allowed_rotations_deg = [0, 90, 180, 270]
allow_mirror = false
minimum_count = 1
row_tolerance_ratio = 0.10
matching_threshold = "CALIBRATE_IN_PHASE_0"
minimum_score_gap = "CALIBRATE_IN_PHASE_0"

[template_fallback]
marker_block_names = []
marker_layer = ""
use_marker_only_after_user_approval = true

[plot]
plotter_name = "DWG To PDF.pc3"
paper_width_mm = 297.0
paper_height_mm = 210.0
paper_tolerance_mm = 0.20
orientation = "landscape"
plot_area = "window"
fit_to_paper = true
center_plot = true
style_sheet = "monochrome.ctb"
plot_object_lineweights = true
plot_with_plot_styles = true
save_changes_to_layout = true
plot_in_background = false
plot_paperspace_last = false
hide_paperspace_objects = false
plot_stamp = false
plot_upside_down = false

[optional_tools.cad2x]
enabled = false
purpose = "poc_only"
executable_path = ""
sha256 = ""

[optional_features.folder_watch]
enabled = false
library = "watchdog"

[output]
first_template_suffix = ""
additional_template_suffix = "_{index}"
copy_suffix = " - 복사본"
validate_pdf_before_commit = true
```

Phase 0에서 확인되지 않은 값은 빈 배열 또는 명시적 오류 상태로 둔다. 추정값으로 채우지 않는다.

---

## 14. 처리 흐름

```text
START
  ↓
설정·의존성 해시·네트워크 금지 상태 확인
  ↓
승인된 축척별 템플릿 프로파일 로드
  ↓
기준 DWG SHA-256 변경 여부 확인
  ↓
입력 인자/드래그 파일 해석
  ↓
출력 폴더 입력 및 쓰기 권한 검증
  ↓
GstarCAD 설치·라이선스·COM·PC3·CTB 검증
  ↓
각 DWG 파일 안정화 및 사전 검사
  ↓
도곽 후보 탐색 → 축척별 형상 프로파일 매칭
  ↓
프로파일별 저장 Plot Window를 대상 좌표로 변환
  ↓
전체 출력 파일명 계획
  ↓
비충돌 출력 먼저 처리
  ↓
  원본 DWG → 임시 폴더 복사
  → 전용 GstarCAD 세션에서 열기
  → 기준 템플릿 탐지
  → 정렬
  → 템플릿별 플롯 설정
  → 임시 PDF 생성
  → PDF 유효성 확인
  → 최종 이름으로 원자적 이동
  → 임시 DWG 닫기 및 정리
  ↓
충돌 출력 목록 사용자 승인
  ↓
승인된 충돌 파일 처리
  ↓
결과 요약 및 로그 저장
  ↓
전용 GstarCAD 세션 종료
  ↓
END
```

---

## 15. 오류 처리 기준

오류는 다음 코드 체계로 관리한다.

| 코드 | 의미 | 기본 동작 |
|---|---|---|
| E100 | 입력 DWG 없음 | 해당 입력 거부 |
| E101 | 출력 폴더 없음/쓰기 불가 | 전체 중단 |
| E200 | GstarCAD 미설치 | 전체 중단 |
| E201 | GstarCAD 라이선스/시작 실패 | 전체 중단 |
| E202 | COM ProgID 확인 실패 | 전체 중단 |
| E210 | 지정 PC3 없음 | 전체 중단 |
| E211 | A4 용지 매칭 실패 | 전체 중단 |
| E212 | monochrome.ctb 없음 | 전체 중단 |
| E213 | STB/CTB 불일치 | 해당 DWG 실패 |
| E214 | 외부 도구 또는 의존성 해시 불일치 | 전체 중단 |
| E215 | 입력 파일이 저장 중이거나 안정화되지 않음 | 해당 DWG 보류 |
| E300 | 기준 템플릿 없음 | 해당 DWG 실패 |
| E301 | 템플릿 경계 비정상 | 해당 템플릿 실패 |
| E302 | 중복/겹침 템플릿 | 해당 DWG 보류 |
| E303 | 등록 프로파일과 매칭되지 않음 | 해당 템플릿 보류 |
| E304 | 두 개 이상 프로파일의 점수가 유사함 | 해당 템플릿 보류 |
| E305 | 기준 템플릿 파일명의 축척 라벨 해석 실패 | 기준 등록 중단 |
| E306 | 기준 DWG에 저장된 Plot Window 없음/조회 실패 | 기준 등록 중단 |
| E307 | 비균일 축척·Shear 등 허용되지 않은 변형 | 해당 템플릿 보류 |
| E308 | 기준 DWG SHA-256 변경 또는 미승인 프로파일 | 프로파일 재등록 요구 |
| E309 | 기준 Plot Window 변환 결과가 비정상 | 해당 템플릿 실패 |
| E400 | DWG 열기 실패 | 해당 DWG 실패 |
| E401 | 외부참조/폰트 누락 경고 | PDF 생성 후 경고 표시 |
| E410 | 플롯 실패 | 해당 템플릿 실패 |
| E411 | 플롯 타임아웃 | 해당 템플릿 실패, 전용 세션 복구 |
| E420 | PDF 유효성 검사 실패 | 최종 저장 금지 |
| E500 | 파일명 충돌 승인 없음 | 해당 출력 보류/건너뜀 |
| E900 | 예상하지 못한 내부 오류 | 안전 종료 및 로그 보존 |

한 DWG의 실패가 나머지 비충돌 DWG까지 무조건 중단시키지 않도록 한다. 단, GstarCAD 자체, PC3, CTB와 같은 공통 환경 오류는 전체 중단한다.

---

## 16. PDF 유효성 검사

최종 저장 전에 최소 다음을 확인한다.

1. 파일이 존재한다.
2. 파일 크기가 0보다 크고 최소 기준 이상이다.
3. PDF 헤더 `%PDF-`가 존재한다.
4. PDF 파서로 열 수 있다.
5. 페이지 수가 정확히 1페이지이다.
6. 페이지 방향이 가로이며 A4 크기와 허용 오차 내에서 일치한다.
7. 렌더링이 가능한지 확인한다.
8. 로그의 템플릿 수와 생성된 PDF 수가 일치한다.
9. 각 PDF에 사용된 축척 프로파일 ID와 변환 Plot Window가 기록되었는지 확인한다.

개발·검수 단계에서는 기준 PDF와 다음 항목을 비교한다.

- 페이지 크기
- 출력 범위
- 여백과 중심
- 객체 누락
- 선가중치
- 흑백 처리
- 문자 폰트 및 깨짐
- 외부참조/이미지 표시
- 래스터 렌더 픽셀 차이

픽셀 비교는 안티앨리어싱 차이를 고려해 완전 동일만을 합격 조건으로 삼지 않는다. 대신 구조적 누락, 크롭, 방향, 위치, 선가중치 이상을 별도로 판정한다.

---

## 17. 테스트 계획

### 17.1 단위 테스트

- 경로 따옴표 제거
- 한글/공백/괄호/특수문자 경로 처리
- `.dwg` 확장자 대소문자 처리
- 다중 템플릿 파일명 생성
- 복사본 이름 생성
- 충돌 파일 계획
- 템플릿 좌표 정렬
- A4 용지 크기 허용 오차 매칭
- 설정 파일 검증
- `1대1`, `2대1` 축척 파일명 파싱
- 잘못된 축척 파일명 거부
- 기준 DWG SHA-256 변경 감지
- 형상 특징 정규화
- 이동·균일 축척·회전 변환
- 비균일 축척·Shear 거부
- 최고 점수와 차순위 점수 판정
- 저장 Plot Window의 대상 좌표 변환
- 축척 라벨이 출력 PDF 이름에 추가되지 않는지 확인
- 네트워크 사용 금지 검사
- 외부 실행 파일 해시 검사

### 17.2 통합 테스트

1. `1대1.dwg` 기준 템플릿 등록
2. `2대1.dwg` 기준 템플릿 등록
3. 기준 템플릿의 저장 Plot Window 읽기
4. 기준 프로파일 PDF와 수동 기준 PDF 비교
5. `1:1` 템플릿 1개 DWG → `파일명.pdf`
6. `2:1` 템플릿 1개 DWG → `파일명.pdf`
7. `1:1`과 `2:1` 혼합 DWG → `파일명.pdf`, `파일명_2.pdf`
8. 동일 축척 템플릿 2개 DWG → `파일명.pdf`, `파일명_2.pdf`
9. 템플릿 10개 이상 번호 정렬
10. 위치가 이동된 템플릿 매칭
11. 균일 확대·축소된 템플릿 매칭
12. 90° 회전된 템플릿 처리
13. 비균일 축척 템플릿 거부
14. 등록되지 않은 축척·형상 거부
15. 두 프로파일 점수가 유사한 모호한 도곽 보류
16. 기준 DWG 변경 후 프로파일 재등록 요구
17. 한글 파일명·한글 경로
18. 긴 경로
19. 읽기 전용 DWG
20. 저장 중인 DWG 안정화 검사
21. 외부참조 포함 DWG
22. 누락 폰트와 한글 SHX/Big Font DWG
23. Layout/Viewport 사용 DWG
24. 해치·동적 블록·Proxy 객체 포함 DWG
25. 미러된 템플릿
26. 서로 겹친 템플릿
27. 기준 템플릿 없음
28. 기존 PDF 충돌 - 덮어쓰기
29. 기존 PDF 충돌 - 복사본
30. 기존 PDF 충돌 - 건너뛰기
31. GstarCAD가 이미 실행 중인 상태
32. GstarCAD 미설치 상태
33. PC3 누락 상태
34. CTB 누락 상태
35. 외부 도구 해시 불일치 상태
36. 네트워크 완전 차단 상태

### 17.3 사용자 PC 간섭 테스트

- 사용자 GstarCAD에서 수정 중인 DWG를 연 상태에서 프로그램 실행
- 활성 문서와 선택 객체가 변하지 않는지 확인
- 작업공간이 클래식/리본일 때 각각 확인
- 프로그램 종료 후 GstarCAD 프로세스가 비정상 잔류하지 않는지 확인
- 사용자가 실행한 GstarCAD가 종료되지 않는지 확인

### 17.4 신규 PC 테스트

- Python 미설치 Windows 10
- Python 미설치 Windows 11
- 관리자 권한 없는 일반 사용자
- 인터넷 연결 차단
- GstarCAD 버전별 최소 2개 버전
- 한글 Windows 사용자 계정
- 백신 실시간 감시 활성화

### 17.5 실제 도면 검증 세트

개발 완료 전 최소 20~30개의 대표 DWG를 사용한다.

| 분류 | 권장 수량 |
|---|---:|
| 일반 부품도 | 5 |
| 조립도 | 5 |
| 판금 제작도 | 5 |
| Layout/Viewport 사용 도면 | 5 |
| 한글 SHX/Big Font 도면 | 3 |
| XREF·이미지 참조 도면 | 3 |
| 해치·블록이 많은 도면 | 3 |
| 동적 블록·Proxy 객체 도면 | 2 이상 |
| `1:1`, `2:1` 혼합 도면 | 3 이상 |
| 실패·모호 매칭 검증 도면 | 3 이상 |

각 도면은 GstarCAD에서 사용자가 수동 출력한 PDF를 기준으로 비교한다. 단순 PDF 생성 성공률과 출력 정확도를 별개의 지표로 관리한다.


---

## 18. 완료 승인 기준

다음 조건을 모두 만족해야 개발 완료로 보고한다.

- [ ] 외부 네트워크 접속이 발생하지 않는다.
- [ ] Python이 설치되지 않은 PC에서 실행된다.
- [ ] GstarCAD의 설치 및 라이선스 상태를 정확히 검사한다.
- [ ] 사용자 GstarCAD 세션에 간섭하지 않는다.
- [ ] 원본 DWG의 수정일, 해시, 내용이 변하지 않는다.
- [ ] `1대1`, `2대1` 기준 파일명을 정확히 축척 라벨로 등록한다.
- [ ] 기준 DWG에 저장된 Plot Window를 정확히 읽고 프로파일에 저장한다.
- [ ] 기준 템플릿 1개/복수 개/혼합 축척을 안정적으로 탐지한다.
- [ ] 허용되지 않은 비균일 변형과 모호한 매칭을 자동 출력하지 않는다.
- [ ] 기준 DWG가 변경되면 프로파일 재등록을 요구한다.
- [ ] 복수 템플릿의 번호 순서가 반복 실행에서도 동일하다.
- [ ] 축척 라벨을 최종 PDF 파일명에 임의로 추가하지 않는다.
- [ ] `DWG To PDF.pc3` 또는 승인된 정확한 플로터만 사용한다.
- [ ] A4 297 × 210 mm 가로 출력이다.
- [ ] Fit to Paper, Center Plot이 적용된다.
- [ ] `monochrome.ctb`가 적용된다.
- [ ] 객체 선가중치와 플롯 스타일이 적용된다.
- [ ] 미지정 플롯 옵션은 비활성화된다.
- [ ] PDF 파일명이 요구 규칙과 일치한다.
- [ ] 비충돌 파일을 먼저 저장한다.
- [ ] 충돌 파일은 사용자 승인 없이 덮어쓰지 않는다.
- [ ] 덮어쓰기 실패 시 기존 PDF가 보존된다.
- [ ] 성공/실패/건너뜀과 프로파일 매칭 점수가 로그에 남는다.
- [ ] 외부 실행 파일과 의존성의 버전·라이선스·SHA-256 기록이 남는다.
- [ ] 기준 PDF와 비교하여 도면 누락, 크롭, 방향 오류가 없다.

---

## 19. CODEX 개발 수행 순서

### Phase 0 - 조사 및 승인

- 대상 PC와 샘플 DWG를 검사한다.
- 축척별 기준 템플릿 DWG와 저장 Plot Window를 검사한다.
- `1대1`, `2대1` 파일명 규칙을 검증한다.
- GstarCAD COM 방식과 GitHub 보조 후보의 PoC 범위를 구분한다.
- 채택 의존성의 버전·라이선스·해시 정책을 확정한다.
- `PHASE_0_FEASIBILITY_REPORT.md`를 작성한다.
- 사용자의 승인을 기다린다.

### Phase 1 - 최소 동작 프로토타입

- GstarCAD 별도 COM 세션 생성
- DWG 한 개 열기
- 사전에 지정한 단일 Window를 A4 PDF로 출력
- 원본 DWG 비변경 검증

### Phase 2 - 기준 템플릿 등록 및 자동 매칭

- `1대1`, `2대1` 축척 라벨 파서 구현
- 기준 DWG의 저장 Plot Window 추출
- 형상 프로파일 생성·승인·버전 관리
- 이동·균일 축척·회전 기반 도곽 매칭
- 모호·미등록·비균일 변형 거부
- 다중·혼합 축척 템플릿 탐지 및 정렬
- `파일명`, `파일명_2` 규칙 구현

### Phase 3 - 일괄 처리 및 충돌 승인

- 다중 DWG 입력
- 비충돌 우선 처리
- 덮어쓰기/복사본/건너뛰기 콘솔 승인
- 원자적 파일 교체

### Phase 4 - 배포 및 신규 PC 실행

- PyInstaller `onedir` 빌드
- Windows 환경에서 Windows 배포본 생성
- Python 미설치 PC 검증
- 인터넷 차단 검증
- 의존성 해시와 `THIRD_PARTY_NOTICES.md` 검증
- 백신 오탐 확인

### Phase 5 - 최종 검수

- 대표 도면 20~30개 이상 검증
- 축척별 기준 PDF와 대상 PDF 비교
- 혼합 축척·모호 매칭·미등록 템플릿 실패 검증
- cad2x-converter를 사용할 경우 별도 PoC 결과와 주 엔진 결과 비교
- 장애 복구
- 로그 검토
- 사용자 안내서 작성
- 설치/배포 파일 체크섬 생성

각 Phase 종료 시 테스트 결과를 보고하고 다음 Phase로 넘어가기 전에 사용자 승인을 받는다.

---

## 20. CODEX가 임의로 변경할 수 없는 사항

- 출력 용지는 A4 가로이다.
- 플롯 축척은 용지에 맞춤이다.
- 플롯 영역은 축척별 기준 DWG에 저장된 Plot Window를 프로파일링하여 적용한다.
- 기준 템플릿 파일명 `1대1`, `2대1`은 축척 라벨로 해석한다.
- 등록되지 않거나 모호하게 매칭된 템플릿을 임의 출력하지 않는다.
- 플롯은 중심 정렬이다.
- 플롯 스타일은 `monochrome.ctb`이다.
- 객체 선가중치와 플롯 스타일 적용을 활성화한다.
- 나머지 플롯 옵션은 비활성화한다.
- 템플릿별 개별 PDF를 생성한다.
- 원본과 동일한 파일명을 첫 출력에 사용한다.
- 추가 템플릿에는 `_2`, `_3` 순서를 사용한다.
- `1대1`, `2대1` 축척 라벨을 최종 PDF 파일명에 임의로 추가하지 않는다.
- 기존 파일을 사용자 승인 없이 덮어쓰지 않는다.
- 외부 접속과 LLM 연결을 금지한다.
- 원본 DWG를 직접 수정하지 않는다.
- 사용자 작업 중인 GstarCAD를 강제 종료하지 않는다.
- cad2x-converter, LibreDWG, ezdxf 등의 보조 도구를 사용자 승인과 PoC 없이 주 변환 엔진으로 교체하지 않는다.
- 런타임에 GitHub 또는 인터넷에서 실행 파일·의존성을 자동 다운로드하지 않는다.

변경이 필요한 경우 코드 수정 전에 변경 이유, 영향, 대안을 보고하고 사용자의 명시적 승인을 받는다.

---

## 21. 검증 근거 및 공식 자료

아래 자료는 개발 착수 시 다시 확인한다.

1. GstarCAD Developer - COM, GRX, LISP, C/C++, VB/VBA, .NET 지원
   - `https://www.gstarcad.net/developer/`
2. GstarCAD Licensing Policy - Perpetual/Subscription, Stand-alone/Network 라이선스
   - `https://www.gstarcad.net/policy/`
3. GstarCAD 공식 사이트 - 평가판 기간 및 최신 제품 정보
   - `https://www.gstarcad.net/`
4. GstarCAD 2026 User Guide - Layout, Plot Area, Fit to Paper, Center Plot, Plot Options, Plot Style
   - `https://cdn-sg-gw.gstarcad.net/gstarsoft_pdf/GstarCAD_2026_User_Guide.pdf`
5. PyInstaller 공식 문서 - Python 인터프리터와 종속 모듈을 묶어 Python 미설치 PC에 배포 가능
   - `https://pyinstaller.org/en/stable/operating-mode.html`
6. Python Windows 공식 문서 - Embeddable/Offline 배포 관련 참고
   - `https://docs.python.org/3/using/windows.html`
7. GitHub `orcastor/cad2x-converter` - DWG/DXF CLI 변환 옵션, LGPL-2.1, Windows x64 바이너리 링크, GitHub Release 미게시 상태 확인
   - `https://github.com/orcastor/cad2x-converter`
8. GitHub `gorakhargosh/watchdog` - Windows 파일 이벤트 감시와 Apache-2.0
   - `https://github.com/gorakhargosh/watchdog`
9. GitHub `py-pdf/pypdf` - PDF 페이지·크기·파싱 검사용 순수 Python 라이브러리
   - `https://github.com/py-pdf/pypdf`
10. GitHub `pyinstaller/pyinstaller` - Python 미설치 PC용 독립 실행 배포, Windows에서 Windows 빌드 필요
   - `https://github.com/pyinstaller/pyinstaller`
11. GitHub `LibreDWG/libredwg` - GPL-3.0, 일부 고급 R2010+ 객체 누락 가능성에 대한 프로젝트 설명
   - `https://github.com/LibreDWG/libredwg`
12. GitHub `mozman/ezdxf` - MIT, DXF 전용 분석·렌더링 보조 라이브러리
   - `https://github.com/mozman/ezdxf`
13. 사용자 제공 검토자료
   - `GstarCAD_DWG_to_PDF_무료_백그라운드_개발검토(1).md`

GitHub 자료의 기능·버전·라이선스는 개발 착수일과 배포일에 다시 확인한다.

---

## 22. 최종 지시

CODEX는 이 문서를 읽은 즉시 프로그램 코드를 작성하지 않는다.

먼저 다음 작업만 수행한다.

1. 프로젝트 폴더 구조 생성 계획을 작성한다.
2. Phase 0에서 필요한 사용자 제공 자료 목록을 작성한다.
3. `1대1.dwg`, `2대1.dwg` 등 축척별 기준 템플릿 등록 절차를 제안한다.
4. 기준 DWG에 저장된 Plot Window를 읽는 GstarCAD COM/API 검증 계획을 작성한다.
5. 로컬 형상 프로파일의 스키마와 매칭 점수 교정 절차를 제안한다.
6. 대상 PC 검사 스크립트의 범위와 실행 결과 예시를 제안한다.
7. GstarCAD COM/API 방식, cad2x-converter PoC 방식, LibreDWG·ezdxf 보조 방식의 장단점을 비교한다.
8. 채택할 GitHub 의존성의 버전·라이선스·SHA-256 관리 계획을 제안한다.
9. 추천안을 제시한다.
10. 사용자의 승인을 기다린다.

사용자 승인 후에만 테스트 우선 방식으로 최소 프로토타입부터 구현한다.
