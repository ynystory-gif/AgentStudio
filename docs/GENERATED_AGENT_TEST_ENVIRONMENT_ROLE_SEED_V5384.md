# v5.384 GeneratedAgentTestEnvironmentRoleSeed

## 목적
신규 생성 Agent를 관리자가 즉시 검증할 수 있도록 관리자 `테스트 환경` 기능을 Agent Factory 기본 계약으로 추가합니다.

## 자동 Seed
- 로그인/회원: 테스트 회원 10명
- 상품: 상품 50, 카테고리 5, 재고 50
- 주문: 주문 20 및 주문상세
- RAG: 문서 20, Chunk 100
- 상담/Memory: 세션 20, 메시지 100, Memory 30
- 예약: 서비스 10, 슬롯 100, 예약 20

실제 생성 항목은 Agent 요구사항과 DB/Auth 설계를 분석해 필요한 것만 선택합니다.

## 권한별 테스트 계정
Role/Permission이 있으면 모든 발견 Role에 대해 테스트 계정을 만들 수 있도록 설계합니다. 기본 예시는 `SUPER_ADMIN 1`, `ADMIN 2`, `MANAGER 2`, `STAFF 3`, `USER 10`이며 실제 Role은 해당 Agent의 RBAC를 기준으로 합니다.

관리자 UI의 `이 권한으로 테스트`는 DEV/TEST에서만 short-lived impersonation으로 동작하고 감사 로그, TEST 배너, 원래 관리자 Session 복귀를 포함합니다.

## 안전장치
- `is_test=true` 또는 동등 필드
- `test_batch_id` Batch 격리
- idempotent Seed
- Batch 단위 reset/delete
- production Seed/Delete/Impersonation 거부
- 테스트 비밀번호 하드코딩 금지
- non-test row 삭제 금지

## 생성 파일 기본 계약
- `backend/app/schemas/test_environment.py`
- `backend/app/services/test_data_service.py`
- `backend/app/routers/admin_test_environment.py`
- `backend/tests/test_test_environment.py`
- React UI가 있으면 `frontend/src/pages/admin/TestEnvironmentPage.tsx|jsx`
- React UI가 있으면 `frontend/src/services/testEnvironmentApi.ts|js`
