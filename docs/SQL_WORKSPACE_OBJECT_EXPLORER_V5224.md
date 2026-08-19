# v5.224 SQL Workspace Object Explorer

- SQL 파일에서도 하단 좌측에 기존 `LLM 대화형 코드 편집`을 유지합니다.
- 하단 우측은 `Data Output / Messages` SQL 실행 결과 영역으로 사용합니다.
- DB 연결 후 우측 `DB 연결` 패널 하단에 `DB Object Explorer`를 표시합니다.
- PostgreSQL / MSSQL / Oracle별로 테이블, 뷰, 프로시저, 함수, 시퀀스, 트리거를 조회합니다.
- Oracle은 패키지 목록도 표시합니다.
- 테이블/뷰는 펼치면 컬럼명, 타입, NULL 허용 여부를 확인할 수 있습니다.
- 연결이 유지되는 동안 SQL 파일을 바꾸거나 Frontend를 새로고침해도 기존 연결을 재사용하고 객체 목록을 다시 읽습니다.
