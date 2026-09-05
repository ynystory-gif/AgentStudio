# THEANOVA AgentStudio v5.602 — History List SQL / Schema SQL / DB Binding Semantics / Dynamic Qwen

## 변경 사항

1. **이력 목록 SQL 버튼 위치 수정**
   - 개별 이력 아이템의 SQL 버튼을 제거했습니다.
   - `총 N건 / 전체 분류`가 있는 목록 조회 도구 영역에 하나의 `SQL` 버튼을 배치했습니다.
   - 현재 프로젝트, 분류, 조회 제한을 반영한 목록 조회 SQL 임시 파일을 생성합니다.
   - 상세 화면의 `SQL 임시 파일` 버튼은 유지합니다.

2. **생성 SQL Schema 명시**
   - 프로젝트 수정 이력 목록/상세 SQL은 현재 Runtime Schema를 명시합니다.
   - LLM 학습 센터의 오판/Dataset/PC별 학습 적용 SQL도 동일하게 Schema를 명시합니다.
   - PostgreSQL/Supabase 테이블 SQL은 `"schema"."table"` 형식을 기본으로 사용합니다.

3. **계정 DB Profile → Agent 프로젝트 적용 이력 의미 수정**
   - PostgreSQL, Redis, Firestore를 각각 별도 Project Setting key로 저장합니다.
   - 처음 추가된 DB Provider는 `CREATE / 신규`입니다.
   - 같은 Provider의 설정이 실제로 달라진 경우만 `UPDATE / 변경`입니다.
   - 동일 값 재저장은 DB/History를 추가하지 않습니다.
   - v5.601에서 하나의 `default` key 때문에 PostgreSQL → Redis가 UPDATE로 남은 기존 audit row는 삭제/재작성하지 않고, 서로 다른 Provider를 추가한 legacy row에 한해 화면 action을 `신규` 의미로 표시합니다.

4. **Qwen 최신 권장 모델 / 동적 표시**
   - 최신 권장: `qwen3.8:27b-mtp-q4_K_M`
   - 기존 qwen3.5 프로젝트 설정은 강제로 변경하지 않습니다.
   - 기존 Qwen3.5-4B QLoRA weight-training 호환 경로도 유지합니다.
   - 메인 AI Trends와 LLM 학습 센터가 동일한 Backend Qwen resolver를 사용합니다.
   - 프로젝트 설정 → 계정 설정 → AgentStudio 현재 설정/기본값 → 설치된 Qwen fallback 순서로 표시 모델을 결정합니다.
   - 프로젝트 전환 시 메인 Dataset 모델 표시도 새 프로젝트 기준으로 갱신합니다.
   - provider/family/model/version/parameter/quantization/MTP/install 정보를 구조화해 전달합니다.

## 회귀 보호

- 기존 Prompt/Tool 동기화, Workflow 저장, no-op 저장 방지 유지
- 기존 qwen3.5 설정 유지
- Frontend에 최신 권장 모델을 현재 모델로 하드코딩하지 않음
- SQL 실행은 자동 수행하지 않고 임시 파일 생성만 수행
