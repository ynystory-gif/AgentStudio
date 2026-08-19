# v5.158 Requirement Coverage Gate 수정

## 발생 원인
Requirement Coverage Gate가 `backend/app/mcp/transport.py`의 purpose 문자열에
`stdio`라는 단어가 직접 포함되어 있는지 검사했습니다.

실제 상태:
- confirmed requirements: stdio
- target workflow: 로컬 stdio 기본
- transport 파일 계획: 존재
- purpose: `MCP Transport 구현`

따라서 구현 구조는 존재했지만 설명 문구에 특정 단어가 없다는 이유만으로
`REQUIREMENT_COVERAGE_FAILED`가 발생했습니다.

## 변경
1. Coverage Gate를 Structure-first 방식으로 변경
2. File Plan purpose의 특정 단어 존재 여부로 실패시키지 않음
3. confirmed requirements를 source of truth로 사용
4. stdio 요구는 File Plan에 자동 보강
5. 실제 생성 코드가 Flask/HTTP인지 여부는 Build Artifact Architecture Gate에서 검증
6. 실패 리포트에 정확한 missing contract를 표시

## 정상 기대 흐름
Requirement Coverage
→ 구조 파일 존재 확인
→ File Plan 자동 보강
→ Code Plan
→ File Apply
→ Architecture Validation
→ Test
