# v5.170 Patch Apply Resilience Fix

## 문제
Code/Patch Generation이 만든 `replacements.old` 문자열이 현재 파일의 공백·줄바꿈 또는 이전 실행 변경 때문에 정확히 일치하지 않으면 전체 Workflow가 `FILE_APPLY_FAILED`로 즉시 종료되었습니다.

## 수정
- Exact match 이후 newline-normalized / unique whitespace-flexible match를 안전하게 시도합니다.
- 이미 `new`가 반영된 Patch는 idempotent no-op으로 처리합니다.
- 의미가 다른 코드를 추측해서 교체하지 않습니다.
- 그래도 old를 찾지 못하면 실패 파일 하나만 현재 내용으로 다시 읽어 `Focused Patch Recovery`를 수행합니다.
- Focused Recovery는 `replace_entire_file=true` 전체 파일 교체를 사용하며 다른 파일 수정은 거부합니다.
- 이미 성공한 앞쪽 Patch는 다시 실행하지 않고 실패 지점 이후만 계속합니다.
- 최대 2개의 stale Patch 대상까지 focused recovery를 허용합니다.
- 진단 자료에 failed target/change/replacement와 recovery 이력을 기록합니다.

Health: `5.170 / PatchApplyResilienceFix`
