# v5.191 Editor Language Detection Fix

- Monaco Editor가 `defaultLanguage=python`에 고정되어 `.ts`, `.tsx` 등 다른 언어 파일을 열어도 올바른 문법 강조가 적용되지 않던 문제를 수정했습니다.
- 열린 파일의 경로/확장자를 기준으로 Monaco `language`와 model `path`를 자동 설정합니다.
- TypeScript: `.ts`, `.tsx`, `.mts`, `.cts` → `typescript`
- JavaScript: `.js`, `.jsx`, `.mjs`, `.cjs` → `javascript`
- Python/JSON/Markdown/HTML/CSS/SQL/YAML/XML/Shell/PowerShell/BAT/C#/Java/C/C++/Go/Rust/PHP/Ruby 등 주요 확장자도 자동 판정합니다.
- 프로젝트+파일 경로별 Monaco model을 사용하여 서로 다른 파일의 언어 상태가 섞이지 않도록 했습니다.
- TypeScript/JavaScript language service의 syntax/semantic diagnostics와 suggestion 기능을 활성화했습니다.
- bracket pair colorization과 편집 지원 옵션을 활성화했습니다.
