# v5.193 Editor False-Positive Diagnostics Fix

- Monaco standalone TypeScript/JavaScript worker의 semantic diagnostics를 비활성화했습니다.
- 실제 프로젝트의 node_modules, tsconfig, NestJS/Jest type graph를 완전히 로드하지 못해 정상 코드에 표시되던 false-positive 빨간 밑줄을 제거합니다.
- Syntax diagnostics는 유지하므로 괄호, 문자열, 잘못된 문법 같은 실제 구문 오류는 계속 에디터에서 표시됩니다.
- 실제 TypeScript 타입/모듈 검증은 프로젝트의 `tsc`, `npm run build`, `npm test` 결과를 기준으로 합니다.
