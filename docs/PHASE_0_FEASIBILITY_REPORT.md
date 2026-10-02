# Phase 0 사전 검증 보고서

- 프로젝트: 로컬 DWG → PDF 자동변환 프로그램
- 기준일: 2026-07-16
- 기준 문서: CODEX 개발 지침 Rev.02
- 보고서 상태: 실제 도면 사전 테스트 및 사용자 품질 기준 반영 완료

## 1. 결론

**조건부 구현 가능**으로 판정한다.

GstarCAD 2026 COM을 통해 기준 DWG의 Plot Window와 플롯 옵션을 읽고 실제 PDF를 생성하면서 원본 DWG의 해시와 수정시간을 보존할 수 있음을 확인했다. 실제 작업 DWG 4건에서도 내부 Scale과 도곽 크기가 템플릿 계열과 일치했고 A4 가로 PDF 변환에 성공했다. 추가 샘플에서는 대상 DWG의 저장 Window가 실제 도곽과 크게 다를 수 있음이 확인됐으므로, 운영 APP은 저장 Window를 사용하지 않고 내부 Scale과 도곽 Anchor로 출력영역을 새로 계산해 `SetWindowToPlot`에 적용하도록 설계한다.

다만 COM 객체 전체 열거는 실제 도면에서 RPC 정지를 일으켰으므로 사용하지 않는다. 자동 템플릿 매칭은 도곽 후보를 먼저 좁히고 그 영역의 중첩 블록만 제한 탐색해야 한다. 사용자는 통상 육안으로 구분하기 어려운 미세 선 누락은 문제없이 통과하도록 품질 기준을 확정했다.

## 2. 확인된 사실

### 2.1 대상 PC

| 항목 | 확인 결과 | 상태 |
|---|---|---|
| 운영체제 | Windows 64-bit, 빌드 10.0.26200, 25H2 | 확인 |
| GstarCAD | GstarCAD 2026 Standard, COM Version 26.00 | 확인 |
| 설치 경로 | `C:\Program Files\Gstarsoft\GstarCAD2026\gcad.exe` | 확인 |
| 언어 | LocaleId 1042, 한국어 | 확인 |
| COM ProgID | `GStarCAD.Application.26`, `Gcad.Application.26` 등 | 확인 |
| PDF 플로터 | `DWG To PDF.pc3` 정확 일치 | 확인 |
| A4 Canonical Media | `A4` | 확인 |
| 템플릿 용지 | `User77`, 실제 297 × 210 mm | 확인 |
| Plot Style | `monochrome.ctb` | 확인 |
| 라이선스 | 평가판 확인, 사용자 계획에 따라 정식 라이선스로 전환 예정 | 배포 전 재검증 |

Windows 제품명 레지스트리 문자열은 `Windows 10 Pro`로 표시되지만 빌드·표시 버전과의 명칭 정합은 최종 신규 PC 시험에서 다시 확인한다. 애플리케이션은 제품명 문자열이 아니라 64-bit 여부와 지원 빌드를 기준으로 검사한다.

### 2.2 기준 템플릿

