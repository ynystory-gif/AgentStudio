# v5.286 FirestoreNodeContextPythonScriptsFix

- Firestore Collection / Document 노드 우클릭 메뉴를 추가했습니다.
- 메뉴: Google Cloud Firestore 연결코드 / 리스트 조회 / 조회 / 등록 / 수정 / 삭제.
- 선택한 Project ID, Database ID, Service Account JSON 경로와 Collection/Document 경로를 반영해 `.agentstudio/firestore_scratch/*.py`를 생성합니다.
- 생성 파일은 자동 실행하지 않습니다. 삭제 템플릿에는 `CONFIRM_DELETE = False` 보호장치를 둡니다.
- Service Account JSON의 Private Key 본문은 생성 코드에 복사하지 않고 JSON 파일 경로만 사용합니다.
- Firestore Service Account 자동 등록 카드의 설명을 상단, 파일 선택 버튼을 하단 전체 폭으로 재배치했습니다.
- 실행은 기존 `SYSTEM_ADMIN.cmd`만 사용합니다.
