# v5.290 PowerPointWindowsComFallbackDiagnosticsFix

## 목적
PowerPoint가 설치된 Windows PC에서도 PPT/PPTX 미리보기 PDF 변환이 실패할 때 원인을 식별하고 더 안정적인 Office COM fallback을 제공합니다.

## 변경
- PowerPoint.Application COM 등록 및 POWERPNT.EXE 경로 진단
- Windows PowerShell STA 명시
- 원본 파일을 임시 ASCII 경로로 복사한 뒤 사본만 변환
- ExportAsFixedFormat 실패 시 SaveAs PDF fallback
- LibreOffice 탐색 경로 확대
- 변환기별 상세 실패 이유를 Frontend Viewer에 표시
- 원본 PPT/PPTX는 수정하지 않음