| 축척 | 기준 파일 | SHA-256 | Plot Window 크기(약) |
|---:|---|---|---:|
| 100:1 | `TEMPLETE_100대1.DWG` | `83673B33511C3B10F54295BA681C359FDEE6948B34A0259C98A8589ED2BB3C6A` | 4.2 × 2.97 |
| 50:1 | `TEMPLETE_50대1.DWG` | `5A4D7E9BBB09897DAD4F74E73B84AD6D0A7C11DD8E39F7B7E3BCCA5CE420C2DD` | 8.4 × 5.94 |
| 20:1 | `TEMPLETE_20대1.DWG` | `CDDF702592A56A3EC6339D6A6D2D0AA780A91B5561144D0B41DE31D703A46018` | 21 × 14.85 |
| 10:1 | `TEMPLETE_10대1.DWG` | `7DC8CFC49AE54E23EED10D391FDF539756679704A559252733C86A103999555B` | 42 × 29.7 |
| 5:1 | `TEMPLETE_5대1.DWG` | `00B5E797E3256C2FD7E53A14C3E49AFAEDC8FF37AF92E23BA7B4E974996A3F8C` | 84 × 59.4 |
| 2:1 | `TEMPLETE_2대1.DWG` | `29F1EAA99261D262653DB21B6483D336E7F0339D09F186D5D548CFE1E3906E88` | 210 × 148.5 |
| 1:1 | `TEMPLETE_1대1.DWG` | `BEEBDF8F0D246CE623E637E7D1A4B3325199035B55DE7D1CC05EBE9D6A1BC281` | 420 × 297 |
| 1:2 | `TEMPLETE_1대2.DWG` | `F2BD4A5A4B8AC83787BD93E81CC8C40D8AEB0C57B149F95F5850D7F226B12E5F` | 840 × 594 |
| 1:5 | `TEMPLETE_1대5.DWG` | `C5370EEA268414604E5A43B7C9810157A9A2925BF96EFCAC698D6ECA48FDBC16` | 2,100 × 1,485 |
| 1:10 | `TEMPLETE_1대10.DWG` | `DCC5B938173453CFA458F633D00064DF6C7F527AE79DB3B7126CF2E3487C6DBA` | 4,200 × 2,970 |
| 1:20 | `TEMPLETE_1대20.DWG` | `03442D0391FCC3AF242A7B6F1CB8507EC7A4B171C303FCDBD7AB4E5E1909C297` | 8,400 × 5,940 |
| 1:50 | `TEMPLETE_1대50.DWG` | `4E0B38F20F1E600A59FD95BC776B98BC2ACCCE68FA0621013EE164001C7E80BF` | 21,000 × 14,850 |
| 1:100 | `TEMPLETE_1대100.DWG` | `F58283F20C16BBBC8FB10682CAE99B7AB26314B94748F489305C7F10C59B6A32` | 42,000 × 29,700 |

모든 템플릿의 Model 탭에서 다음 공통 조건을 확인했다.

- `DWG To PDF.pc3`
- Window Plot
- Fit to Paper
- Center Plot
- `monochrome.ctb`
- 객체 선가중치와 플롯 스타일 사용
- Plot Hidden 비활성
- Plot Viewports First 활성

수정된 5:1 파일은 이전 해시와 달라졌고, 새 파일에서 위 설정과 84 × 59.4 Plot Window를 확인했다.

### 2.3 실제 플롯 PoC

| 시험 | 결과 |
|---|---|
| 1:1 저장 설정 기반 PlotToFile | 성공 |
| 1:1 출력 | `%PDF-1.7`, 25,930 bytes |
| 5:1 저장 설정 기반 PlotToFile | 성공 |
| 5:1 출력 | `%PDF-1.7`, 25,944 bytes |
| 원본 SHA-256 | 전후 동일 |
| 원본 수정시간 | 전후 동일 |

### 2.4 형상 지문 대표 확인

1:1과 수정된 5:1의 대표 Model Space는 각각 34개 엔티티로 구성됐다.

- AcDbMText 18개
- AcDbBlockReference 4개
- AcDbLine 12개
- 레이어: `0`, `4-1`, `SLD-0`

1:1과 1:2 대표 템플릿의 제목란에서 각각 `1대1`, `1대2` 축척 토큰을 확인했다. 블록 이름은 동일하므로 축척 토큰과 기준 크기를 형상 지문에 함께 포함해야 한다.

### 2.5 사용자 제공 운영 조건

다음 항목은 2026-07-16 사용자 확정 요구사항이다.

- 실제 작업용 DWG 파일명에는 축척 정보가 없다.
- 향후 작업용 DWG는 현재 제공된 13개 템플릿 규격으로만 작성된다.
- 각 도곽의 우측 하단에 `Scale` 글자가 있다.
- `Scale` 바로 아래에 `1:1`, `2:1` 등의 실제 축척값이 기록된다.
- `Scale` 라벨과 축척값은 도곽 내에서 언제나 동일한 상대 위치 관계를 유지한다.
- 도곽 전체의 X/Y 위치 변경과 0°·90°·180°·270° 회전은 지원 대상이다.

따라서 작업용 DWG 파일명은 축척 판정에서 완전히 제외하고, 내부 `Scale` 셀을 기준 템플릿에서 학습해 도곽별 축척을 판정한다. 13개 템플릿의 정확한 `Scale` 라벨·축척값 상대 좌표는 프로파일 등록 단계에서 COM으로 전수 측정한다.

### 2.6 실제 작업 도면 사전 테스트

