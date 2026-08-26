# v5.360 DeepAttachmentRequirementMining + RootSourceFenceRepair

## 목적

요구사항이 많은 Notebook/문서 첨부를 단순 기술 요약으로 축소하지 않고, Markdown 문제 문장·bullet·제약·산출물·데이터 조건을 source-grounded Requirement Registry로 추출한다. 동시에 Agent 개발 테스트에서 프로젝트 루트 파일을 잘못된 동명 파일로 Repair하거나, LLM이 소스 전체를 Markdown code fence로 감싸 저장해 `SyntaxError`가 발생하는 문제를 결정적으로 복구한다.

## Deep Attachment Requirement Mining

- Notebook의 Markdown Cell을 코드보다 우선 분석한다.
- Heading, bullet, 일반 한국어 요구사항 문장, 제약, 산출물, 제공자료를 후보로 보존한다.
- 긴 Markdown 문단은 문장 단위로 분해하여 각각의 요구사항 후보를 유지한다.
- 요구사항 후보를 `REQ-001...` ID로 관리한다.
- UI / SEARCH / DATABASE / CACHE / DATA / LLM / MCP_TOOL / BACKEND / SECURITY / OUTPUT / RUNTIME / CONSTRAINT / ORDER / ANALYTICS 등으로 분류한다.
- 각 요구사항에 원본 파일명과 Notebook Cell 위치를 함께 저장한다.
- 요약 LLM은 Requirement Registry를 먼저 전달받아 명시적 요구사항을 누락하지 않도록 한다.
- 일반 인터뷰에서도 두 번째 LLM 호출 없이 Registry와 빠른 요약을 즉시 화면에 표시한다.
- Draft 저장/복원 시 요구사항 목록과 Coverage 정보도 함께 복원한다.
- Workflow/DB Preview/코드 생성 요청에도 Attachment Requirement Registry를 포함한다.

## Interview Slot Completion

- 사용자가 `없다`, `필요 없다`, `사용하지 않는다`라고 답한 항목을 정상 완료값으로 처리한다.
- 한 번 질문한 Slot에 사용자가 응답하면 해당 Slot을 완료 처리한다.
- 이미 물어본 미확정 질문을 자동 반복하지 않는다.
- `파일은 없다. 데이터는 최대 100건` 같은 문장은 입력 파일 없음과 조회 제한을 동시에 반영할 수 있도록 Fast Interview confirmation을 보완했다.

## Agent 개발 실패 복구

진단 자료에서 실제 실패 파일은 `C:\AI\MINI_PRO\main.py`였지만 이전 Repair는 같은 basename의 `backend/app/main.py`를 선택했다. 테스트 로그에는 `\.\main.py`가 명시되어 있었으므로 v5.360은 이 프로젝트-root 상대 경로를 File Plan의 동명 파일보다 우선한다.

또한 생성 코드가 파일 전체를 Markdown fence로 감싼 형태(예: 첫 줄이 `\`\`\`python`, 마지막 줄이 `\`\`\``)로 저장될 경우:

    ```python
    ...python source...
    ```


소스 확장자와 fence 언어가 일치하고 파일 전체가 fence로 감싸진 경우에만 외부 fence를 자동 제거한다.

- Patch 적용 시 신규/전체 교체 source에서 즉시 제거
- Test 실행 직전 기존 프로젝트 source도 한 번 더 검사하여 자동 복구
- Markdown 문서 자체는 변경하지 않음
- root `main.py`와 `backend/app/main.py`처럼 basename이 같은 파일이 있어도 테스트가 명시한 정확한 상대경로를 우선

## 완료 조건

- 요구사항이 많은 `.ipynb`에서 단순 기술 3~5개가 아니라 명시적 문제 요구사항을 다수 추출한다.
- 화면에서 `추출 요구사항` 목록과 출처를 확인할 수 있다.
- `없다` 답변 뒤 같은 질문이 반복되지 않는다.
- `\.\main.py` SyntaxError가 `backend/app/main.py`로 잘못 Repair되지 않는다.
- 전체 source Markdown fence는 테스트 전에 자동 제거된다.
