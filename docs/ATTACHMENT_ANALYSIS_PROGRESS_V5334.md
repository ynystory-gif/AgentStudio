# v5.334 Attachment Analysis Progress

## 목적

참고 파일을 등록한 사용자가 AgentStudio가 실제로 파일을 읽고 있는지, 어떤 파일이 준비됐는지 알 수 있도록 파일별 분석 준비 진행 상태를 제공한다.

## 표시 원칙

LLM/Ollama/OpenAI/Codex 내부에는 파일별 정확한 처리 퍼센트가 제공되지 않는다. 따라서 AgentStudio는 임의의 AI 처리율을 만들지 않고 Backend에서 실제로 관찰 가능한 파일 처리 단계만 수치화한다.

- 0%: 대기
- 15%: 파일 존재/크기 확인
- 45%: 파일 형식별 텍스트 추출
- 85%: AI Context 준비
- 100%: 준비 완료

준비 완료 후 실제 LLM/Codex 요청이 실행되면 Progress Bar는 100%를 유지하고 상태 문구만 `AI 분석에 사용 중`으로 전환한다.

## 적용 위치

- Agent 설계 인터뷰
- LLM 대화형 파일/프로젝트 코드 편집
- 오른쪽 Codex 패널

세 화면은 공통 `AiAttachmentPicker`를 사용하므로 동일한 진행 표시와 오류 처리 규칙을 공유한다.

## Backend

`POST /api/ai/attachments/analyze`는 `AI_ATTACHMENT_ANALYSIS` Background Job을 만들고 `/api/jobs/{job_id}`에서 파일별 진행 metadata를 제공한다. 실제 파일 본문은 progress 응답에 포함하지 않는다.

`prepare_attachment()`는 추출한 텍스트를 attachment id별 메모리 캐시에 저장한다. 파일 크기와 `mtime_ns`가 동일한 동안 `build_attachment_context()`가 캐시를 재사용하며, 파일이 변경되면 자동으로 다시 추출한다.

## 디스크 I/O 정책

v5.333의 idle disk I/O 개선을 유지한다. 첨부 progress는 활성 Job 동안만 짧게 조회하며, 참고 파일이 없거나 분석이 끝난 뒤에는 추가 polling을 하지 않는다.
