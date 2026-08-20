# v5.275 Firestore / Supabase Database Provider Support

## 목적

AgentStudio DB 연결에 Google Cloud Firestore와 Supabase를 추가합니다.

## Google Cloud Firestore

- DB 종류: `Google Cloud Firestore`
- 분류: NoSQL Document Database
- 설정: Project ID, Database ID, Service Account JSON 경로
- Service Account JSON 경로를 비우면 `GOOGLE_APPLICATION_CREDENTIALS` / Application Default Credentials를 사용합니다.
- 인증 JSON 파일 내용은 AgentStudio 연결 프로필에 저장하지 않고 경로만 저장합니다.
- 연결 테스트는 Firestore API에 인증된 요청을 보내는 방식으로 수행합니다.
- Firestore는 SQL 대상이 아니므로 SQL 실행은 명확한 오류로 차단합니다.
- Google Cloud Firestore 관리 콘솔 버튼을 제공합니다.

## Supabase

- DB 종류: `Supabase (PostgreSQL)`
- 실제 드라이버: `psycopg`
- 기본 SSL Mode: `require`
- Host / Port / Database / User / Password 방식과 Supabase Dashboard에서 복사한 Connection URL 입력을 지원합니다.
- Connection URL은 UI에서 Host/Port/Database/User/Password로 분해하고 원본 URL 자체는 저장하지 않습니다.
- 비밀번호는 기존 AgentStudio 정책대로 Windows DPAPI 현재 사용자 범위로 보호하여 저장합니다.
- `https://supabase.com/dashboard` 바로가기 버튼을 제공합니다.
- PostgreSQL 호환 SQL Workspace / Object Explorer를 그대로 사용합니다.

## UI

DB 연결 탭은 `.sql` 파일에서만 나타나던 제한을 제거하여 일반 프로젝트 파일을 편집할 때도 열 수 있습니다. Firestore 같은 NoSQL 연결도 SQL 파일 없이 설정할 수 있습니다.

## 의존성

Backend에 `google-cloud-firestore>=2.21`을 추가했습니다.

## 보안

루트 `.gitignore`에 일반적인 Google Service Account JSON 파일명을 추가하여 자격증명 파일이 Git에 실수로 포함될 위험을 줄였습니다.
