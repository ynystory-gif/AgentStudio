# v5.169 Placeholder Semantic Repair Fix

## 문제
- v5.168은 소스의 `placeholder` 문자열을 무조건 미구현으로 판정했습니다.
- React의 `placeholder="파일 경로"` 정상 속성까지 실패로 오인했습니다.
- 실제 미구현 `# Placeholder for actual chunking logic`은 파일 경로만 Repair Prompt에 전달되어 정확한 줄을 고치지 못할 수 있었습니다.

## 수정
- JSX/HTML `placeholder=` 속성은 미구현 판정에서 제외합니다.
- TODO/FIXME/NotImplementedError/구현 대기 주석/Python 빈 함수 등 의미 있는 stub만 검출합니다.
- Placeholder 파일과 line/reason/snippet을 진단/Repair Prompt에 전달합니다.
- Repair LLM Context는 실패 대상 파일만 사용하고, Repair Plan도 실패 대상 파일로 제한합니다.
- 동일 실패 시 한 번의 focused retry를 더 허용하며 두 번째 Repair는 관련 함수/컴포넌트 완전 재작성 지시를 사용합니다.
- 진단 UI와 failure_report.md에 Placeholder 상세 위치를 표시합니다.

Health: `5.169 / PlaceholderSemanticRepairFix`
