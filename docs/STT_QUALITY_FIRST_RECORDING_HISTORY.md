# STT 품질 우선 처리 및 이전 녹음 기록 정책 (v5.574)

- 녹음 중에는 `AGENTSTUDIO_STT_MODEL`(기본 small)로 빠른 임시 Transcript만 표시한다.
- 녹음 정지 후 전체 PCM을 `AGENTSTUDIO_STT_REFINE_MODEL`(기본 medium)로 다시 분석해 최종 Transcript로 교체한다.
- GPU 사용은 명시적으로 `AGENTSTUDIO_STT_REFINE_DEVICE=cuda`, `AGENTSTUDIO_STT_REFINE_COMPUTE_TYPE=float16`을 선택했을 때 사용한다.
- 요약/분석 입력에서는 `[00:15:46]`, `00:15:46` 형식의 녹음 시간과 UI 상태 문구를 제거한다. Timestamp는 Transcript segment metadata에는 유지한다.
- 녹음 종료 시 최종 Transcript를 자동 저장하고 프로젝트 `.agentstudio/recording_history.json`에 기록한다.
- 요약정리를 실행하면 요약도 같은 recording_id로 자동 저장한다.
- 이전 녹음 기록 목록에서 항목을 클릭하면 저장된 최종 Transcript와 요약이 있으면 함께 표시한다.
