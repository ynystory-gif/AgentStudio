# v5.378 PDF Multi-Extractor Search + Notebook Runtime Context Isolation

## PDF 검색
- pypdf layout/plain + PyMuPDF sorted text 다중 추출기
- NFKC, zero-width, 공백/줄바꿈 보정
- 일반 검색 실패 시 구두점/기호 무시 fallback
- 페이지별 중복 결과 통합
- 새 검색 시 이전 PDF navigation 상태 제거
- request sequence로 stale async response 차단

## Notebook 실행
- NotebookEditor가 열린 projectRoot를 실행 요청에 직접 전달
- Notebook 파일별 안정적인 runtime session id 사용
- 출력 터미널 id와 Python worker session id 분리
- 프로젝트 .venv interpreter가 변경되면 기존 worker 자동 폐기/재생성
- PDF 검색/탭 전환이 Notebook 실행 root/interpreter를 변경하지 않도록 격리
