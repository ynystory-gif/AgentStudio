# THEANOVA AgentStudio
# Git 최신 버전 빠른 업로드 정책 및 불필요 작업 금지 요청서

## 1. 목적

THEANOVA AgentStudio에서 GPT가 수정 완료한 최신 버전을 GitHub에 올릴 때,
불필요한 패치 생성, Base64 변환, Blob 분할 업로드, GitHub Tree 재구성,
Workflow 반복 확인, Hash/SHA-256 반복 검증 등 과도한 후처리를 수행하지 않는다.

이 작업의 목적은 **수정 완료된 현재 작업본을 최대한 빠르고 단순하게 Git에 반영하고,
필요한 경우 현재 로컬 작업본에서 바로 배포 ZIP을 생성하는 것**이다.

---

## 2. 기본 원칙

최신 버전 소스가 이미 수정 완료된 상태라면 추가 분석이나 재생성을 하지 않는다.

기본 Git 업로드 흐름은 아래 단계만 사용한다.

```text
현재 최신 작업본
    ↓
git status
    ↓
git add -A
    ↓
git commit
    ↓
git push
```

다운로드 ZIP이 필요한 경우:

```text
현재 최신 작업본
    ├─ Git Commit / Push
    └─ 현재 로컬 작업본에서 ZIP 생성
```

GitHub에 업로드한 뒤 다시 내려받아 ZIP을 생성하지 않는다.

---

## 3. 금지 작업

최신 버전 Git 업로드 과정에서 아래 작업을 기본적으로 수행하지 않는다.

### 3.1 패치 관련 작업 금지

```text
- 전체 패치 재생성
- v5.xxx 이전 버전과 전체 패치 비교
- Base64 패치 생성
- Base64 패치 내용 검증
- 패치 파일 분할
- 패치 재조립
- 패치 Manifest 생성
- 패치 Manifest 재검증
```

현재 작업본 자체가 최신 완성본이므로 별도 패치 포맷으로 변환하지 않는다.

---

### 3.2 GitHub Blob / Tree 직접 구성 금지

아래와 같은 GitHub Low-Level API 방식은 기본 업로드에서 사용하지 않는다.

```text
- GitHub Blob 개별 생성
- Blob 단위 파일 분할 업로드
- Chunk Blob 생성
- Chunk Blob 읽기
- Chunk 데이터 재계산
- GitHub Tree 직접 생성
- GitHub Tree 재구성
- Tree SHA 직접 계산
- Commit Tree 직접 연결
- API를 이용한 수동 Commit 객체 구성
```

Git 저장소가 정상적으로 준비되어 있다면 일반 Git 명령을 사용한다.

---

### 3.3 불필요한 Hash 검증 금지

일반적인 Git Push 성공 이후 아래 검증을 반복하지 않는다.

```text
- 로컬 파일 SHA-256 전체 계산
- GitHub Blob SHA 전체 비교
- Git Hash와 SHA-256 이중 검증
- 동일 파일 Hash 반복 계산
- Chunk별 Hash 반복 검증
- Push 이후 Blob 재다운로드 후 검증
```

필요한 무결성 확인은 Git 자체의 Commit/Push 결과를 기본 기준으로 한다.

심각한 업로드 오류나 손상 의심 상황에서만 별도 Hash 검증을 수행한다.

---

### 3.4 GitHub Actions 반복 감시 금지

단순 소스 업로드 목적에서는 GitHub Actions를 기다리며 반복 Polling하지 않는다.

기본적으로 아래 작업을 하지 않는다.

```text
- 5초/6초/10초 단위 반복 Polling
- Workflow Run 완료 대기
- Actions 로그 반복 조회
- Workflow Job 상태 반복 조회
- Build 완료까지 무조건 대기
- Actions 성공 후 다시 Git 상태 검증
```

CI/CD 결과 확인이 명시적으로 필요한 경우에만 수행한다.

---

### 3.5 재다운로드 금지

Git Push가 성공한 뒤 아래 작업을 수행하지 않는다.

```text
- git clone 재실행
- git pull 재실행
- GitHub ZIP 재다운로드
- GitHub에서 최신 소스 다시 내려받기
- 내려받은 파일과 로컬 파일 전체 비교
- 내려받은 파일로 배포 ZIP 재생성
```

현재 로컬 작업본이 이미 최신 기준이다.

---

### 3.6 전체 프로젝트 재분석 금지

Git 업로드를 위해 프로젝트 구조를 다시 분석하지 않는다.

```text
- 전체 소스 재분석
- 전체 파일 의미 분석
- 전체 프로젝트 구조 재생성
- 모든 파일 내용 다시 읽기
- 변경되지 않은 파일 재검토
- 전체 코드 영향도 분석
```

코드 수정 작업이 끝난 뒤 Git 저장 요청만 받은 경우에는 Git 저장 작업만 수행한다.

---

## 4. 허용하는 기본 Git 작업

정상적인 Git 저장소에서는 아래 명령 흐름을 기본으로 사용한다.

```bash
git status
git add -A
git commit -m "Update THEANOVA AgentStudio"
git push origin <current-branch>
```

현재 브랜치를 자동 확인하여 해당 브랜치에 Push한다.

예:

```text
현재 브랜치: main

git status
git add -A
git commit -m "Update THEANOVA AgentStudio v5.xxx"
git push origin main
```

