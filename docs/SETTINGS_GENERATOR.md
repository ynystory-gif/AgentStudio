# v5.126 Agent Settings Generator

AgentStudio가 생성하는 Agent마다 필요한 설정 화면/API를 자동 설계·생성합니다.

## Agent Factory Workflow

```text
Project File Plan
  ↓
Settings Requirement Analysis
  ↓
Settings Schema Design
  ↓
Settings UI Design
  ↓
Checkpoint / Approval
  ↓
Code Generation
  ↓
Settings Generator
  ↓
Settings Validation
  ↓
Environment Configuration
  ↓
Test
```

## 판단 원칙

- AgentStudio 설정 전체를 복사하지 않습니다.
- 생성 대상 Agent에 실제 필요한 설정만 만듭니다.
- 현재 사용하지 않는 DB 설정은 만들지 않습니다.
- Secret은 별도 보안 규칙을 적용합니다.

## 생성 대상

필요 시:
- `app/core/settings.py`
- `app/schemas/settings.py`
- `app/services/settings_service.py`
- `app/routers/settings.py`
- `frontend/src/pages/SettingsPage.jsx`
- `frontend/src/services/settingsApi.js`
- `.env.example`

## Secret

- GET에서 원문 반환 금지
- has_value / masked 상태 반환
- Frontend 하드코딩 금지
- `.env.example` 실제 Secret 금지

## Validation

- 계획된 Settings 파일 존재 여부
- `.env.example` Secret Scan
- 전체 Agent test workflow와 Coding Style Validator 재검증
