# v5.149 Agent Development Progress

`개발 시작` 버튼을 누르면 Agent Factory 실행 상태를 Progress UI로 표시합니다.

## 표시 항목

- 현재 진행률 %
- 경과 시간(초)
- 현재 단계
- 현재 작업 설명
- Progress Bar
- 단계 Indicator

## 단계

1. 개발 준비
2. Agent Factory 시작
3. 코드 생성 / 검증 진행 중
4. 테스트 / 자동 복구 진행 중
5. 패키징 / 최종 검토 진행 중
6. 개발 결과 정리
7. 완료

## 정확성

현재 `/workflow/start` API는 LangGraph 전체 Agent Factory Workflow가 끝난 뒤
최종 State를 한 번에 반환합니다.

따라서 API 응답 전 진행률은 사용자에게 대기 상태를 알리기 위한 점진적 진행 표시이며,
개별 LangGraph Node가 실제 완료됐다고 단정하지 않습니다.

최종 응답이 도착하면 실제 `state.status`를 사용해 94% → 100% 완료 처리합니다.

향후 LangGraph event streaming(SSE/WebSocket)을 연결하면 이 Progress UI를
실제 Node별 진행률로 교체할 수 있습니다.
