# v5.145 Persistent Code Workspace

## 문제

다른 탭으로 이동했다가 CODE 탭으로 돌아오면 Terminal 화면이 깨졌습니다.

원인은 기존 숨김 방식이었습니다.

```css
width: 1px;
height: 1px;
```

xterm이 숨겨진 1px 컨테이너를 실제 Terminal 크기로 인식하고 `fit()`을 수행하면서
열/행 크기가 망가졌습니다.

## 수정

### Terminal

- xterm DOM을 unmount하지 않음
- 다른 탭에서는 `display:none`
- 숨겨진 동안 `fit()` 호출 금지
- CODE 탭 복귀 후에만 모든 Terminal에 `fit()` / `refresh()` 적용
- 활성 Terminal은 `scrollToBottom()` 복원

### Monaco / 열린 파일

CODE 상단 Editor도 조건부 unmount하지 않고 항상 React DOM에 유지합니다.

다른 탭:
- `display:none`

CODE 복귀:
- 같은 Editor instance 재사용
- `editor.layout()` 호출
- 열린 파일 탭 유지
- 선택된 파일 유지
- 수정 중인 내용 유지
- dirty 상태 유지

### 유지되는 상태

- 열린 파일 목록
- 현재 선택 파일
- 저장되지 않은 코드
- 파일별 dirty 상태
- LLM 코드 편집 대화
- Terminal 탭
- Terminal process/WebSocket
- Terminal 화면 buffer/history
- 활성 Terminal