---

## 5. 변경 파일만 처리

Git 업로드 시 핵심 기준은 **현재 작업본에서 변경된 파일만 Git에 반영하는 것**이다.

```text
Modified → 반영
Added    → 반영
Deleted  → 반영

Unchanged → 재처리하지 않음
```

변경되지 않은 파일을 다시 생성하거나 다시 저장하지 않는다.

---

## 6. 제외 대상

다음 파일/폴더는 Git 또는 배포 ZIP 대상에서 기본적으로 제외한다.

```text
node_modules/
.venv/
venv/
dist/
build/
.cache/
__pycache__/
.pytest_cache/
coverage/
tmp/
temp/
logs/
*.pyc
*.log
.git/
```

프로젝트 정책에 따라 추가 제외 대상이 존재하면 기존 규칙을 유지한다.

---

## 7. 배포 ZIP 생성 규칙

사용자가 최신 버전 다운로드까지 요청한 경우,
GitHub에서 다시 내려받지 않고 현재 작업본에서 바로 ZIP을 생성한다.

권장 흐름:

```text
GPT 수정 완료 최신 소스
        │
        ├─ Git Commit / Push
        │
        └─ 배포 대상 파일 수집
                 ↓
             ZIP 1회 생성
                 ↓
             다운로드 제공
```

금지 흐름:

```text
현재 소스
   ↓
Git Push
   ↓
GitHub Clone
   ↓
전체 재검증
   ↓
다시 ZIP
```

---

## 8. GitHub API 사용 기준

GitHub API를 완전히 금지하는 것은 아니다.

다만 일반 Git Push가 가능한 상황에서는 API를 우회 경로로 사용하지 않는다.

GitHub API를 사용하는 경우는 아래와 같이 제한한다.

```text
- 일반 Git 명령을 사용할 수 없는 환경
- Git 저장소가 존재하지 않는 환경
- 사용자가 명시적으로 GitHub API 방식을 요청한 경우
- 특정 파일 API 업데이트가 반드시 필요한 경우
```

그 외에는 일반 Git 명령을 우선한다.

---

## 9. 예외 처리

아래 상황이 실제로 발생했을 때만 추가 작업을 수행한다.

### Push 거절

```text
remote rejected
non-fast-forward
branch protection
authentication failure
```

이 경우 원인을 확인하고 필요한 조치만 수행한다.

---

### 충돌 발생

원격 변경사항 때문에 Merge/Rebase가 필요한 경우,
사용자의 로컬 최신 작업을 임의로 덮어쓰지 않는다.

충돌 원인을 먼저 확인한다.

---

### 파일 손상 의심

Push 성공 후 실제 파일 손상이 의심되는 경우에만
선택적으로 Hash 검증 또는 GitHub 파일 확인을 수행한다.

전체 프로젝트를 무조건 재검증하지 않는다.

---

## 10. 진행 상태 표시

Git 업로드 진행 상태는 간단하게 표시한다.

예:

```text
[1/4] Git 변경사항 확인
[2/4] 변경 파일 Stage
[3/4] Commit 완료
[4/4] Push 완료
```

ZIP 다운로드까지 요청된 경우:

```text
[5/5] 배포 ZIP 생성 완료
```

아래와 같은 지나치게 세부적인 내부 작업 로그는 사용자에게 기본 표시하지 않는다.

```text
Blob 생성
Tree 생성
Base64 생성
Chunk 계산
SHA 계산
SHA-256 계산
Workflow Polling
Blob 재검증
```

---

## 11. 완료 기준

아래 조건을 만족하면 Git 업로드 작업 완료로 판단한다.

- [ ] 현재 최신 작업본 기준으로 작업
- [ ] 전체 프로젝트 재분석 없음
- [ ] 불필요한 Patch/Base64 생성 없음
- [ ] Blob/Tree 직접 구성 없음
- [ ] Chunk 분할 업로드 없음
- [ ] Hash/SHA-256 반복 검증 없음
- [ ] GitHub Actions 반복 Polling 없음
- [ ] GitHub 재다운로드 없음
- [ ] 변경 파일만 Stage/Commit
- [ ] 현재 브랜치에 Push 성공
- [ ] ZIP 요청 시 현재 로컬 작업본에서 바로 생성
- [ ] 기존 정상 기능 및 파일 임의 수정 없음

---

## 12. 핵심 지시

Git 업로드 요청은 개발 작업이나 프로젝트 재분석 작업이 아니다.

사용자가 다음과 같이 요청한 경우:

```text
현재 최신 버전 Git에 올리고 다운로드 해줘
```

기본적으로 다음 작업만 수행한다.

```text
현재 최신 작업본
    ↓
Git 상태 확인
    ↓
변경 파일 Stage
    ↓
Commit
    ↓
Push
    ↓
필요 시 현재 작업본 ZIP 생성
    ↓
다운로드 제공
```

다음과 같은 복잡한 파이프라인으로 변경하지 않는다.

```text
전체 비교
→ Patch
→ Base64
→ Chunk
→ Blob
→ GitHub Tree
→ Hash
→ SHA-256
→ Workflow
→ Polling
→ 재다운로드
→ 재검증
→ ZIP
```

**빠른 Git 반영이 목적일 때는 일반 Git Commit/Push를 최우선으로 사용한다.**
