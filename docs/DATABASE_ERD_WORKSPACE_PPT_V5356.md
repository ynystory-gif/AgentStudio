# THEANOVA AgentStudio v5.356 — Database ERD Workspace + PPT

## 목적

v5.356은 신규 Agent 생성 결과 또는 기존 프로젝트 로드 결과에서 사용되는 데이터 저장소를 분석하여 **DB 종류별로 독립된 ERD / 논리 데이터 모델**을 제공합니다. 아키텍처 탭 오른쪽에 `DB ERD` 탭을 추가하고, 페이지 PPT / Agent 전체 PPT / Studio 전체 PPT에 ERD를 연동합니다.

## Workspace

- 탭 순서: `아키텍처` → `DB ERD` → `LLM 리스트`
- `DB ERD` 진입 시 현재 프로젝트를 다시 분석합니다.
- 관계형 DB와 pgvector는 기존 Database Diagram Viewer를 재사용합니다.
- Redis는 관계형 ERD가 아니므로 Key Pattern / 역할 / TTL / Data Type 기반 논리 데이터 모델을 표시합니다.
- Firestore는 Collection 단위 논리 데이터 모델을 표시합니다.

## DB별 분리 원칙

한 프로젝트가 여러 저장소를 사용하면 하나의 ERD에 섞지 않고 DB별로 분리합니다.

예:

- PostgreSQL → PostgreSQL ERD
- Microsoft SQL Server → SQL Server ERD
- Oracle → Oracle ERD
- SQLite → SQLite ERD
- MySQL/MariaDB → MySQL ERD
- pgvector → Vector Store ERD
- Redis → Redis Key Model
- Firestore → Collection Model

신규 Agent 생성 전에는 Agent Factory의 `database_plan`을 우선 사용하고, 기존 프로젝트는 SQL DDL 및 소스 분석 결과를 사용합니다. 실제 소스에 여러 SQL DB의 DDL이 있으면 엔진별로 분리하여 생성합니다.

## PPT Export

### 페이지 PPT

`DB ERD` 탭의 `PPT 다운로드`는 **현재 Agent 또는 현재 로드된 프로젝트만** 대상으로 합니다.

- 관계형 DB: Table Card, Column, PK/FK, Relationship
- pgvector: VECTOR Column과 직접 관련된 Table/Relationship
- Redis: Key Pattern / Purpose / TTL / Data Type
- Document DB: Collection Card

### Agent PPT

상단 `Agent PPT` 전체 문서에는 현재 Agent/프로젝트의 DB ERD가 추가됩니다. AgentStudio 자체 ERD는 포함하지 않습니다.

### Studio PPT

상단 `Studio PPT` 전체 문서에는 THEANOVA AgentStudio 자체 DB ERD가 추가됩니다. 현재 선택된 Agent/프로젝트의 ERD는 포함하지 않습니다.

AgentStudio 정적 소유 Schema는 `backend/sql/supabase_agentstudio_full_schema.sql`을 기준으로 PostgreSQL/Supabase ERD를 구성하며, VECTOR 컬럼이 존재하면 pgvector 논리 ERD도 별도 구성합니다. LangGraph Checkpointer처럼 라이브러리 `setup()`이 런타임에 생성하는 내부 테이블은 정적 AgentStudio 소유 SQL과 구분합니다.

## PPT 편집 가능성

- Table/Card/Title/Relationship Line은 PowerPoint 네이티브 도형으로 생성합니다.
- 텍스트는 PPT에서 직접 편집할 수 있습니다.
- Redis/Document Store도 카드 기반으로 생성하여 편집 가능합니다.
- 전체 ERD를 한 장의 스크린샷 이미지로 넣지 않습니다.

## 오류 및 Fallback

- DB 사용은 감지했지만 DDL/Schema가 없으면 해당 DB 탭을 유지하고 “Schema를 아직 찾지 못했습니다” 상태를 표시합니다.
- ERD 재분석 실패가 Agent/Studio 전체 PPT 다운로드 자체를 막지 않도록 기존 Snapshot으로 fallback합니다.
- Redis Key Pattern이 없으면 Redis 사용 감지 상태를 유지합니다.

## 검증

v5.356 계약 검증 범위:

- PostgreSQL + SQL Server + pgvector + Redis를 한 프로젝트에서 각각 분리
- FK Relationship 검출
- Redis Key Model 검출
- DB ERD 페이지 PPT 생성
- Agent PPT에 프로젝트 ERD 포함 및 Studio ERD 격리
- Studio PPT에 AgentStudio ERD 포함 및 프로젝트 ERD 격리
- 기존 Agent/Studio PPT 분리, Project Adaptive Architecture, Notebook, Search 기능 회귀 검증
