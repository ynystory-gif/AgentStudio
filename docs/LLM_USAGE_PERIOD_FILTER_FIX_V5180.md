# v5.180 LLM Usage Period Filter Fix

유료 토큰 / 비용 패널의 AgentStudio 전체 집계를 기간별로 조회할 수 있도록 확장했습니다.

- 기본: AgentStudio 오늘 전체
- 전체 누적
- 월별 선택 (`YYYY-MM`)
- 일별 선택 (`YYYY-MM-DD`)
- 현재 Agent / 프로젝트 카드는 기존 의미를 유지해 오늘 사용량을 표시합니다.
- 모든 조회는 기존 `logs/llm_usage.jsonl` 기록을 집계하며 새로운 LLM 호출을 발생시키지 않습니다.
