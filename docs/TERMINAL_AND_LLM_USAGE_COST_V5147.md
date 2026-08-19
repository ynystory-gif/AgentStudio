# v5.147 Terminal Stability + LLM Usage Cost

## Terminal
- 숨겨진 xterm에서 fit 금지
- CODE 탭 복귀 시 컨테이너 실제 크기 확인
- ResizeObserver 적용
- 40/120/260/500/900ms 단계 재보정
- xterm fit/refresh/scrollToBottom
- Monaco layout 복원

## Usage
모든 model_for_task() 호출의 token usage를 logs/llm_usage.jsonl에 기록합니다.

화면:
- 실행 결과: 현재 Agent / 프로젝트 + 오늘 AgentStudio 전체
- 분석 리포트: 현재 Agent / 프로젝트 + 오늘 AgentStudio 전체

표시:
- Input
- Cached Input
- Output
- Total
- Estimated USD cost
