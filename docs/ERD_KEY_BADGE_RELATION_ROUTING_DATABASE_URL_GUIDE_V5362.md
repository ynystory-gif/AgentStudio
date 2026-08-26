# v5.362 ErdKeyBadgeRelationRoutingDatabaseUrlGuide

## 목적

1. PowerPoint DB ERD에서 PK/FK 표기가 세로로 눌리지 않도록 가로 배지를 보장합니다.
2. 여러 FK 관계선이 하나의 수평선으로 겹쳐 방향을 구분하기 어려운 문제를 해결합니다.
3. 생성 Agent의 첫 실행에서 `DATABASE_URL=`에 무엇을 입력해야 하는지 `.env`와 콘솔에서 즉시 알 수 있게 합니다.

## DB ERD PPT

- PK/FK 배지 폭을 고정하고 `word_wrap=False`로 처리합니다.
- 키 배지, 컬럼명, 타입 영역을 독립 좌표로 배치합니다.
- 상·하위 테이블 사이에 전용 relation routing corridor를 확보합니다.
- 각 relation에 고유 lane을 배정하고 parent/child card anchor도 분산합니다.
- relation은 `parent(PK) -> child(FK)` 방향의 화살표로 표시합니다.
- relation마다 색을 순환 적용하여 교차/근접 관계의 추적성을 높입니다.
- 관계 수가 많으면 한 슬라이드의 table chunk를 6 -> 5 또는 4로 자동 축소합니다.

## 생성 Agent DATABASE_URL 안내

생성 Agent의 `.env`에 `DATABASE_URL=`이 있고 값이 비어 있으면 `SYSTEM_ADMIN.ps1`이 다음 안내를 해당 키 바로 위에 자동 삽입합니다.

```dotenv
# DATABASE_URL 입력 방법 (PostgreSQL)
# 형식: postgresql://사용자:비밀번호@호스트:포트/데이터베이스명
# 로컬 예시: postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/postgres
# YOUR_PASSWORD와 마지막 DB 이름을 실제 PostgreSQL 환경에 맞게 변경하세요.
DATABASE_URL=
```

`DATABASE_URL`이 미설정이면 콘솔 `[SETUP_REQUIRED]` 화면에도 같은 형식/예시를 표시한 뒤 `.env`를 메모장으로 엽니다.

실제 비밀번호를 AgentStudio가 임의 생성하거나 하드코딩하지 않습니다.