| 작업 도면 | 내부 Scale | Extents(약) | PDF 구조 | 렌더 판정 |
|---|---:|---:|---|---|
| `XXX-XXXXA_GASKET_FRT.DWG` | 1:5 | 2,100 × 1,485 | 1페이지, A4 가로 | 정상 |
| `XXX-XXXXA_Insualtion sheet UPR COVER B.DWG` | 1:2 | 840 × 594 | 1페이지, A4 가로 | 정상 |
| `XXX-XXXXA_PAD_UPR.DWG` | 1:10 | 4,200 × 2,970 | 1페이지, A4 가로 | 주요 형상·문자 정상, 일부 도곽·표제란 선 차이 |
| `XXX-XXXXA_Silicon Gromet A.DWG` | 1:1 | 420 × 297 | 1페이지, A4 가로 | 정상 |

네 파일 모두 `DWG To PDF.pc3`, `User77`, Window Plot, Fit, Center, `monochrome.ctb`, 선가중치 설정으로 `PlotToFile`에 성공했다. 각 원본 SHA-256은 변환 전후 동일했고 최종 PDF는 `%PDF-1.7`, 297 × 210 mm였다.

`PAD_UPR`은 Window와 진단용 Extents 출력에서 같은 선 차이가 재현됐다. 9개 레이어는 모두 출력 가능·켜짐·비동결 상태였으며, 도곽 익명 블록 `A$C0C890E57` 내부 16개 객체에는 ByLayer, 색상 150, 색상 7/TrueColor 흰색 등이 혼합돼 있었다. 따라서 Plot Window 오류는 배제했고 객체 색상·블록·CTB 조합을 원인 후보로 분류했다. 사용자는 이 수준의 차이는 육안 판별 대상이 아니므로 운영상 정상 통과하도록 확정했다.

### 2.7 Window 위치 변동 샘플

| 샘플 | SHA-256 | 실제 도곽/Extents(약) | 저장 Plot Window(약) | 판정 |
|---|---|---:|---:|---|
| `윈도우 영역 학습용/TEMPLETE_1대1.DWG` | `15F65A792E68FD3A079F8104DDCC2A19DB001CF200CE309F6D3BC8D8753EFEF0` | 420 × 297 | 148.08 × 98.32 | 저장 Window 사용 불가 |
| `윈도우 영역 학습용/TEMPLETE_1대50.DWG` | `A57715DD338BF99240481E2CA67A3F8E43CACDC5AE3E861E37B33D61B4A8FA85` | 21,000 × 14,850 | 37,280.04 × 31,994.98 | 저장 Window 사용 불가 |

두 파일은 `DWG To PDF.pc3`, `User77`, Fit, Center, `monochrome.ctb` 등 공통 플롯 속성은 유지하지만 저장 Window 좌표·크기가 실제 도곽을 대표하지 않는다. 따라서 이 두 파일은 기준 프로파일을 대체하지 않고, 대상 저장 Window 무시와 자동 Window 재계산을 검증하는 고정 회귀 샘플로 사용한다.

## 3. 분석

### 3.1 구현 가능성

`GetWindowToPlot`과 Model Layout의 플로터·용지·CTB·선가중치 옵션 조회 및 `PlotToFile` 성공을 확인했으므로 GstarCAD COM은 주 변환 엔진으로 사용할 수 있다. 자동 계산 좌표를 `SetWindowToPlot`에 적용하는 경로는 구현 단계의 통합시험에서 검증한다. 대상 DWG의 저장 Window는 신뢰하지 않고 진단 로그에만 기록한다.

### 3.2 템플릿 식별성

13개 템플릿은 같은 A계열 도곽을 균일 축척한 관계다. 위치·크기를 모두 정규화하면 프로파일 간 지문이 같아질 수 있다. 작업용 DWG 파일명에는 축척 정보가 없으므로 파일명은 사용할 수 없다. 따라서 다음 정보를 결합해야 한다.

- 우측 하단 `Scale` 라벨의 정규화 위치
- `Scale` 바로 아래 축척값의 정규화 위치와 상대 벡터
- 내부 축척값과 기준 프로파일 축척의 정확 일치
- 기준 크기와 대상 후보의 실제 크기
- 후보 영역에서 필터 선택된 블록·레이어·엔티티 분포
- 정규화 Anchor와 변환 잔차

학습된 위치에 `Scale` 라벨이나 축척값이 없으면 E303으로 보류한다. 내부 축척값과 형상 프로파일이 모순되거나 후보가 여러 개 남으면 자동 추정하지 않고 E304로 보류한다. 파일명이나 다른 위치의 주석 문자열은 대체 근거로 사용하지 않는다.

