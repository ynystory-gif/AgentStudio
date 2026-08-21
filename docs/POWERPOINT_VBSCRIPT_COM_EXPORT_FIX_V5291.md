# v5.291 PowerPointVbScriptComExportFix

## 문제
Windows PowerPoint COM은 정상 등록되고 PPTX도 열렸지만 PowerShell late binding에서
`Presentation.ExportAsFixedFormat($outputPath, 2)`가 메서드가 아니라 COM 속성처럼
잘못 바인딩되어 `Cannot convert the "2" value of type "int" to type "Object"` 오류가
발생할 수 있었다. v5.290의 `SaveAs(..., 32)` fallback도 읽기 전용으로 연 임시
프레젠테이션에서는 PowerPoint 일반 저장 오류(HRESULT 0x80004005)가 발생할 수 있었다.

## 수정
- PowerPoint PDF 변환의 1차 경로를 Windows Script Host(VBScript) IDispatch 호출로 변경.
- 원본은 그대로 보존하고 ASCII 임시 경로에 복사한 사본만 자동화 대상으로 사용.
- 임시 사본을 writable 모드로 열어 `SaveAs(PDF)` fallback도 정상 동작 가능하게 함.
- VBScript에서 `ExportAsFixedFormat outputPath, 2`를 우선 실행.
- 실패 시 `SaveAs outputPath, 32`를 수행.
- Windows Script Host가 없거나 VBScript COM이 실패하면 PowerShell reflection
  `InvokeMember()` 경로로 한 번 더 시도하여 PowerShell 직접 COM binder 문제를 회피.
- PowerPoint가 실패한 경우에만 기존 LibreOffice fallback 실행.
- 단계별 진단은 VBScript COM / PowerShell COM reflection을 구분해 표시.

## 안전성
- 사용자의 원본 PPT/PPTX는 읽기만 하며 수정/저장하지 않는다.
- 자동화는 AgentStudio 임시 사본에서만 수행한다.
- preview.pdf 캐시 정책은 기존과 동일하다.
