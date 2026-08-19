# v5.134 Grouped Workflow Overview

Target Agent Workflow를 기본 화면에서는 그룹 단위로 단순화합니다.

## 기본 화면

```text
입력 / 검증
  ↓
MCP 파일 처리
  ↓
LLM 요약
  ↓
결과 표시
  ↓
선택적 저장
  ↓
완료
```

기본 화면에서는 각 그룹의 제목과 단계 수만 표시합니다.

## 상세 화면

그룹을 클릭하면 해당 그룹 내부의 세부 Workflow를 기존 카드 스타일로 표시합니다.

예:

```text
MCP 파일 처리
├─ MCP Client 요청
├─ MCP Transport
├─ MCP Server 처리
└─ File MCP Tool 실행
```

`← 전체 Workflow` 버튼으로 다시 그룹 화면으로 돌아갑니다.

## 목적

내부 Workflow의 상세 단계는 유지하면서,
사용자가 전체 흐름을 한눈에 파악할 수 있도록 Overview와 Detail을 분리합니다.