대상 Scale Anchor를 기준으로 승인된 프로파일의 0°·90°·180°·270° 후보를 역산하고, 예상 도곽 모서리·제목란·비대칭 Anchor가 유일하게 맞는 후보만 승인한다. 선택된 변환을 기준 템플릿의 참조 Plot Window 네 모서리에 적용하고, 회전에 맞는 PlotRotation으로 PDF를 A4 가로 정방향으로 보정한다. 전체 도곽이 함께 이동·회전하는 경우를 지원하며, 임의 확대·축소·미러·Shear 또는 일부 객체만 이동한 경우는 자동 출력하지 않는다.

### 3.3 COM 수명주기

두 COM 인스턴스 생성 시험에서 별도 프로세스는 생성됐으나 종료 응답이 불안정했고, 13개 파일의 축척 토큰 일괄 조회에서도 결과가 반환되지 않은 사례가 있었다. 반면 한두 문서를 처리하는 단일 세션은 안정적으로 종료됐다.

실제 작업 도면에서 11,603개 ModelSpace 전체 열거와 블록 정의 전체 열거가 60초 이상 응답하지 않는 사례가 추가 확인됐다. 반면 Layout·Extents·객체 수 조회와 `PlotToFile`은 독립 세션에서 성공했다. 따라서 운영 설계는 동시 다중 세션이나 전체 열거가 아니라 다음 방식을 사용한다.

- 작업 파일마다 새 전용 세션 한 개
- 한 파일의 열기·제한 탐색·플롯·닫기 후 다음 파일 처리
- 문서마다 진행 체크포인트 기록
- 단계별 COM 호출 타임아웃
- SelectionSet 필터와 도곽 후보의 중첩 블록만 제한 탐색
- ModelSpace·Blocks 컬렉션 전체 열거 금지
- 생성 전후 PID 차이로 소유권 확인
- 정상 종료 실패 시 소유 PID만 복구 종료

### 3.4 PDF 품질 판정 기준 수정

운영 실패 조건은 PDF 헤더·파싱·1페이지·A4 가로·렌더 성공·비백지·도곽 수·Scale/프로파일 일치로 제한한다. 수동 기준 PDF와의 픽셀 또는 선 단위 완전 일치는 운영 실패 조건으로 사용하지 않는다.

개별 선, 외곽 도곽 일부, 표제란 격자 일부, TrueColor/CTB 차이처럼 통상 배율에서 사람이 구분하기 어려운 차이는 결과 저장을 막지 않는다. 선택적 진단에서 검출하면 비차단 경고를 남길 수 있으나 기본 운영에서는 정상 통과한다.

## 4. 방식 비교

| 방식 | 장점 | 한계 | 판단 |
|---|---|---|---|
| GstarCAD COM | 실제 GstarCAD 플롯 엔진, PC3·CTB·폰트·Proxy 호환성 | COM 수명주기·타임아웃 관리 필요 | 채택 |
| GstarCAD 명령 스크립트 | 일부 COM 미지원 기능의 보조 가능 | 언어·명령 상태·타이밍 의존 | 제한적 폴백 |
| cad2x-converter | 무창 CLI, 흑백·Fit·용지 옵션 | 저장 Plot Window·CTB 동일 재현 근거 없음, 정식 Release 없음 | 별도 PoC만 |
| LibreDWG | DWG 직접 분석 가능 | GPL-3.0, 일부 고급 객체 누락 가능 | 주 경로 제외 |
| ezdxf | MIT, DXF 분석·렌더링 편리 | DWG 직접 입력은 외부 변환기 필요 | 진단 보조만 |

## 5. 리스크와 한계

