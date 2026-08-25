# v5.338 Attachment Intent Summary & Requirement Redefinition

## 목적

Agent 설계 인터뷰에서 참고 파일을 선택했을 때 파일 추출 완료 여부만 보여주는 대신, 여러 파일의 내용을 통합해 사용자가 만들고자 하는 프로그램/Agent 요구사항을 먼저 정리해 보여줍니다. 또한 기존 프로젝트 경로에서 이전 요구사항 Draft를 복원한 뒤에도 과거 대화와 수집 요구사항을 사용자가 직접 삭제·재정의할 수 있게 합니다.

## 첨부 파일 요구사항 요약

1. 기존 파일별 분석 Progress를 그대로 사용합니다.
2. 텍스트 추출이 완료되면 `/chat/interview/attachments/summary`를 호출합니다.
3. Backend는 요구사항 인터뷰 전용 압축 Context를 사용하며 API Key, Token, Password, DB credential은 AI Context 진입 전에 마스킹됩니다.
4. Adaptive Provider Router의 `REQUIREMENTS_ANALYSIS` 작업으로 Ollama를 우선 사용하고 설정에 따라 OpenAI/Codex fallback을 사용할 수 있습니다.
5. 사용자에게는 다음 항목을 1,500자 이내로 표시합니다.
   - 만들고자 하는 내용
   - 핵심 기능
   - 입력 / 데이터
   - 기술 / 연동
   - 추가 확인이 필요한 항목
6. 파일 원문, 긴 코드, CSV 원시 행은 사용자 요약에 출력하지 않습니다.
7. 요약 완료 후 원본 attachment id는 해제하고 안전한 요구사항 요약만 세션 Context로 유지합니다.

## 이전 대화 삭제 및 재정의

우측 요구사항 수집 현황에 `지난 대화 / 요구사항 삭제·재정의` 영역을 추가합니다.

- 사용자 답변 개별 삭제: 해당 사용자 답변과 바로 다음 AI 응답을 함께 제거합니다.
- 지난 내용 전체 삭제 후 재정의: 저장된 요구사항 Draft만 초기화하며 프로젝트 파일 자체는 삭제하지 않습니다.
- 요구사항 항목별 재정의: 목적, 파일 형식, 결과 형식, LLM, UI, Backend, MCP/Transport, DB, 권한/파일 접근, 실행 환경, 처리 제한을 새로운 값으로 덮어쓸 수 있습니다.
- 수동 재정의 값은 기존 대화보다 우선하며 Draft와 Workflow 요청에 명시적으로 저장됩니다.
- 요구사항이 바뀌면 기존 Workflow Preview/Quality를 폐기하고 `REQUIREMENTS` 단계로 되돌려 오래된 설계로 프로젝트가 생성되는 것을 방지합니다.
