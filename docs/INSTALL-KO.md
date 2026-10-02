# Windows 설치·실행 안내

준비 조건은 Windows x64, 정식 GstarCAD 2026과 `GStarCAD.Application.26` COM 등록, `DWG To PDF.pc3`, `monochrome.ctb`, A4 가로 297×210 mm 용지입니다. 실행 ZIP에는 Python 런타임과 기준 템플릿이 포함되며 CAD·라이선스·폰트는 포함하지 않습니다.

## 설치

1. `releases/windows/dwg-to-pdf-validation.zip` 또는 GitHub Release의 같은 파일을 받습니다.
2. ZIP을 `C:\DWG-PDF` 등 로컬 폴더에 전체 압축 해제합니다.
3. `dwg-to-pdf-validation` 폴더 안의 EXE와 `_internal`을 함께 유지합니다.
4. PowerShell에서 해당 폴더로 이동하여 `.\dwg-to-pdf.exe --self-check`를 실행하고 `RUNTIME_SELF_CHECK_OK`를 확인합니다.
5. EXE를 더블클릭하고 대표 DWG 1개를 변환합니다. PDF의 방향·도곽·잘림·누락을 육안 확인한 뒤 일괄 작업합니다.

압축 파일 안에서 EXE만 실행하거나 EXE만 다른 폴더에 복사하지 마세요. 새 PC 호환성은 해당 PC에서 실제 변환으로 확인합니다.

## 무결성 확인

배포 폴더의 `SHA256SUMS.txt`와 다음 명령 결과를 비교합니다.

```powershell
Get-FileHash .\dwg-to-pdf-validation.zip -Algorithm SHA256
```

ZIP 안의 `dwg-to-pdf-validation-checksums.csv`는 파일별 체크섬입니다.

## 오류 대응

| 현상 | 확인할 내용 |
| --- | --- |
| EXE가 시작되지 않음 | 전체 압축 해제, `_internal` 유지, 보안 프로그램 차단 기록 |
| CAD 연결 오류 | GstarCAD 2026 설치·최초 실행·라이선스·COM 등록 |
| PDF 플롯 설정 실패 | PC3, CTB, A4 용지와 CAD 사용자 환경 |
| 템플릿 매칭 실패 | 13개 승인 규격, 단일 Scale 라벨, 도곽 구조·축척 |
| 출력 저장 실패 | 출력 폴더 권한, PDF 잠금, 충돌 정책 |

파일명·실패 사유·로그와 사용한 버전을 보존해 담당자에게 전달합니다.

### 네이티브 추출 호환 설정

추가 개선본에는 `bulk_extract.lsp`가 포함되어 있습니다. APP은 자체 CAD의 임시 작업 복사본에서 이 파일을 로드합니다. LISP 로드를 제한하는 보안 정책은 임의 해제하지 마십시오. 필요한 경우 `_internal/config.toml`의 `[matching]` 아래 `use_native_extraction=false`로 기존 COM 경로를 사용합니다. 사용자 지정 설정은 `--config`로 지정할 수 있습니다. 다른 PC는 대표 도면으로 반드시 실제 출력을 확인하십시오.