| 리스크 | 영향 | 대응 |
|---|---|---|
| 실제 도면·수동 기준 PDF 부족 | 임계값과 출력 정확도 승인 불가 | 20~30개 대표 세트 확보 후 교정 |
| 정규화 형상의 축척 간 동점 | 잘못된 축척 선택 | 우측 하단 Scale 셀의 내부 축척값을 필수 조건으로 적용; 동점 보류 |
| Scale 라벨·축척값 위치 변경 | 축척 판정 실패 | 기준 상대 위치 허용 오차 검사, E303 보류, 템플릿 재등록 |
| 파일명에 축척 정보가 없음 | 파일명 기반 판단 불가 | 파일명은 출력 기본 이름에만 사용하고 내부 Scale 셀로 판정 |
| COM 장시간 일괄 처리 정지 | 배치 중단·프로세스 잔류 | 문서 단위 체크포인트, 타임아웃, 소유 PID 복구 |
| ModelSpace·Blocks 전체 열거 정지 | 축척 판독 중 RPC 중단 | Extents를 필터 한계로만 사용, SelectionSet 유형 필터, 후보 중첩 블록만 제한 탐색 |
| 대상 저장 Window가 도곽과 불일치 | 크롭·과대 여백·백지 출력 | 저장 Window 무시, Scale Anchor와 기준 프로파일로 Window 신규 계산 |
| 미세 도곽·표제란 선 차이 | 자동 품질검사 과민 반응 | 운영 실패 조건에서 제외하고 선택적 비차단 경고 또는 무시 |
| 4방향 회전과 PlotRotation 매핑 오류 | PDF 내용 방향 오류 | 0°·90°·180°·270° 고정 샘플별 A4 가로 정방향 회귀시험 |
| XREF·폰트·Proxy 누락 | PDF 품질 저하 | 경고 수집과 수동 기준 PDF 비교 |
| 정식 라이선스 전환 전 | 운영 승인 불가 | 배포 전 라이선스 재검사 |
| PyInstaller/백신 환경차 | 신규 PC 실행 실패 | onedir 우선, 체크섬·백신 시험 |

## 6. 실행안

1. 승인된 설계로 구현계획 작성
2. 테스트 우선으로 축척 파서·4방향 좌표변환·자동 Window·PlotRotation·품질 게이트 등 순수 로직 구현
3. 파일당 독립 세션·단계별 타임아웃·소유 PID 복구 구현
4. SelectionSet 필터와 후보 중첩 블록 제한 탐색 구현
5. 13개 템플릿 프로파일 등록과 Scale·도곽 모서리·회전 Anchor·참조 Window 전수 검증
6. 다중·혼합 도곽 탐지와 충돌 처리 구현
7. 실제 도면과 기준 PDF로 가중치·임계값 교정
8. pypdf·렌더 기반 필수 검증과 원자적 저장 완성
9. PyInstaller onedir 배포와 네트워크 차단 시험
10. 정식 라이선스 전환 후 최종 검수

## 7. 추가 검증 필요 자료

- 각 축척 템플릿의 GstarCAD 수동 기준 PDF
- 단일·동일 축척 복수·혼합 축척 실제 DWG
- X/Y 이동 및 0°·90°·180°·270° 전체 도곽 회전 도면
- 비균일·미등록·모호·겹침 실패 도면
- XREF·SHX/Big Font·이미지·해치·동적 블록·Proxy 객체 대표 도면

현재 실제 작업 도면 4건과 Window 변동 샘플 2건은 검증했지만 4방향 회전·축척·객체 유형·다중 도곽 조합을 대표하지는 않는다. 나머지 자료가 확보되기 전에는 구현과 dry-run 검증은 가능하지만 자동 매칭 임계값과 전체 운영 범위를 승인할 수 없다.

## 8. 출처와 검증 기준

공식 자료는 2026-07-15~16에 재확인했다.

1. GstarCAD Developer — COM·GRX 등 API 지원  
   https://www.gstarcad.net/developer/
2. GstarCAD Licensing Policy — Stand-alone·Network 라이선스  
   https://www.gstarcad.net/policy/
3. GstarCAD 2026 User Guide — Window, Center Plot, Fit to Paper  
   https://cdn-sg-gw.gstarcad.net/gstarsoft_pdf/GstarCAD_2026_User_Guide.pdf
4. PyInstaller operating mode — Python 미설치 PC용 self-contained 배포와 onedir 우선 검증  
   https://www.pyinstaller.org/en/stable/operating-mode.html
5. pypdf 공식 문서 — PDF 파싱, 페이지·MediaBox 검사  
   https://pypdf.readthedocs.io/en/stable/
6. 2026-07-16 로컬 사전 테스트 — 실제 작업 DWG 4건의 내부 Scale, Extents, PlotToFile, PDF 구조, 렌더, 원본 SHA-256 검증
7. 2026-07-16 로컬 추가 테스트 — Window 위치 변동 DWG 2건의 저장 Plot Window, Extents, 플롯 속성, 원본 SHA-256 검증
8. cad2x-converter 공식 저장소 — CLI 옵션, LGPL-2.1, 정식 Release 없음
   https://github.com/orcastor/cad2x-converter
9. LibreDWG 공식 저장소 — GPL-3.0, 일부 고급 R2010+ 객체 한계
   https://github.com/LibreDWG/libredwg
10. ezdxf 공식 저장소 — DXF 중심, MIT, ODA File Converter 보조 경로
   https://github.com/mozman/ezdxf
