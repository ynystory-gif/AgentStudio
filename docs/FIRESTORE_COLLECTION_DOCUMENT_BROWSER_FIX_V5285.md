# v5.285 FirestoreCollectionDocumentBrowserFix

Google Cloud Firestore 연결 후 비어 있던 우측 DB 영역을 실제 읽기 전용 Browser로 확장했습니다.

## 동작

1. 연결 직후 최상위 Collection 목록을 조회합니다.
2. Collection을 선택하면 해당 Collection의 Document를 최대 500개까지 lazy load합니다.
3. Document를 선택하면 Field 이름, Firestore 타입, 값, create/update/read time을 표시합니다.
4. Document 아래 Subcollection이 있으면 이름을 함께 표시합니다.
5. Collection/Document 검색과 새로고침을 지원합니다.

## 안전성

- 전체 Collection의 Document count를 자동 집계하지 않아 불필요한 Firestore read 비용을 피합니다.
- Browser는 읽기 전용이며 생성/수정/삭제를 자동 수행하지 않습니다.
- Firestore 값은 JSON-safe 표현으로 변환해 Timestamp/Map/Array/Reference/GeoPoint 등도 UI가 깨지지 않게 표시합니다.
