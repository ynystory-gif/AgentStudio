# v5.215 Project Coding Factory Plan Fix

- `/ai/project-edit`가 Prompt에서 `factory_plan`과 `factory_policies`를 참조하면서 변수를 정의하지 않아 발생하던 `NameError`를 수정했습니다.
- 프로젝트 코딩 요청별로 `infer_fastapi_factory_plan()`을 실행해 설계 적용 계획을 구성합니다.
- FastAPI 후보 요청에만 Factory 세부 정책을 Prompt에 포함하고, NestJS/TypeScript 등 비-FastAPI 요청에는 불필요한 FastAPI 정책을 주입하지 않습니다.
- Factory plan은 JSON 문자열로 직렬화해 Prompt에 안정적으로 포함합니다.
