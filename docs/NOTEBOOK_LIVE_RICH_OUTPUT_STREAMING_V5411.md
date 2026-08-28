# v5.411 Notebook Live Rich Output Streaming

AgentStudio Notebook 실행기는 persistent Python worker를 유지하지만 완전한 ipykernel은 사용하지 않습니다. 따라서 기존에는 `IPython.display.display(fig)`가 브라우저의 셀 출력으로 실시간 전달되지 못하고 `Figure(700x600)` 같은 텍스트만 남을 수 있었습니다.

v5.411은 Notebook 실행에 별도 Rich Output 이벤트 프로토콜을 추가합니다.

- `clear_output(wait=True)` → 즉시 `clear_output` 이벤트
- `display(fig)` → Matplotlib Figure를 PNG MIME bundle로 직렬화해 즉시 `display_data` 이벤트
- Backend `/python/execute/stream` → NDJSON StreamingResponse
- Frontend → 실행 중 같은 셀의 출력 영역을 프레임 단위로 갱신
- 마지막 프레임 → `rich_outputs`로 최종 Notebook output에 보존

따라서 학습 루프에서 `clear_output(wait=True)`, `display(fig)`, `time.sleep(...)`을 사용하면 VS Code/Jupyter처럼 Epoch가 진행되는 동안 결정 경계 이미지가 계속 바뀝니다.
