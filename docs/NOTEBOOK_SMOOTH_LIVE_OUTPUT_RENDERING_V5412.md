# v5.412 Notebook Smooth Live Output Rendering

## 문제

`clear_output(wait=True)` + `display(fig)` 애니메이션에서 v5.411 Frontend가 clear 이벤트를 받는 즉시 현재 출력 배열을 비웠습니다. 그 결과 다음 PNG가 도착하기 전 짧은 시간 동안 출력 영역이 비어 반복적인 번쩍임이 보였습니다.

## 수정

1. `wait=True` clear는 실제 삭제하지 않고 `pendingLiveClearWaitRef`에 예약합니다.
2. 다음 Rich Output 이벤트가 도착하면 예약된 clear와 새 output 삽입을 한 번의 React state update로 처리합니다.
3. 재실행 시작 시 기존 저장 프레임을 유지하고 첫 새 출력이 도착할 때 교체합니다.
4. PNG data URI는 `Image()`로 preload/decode한 후 화면 `<img>` 소스를 변경합니다.
5. Backend `rich_outputs`도 wait=True clear를 다음 output까지 지연해 Jupyter 의미를 유지합니다.

## 기대 동작

Epoch 1 → Epoch 2 → ... 형태로 같은 위치의 이미지가 계속 교체되며 중간에 빈 출력 영역이 나타나지 않습니다.
