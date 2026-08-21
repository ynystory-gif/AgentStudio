# v5.287 FirestoreCompactFieldRowsFix

## 문제
Firestore Document 상세의 Field 테이블 행이 상세 패널의 남는 세로 공간을 채우며 과도하게 늘어나는 문제가 있었습니다.

## 수정
- Field 테이블/thead/tbody/tr/td 높이를 콘텐츠 기준 `auto`로 고정
- 테이블 자체가 상세 영역 높이를 강제로 채우지 않도록 `height: max-content` 적용
- 일반 단일 값 Field는 compact row로 표시
- Map/Array 등 긴 Value는 최대 180px에서 내부 스크롤
- 상세 패널 전체 스크롤 구조는 유지

## 실행
기존과 동일하게 `SYSTEM_ADMIN.cmd`만 사용합니다.
