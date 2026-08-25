# v5.341 As-Built Architecture Conformance Gate

Agent Factory가 설계 아키텍처만 저장하고 완료하던 흐름을 보강합니다.

## 제작 흐름

1. Requirement / Capability / Tool-MCP 분석
2. Design Architecture 확정
3. DB / Target Workflow / File Plan 확정
4. Code Generation + Settings + Build Artifact Validation
5. **As-Built Architecture Analyzer**
   - 실제 프로젝트 파일을 정적 스캔
   - 파일, 클래스, 함수, FastAPI/React/LangGraph/MCP/DB/Realtime 증거 수집
   - 고성능 Provider(Codex → OpenAI → Ollama)가 증거 기반 의미 분류를 보강
6. **Architecture Conformance Gate**
   - Design component ↔ component_file_map ↔ 실제 파일 비교
   - required file, interface, persistence, state, security 비교
   - 85점 이상이며 Critical mismatch가 없어야 PASS
7. FAIL이면 **Architecture Repair**를 최대 2회 수행한 뒤 다시 정적 분석/비교
8. PASS 이후에만 환경 구성 → 테스트 → 패키지 → 최종 Review 진행

## 완료 규칙

- 계획된 필수 파일 존재
- Placeholder / Coding Style 검증 PASS
- Design ↔ As-Built Conformance PASS
- 테스트 PASS
- SYSTEM_ADMIN 실행 계약 PASS

Critical mismatch가 자동 보정 2회 후에도 남으면 완료 처리하지 않습니다.
