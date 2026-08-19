# v5.148 Workflow Design Progress

Workflow 설계 버튼을 누른 뒤 결과가 돌아올 때까지 진행 상태를 표시합니다.

표시 항목:
- 진행률 %
- 현재 단계
- 현재 작업 설명
- 진행률 Bar
- 단계 Indicator

단계:
1. 요구사항 준비
2. AI Workflow 설계 요청
3. AI 설계 응답 대기
4. Workflow 검증
5. 완료

주의:
Backend의 `design_agent_factory()`는 현재 한 번의 LLM 호출로 전체 설계 Bundle을 생성합니다.
따라서 응답 대기 중에는 존재하지 않는 내부 Node가 실제로 실행되는 것처럼 표시하지 않고
`AI 설계 응답 대기` 상태와 점진적인 진행 표시를 제공합니다.

응답 수신 후에는 실제 Workflow 요구사항 검증 단계가 표시되고 100% 완료 처리됩니다.
