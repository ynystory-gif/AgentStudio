# v5.359 FastInterviewStateDedupRepairRecovery

## 문제 1: 짧은 인터뷰가 오래 걸림

v5.357은 요구사항 인터뷰의 매 사용자 턴마다 `requirements_interview` LLM 호출을 수행했습니다. 로컬 Ollama 모델을 선택한 환경에서는 짧은 확인/요구사항 추가도 수십 초가 걸릴 수 있었습니다.

### 개선

- 최초 목적 분석 또는 새 첨부 파일의 실제 분석은 기존 LLM 경로를 유지합니다.
- 이미 인터뷰가 시작된 420자 이하의 짧은 사용자 턴은 결정적 Fast Path를 사용합니다.
- Fast Path는 사용자 대화 + 저장된 첨부 요구사항 요약에서 알려진 항목을 확인하고, 아직 질문하지 않은 미확정 항목 하나를 선택합니다.
- DB Preview는 인터뷰 응답 처리 중 실행하지 않고 응답 완료 후 갱신합니다.

## 문제 2: 첨부 파일 안내/질문 반복

기존 구현은 `attachment_memory`와 새 첨부 원문 Context를 합친 값을 Echo Guard 근거로 사용했습니다. 이미 안전하게 요약된 첨부 메모리까지 매 턴 Echo 검사 대상이 되어 로컬 모델 출력이 보호 조건에 걸릴 때 고정 fallback 문장이 반복될 수 있었습니다.

### 개선

- `fresh_attachment_context`: 이번 턴 새 첨부 자료
- `attachment_memory`: 이전에 분석 완료된 요구사항 요약/메모리

두 값을 분리합니다. Echo Guard/첨부 완료 fallback은 `fresh_attachment_context`가 있을 때만 동작합니다.

또한 최근 Assistant 응답과의 유사도 및 이미 질문한 Requirement Slot을 검사해 동일 응답과 동일 질문을 연속해서 출력하지 않습니다.

## 문제 3: Focused Repair Plan 불완전 오류

테스트 실패 후 Patch LLM이 대상 파일에 대해 유효한 `replacements`를 반환해도 v5.357은 `replace_entire_file=true + content`만 인정했습니다. 또한 스택 트레이스에서 여러 후보 파일을 찾은 경우 모든 후보의 전체 파일 Patch가 한 번에 생성되지 않으면 전체 개발이 종료되었습니다.

### 개선

1. `replacements`를 PatchService의 안전 치환 규칙으로 메모리에서 적용해 전체 파일 `content`로 승격합니다.
2. 대상 파일 Patch가 없거나 형식이 잘못되면 동일 파일 하나만 넣은 Focused Patch Recovery를 한 번 재시도합니다.
3. 여러 후보 중 일부만 안전하게 수정할 수 있으면 해당 Patch를 먼저 적용하고 테스트를 재실행합니다.
4. 실제 실패가 남아 있을 때 다음 Debug 반복이 남은 원인만 다시 분석합니다.

이 방식은 호출 스택의 모든 파일을 무조건 수정하는 것보다 안전하며, 유효한 수정이 있는데도 `TEST_REPAIR_PLAN_INCOMPLETE`로 조기 종료되는 문제를 줄입니다.
