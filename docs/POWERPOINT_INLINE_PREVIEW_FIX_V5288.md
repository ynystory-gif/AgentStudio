# v5.288 PowerPointInlinePreviewFix

## 목적
- `.ppt`, `.pptx` 파일을 원본 손상 없이 AgentStudio 안에서 미리보기합니다.
- 파일을 임의로 재구성하지 않고 PowerPoint/LibreOffice의 실제 렌더러를 사용합니다.

## 변환 우선순위
1. Windows + Microsoft PowerPoint 설치: PowerPoint COM `ExportAsFixedFormat(..., PDF)`
2. PowerPoint 미설치/변환 실패: LibreOffice `soffice --headless` PDF 변환
3. 둘 다 사용 불가: 원본을 건드리지 않고 사용자에게 변환기 설치 안내

## 캐시
- `.agentstudio/preview/presentations/<relative-path-hash>/preview.pdf`
- source SHA-256이 같으면 기존 미리보기를 재사용합니다.
- 원본 파일은 읽기 전용 소스로만 사용하며 저장/덮어쓰기를 하지 않습니다.

## UI
- 기존 PDF Viewer 기반 inline 표시
- 변환기(PowerPoint/LibreOffice), 캐시 사용 여부 표시
- 수동 새로고침 지원
- PPT/PPTX는 코드 저장/LLM 코드 수정 대상에서 제외

## 실행
- 사용자 실행 파일은 기존과 동일하게 `SYSTEM_ADMIN.cmd` 하나입니다.
