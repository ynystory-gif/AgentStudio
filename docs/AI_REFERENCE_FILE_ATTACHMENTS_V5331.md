# v5.331 AI Reference File Attachments

## 목적

Agent 설계 인터뷰, LLM 대화형 코드 편집, 오른쪽 Codex 패널에서 사용자가 필요할 때 참고 파일을 직접 등록하고 AI가 해당 내용을 함께 분석할 수 있도록 합니다.

## 공통 Attachment Registry

- Windows 네이티브 다중 파일 선택창을 사용합니다.
- 사용자가 파일 선택창에서 직접 고른 파일만 Backend Attachment Registry에 등록합니다.
- Frontend는 실제 로컬 경로를 AI API에 직접 읽기 요청하지 않고 opaque `attachment_id`만 전달합니다.
- Registry 항목은 Backend 메모리에 보관되며 12시간 후 자동 만료됩니다.
- 파일 1개 최대 20MB, 화면별 최대 12개를 등록할 수 있습니다.
- 모델 Context에 넣을 때 파일별/전체 문자 예산을 적용해 지나치게 큰 파일은 일부만 전달합니다.
- 첨부 파일은 참고/분석 Context이며, 코드 편집의 직접 수정 대상은 현재 선택 파일 또는 프로젝트 루트 내부 파일로 제한됩니다.

## 지원 파일

- 코드/텍스트/설정: TXT, Markdown, CSV/TSV, JSON/JSONL, YAML, TOML, INI, XML/HTML/CSS, Python, JS/TS, Java, C/C++, C#, Go, Rust, Shell/PowerShell, SQL 등
- Jupyter Notebook: `.ipynb`의 Cell source를 추출하며 output/metadata는 분석 Context에서 제외합니다.
- PDF: `pypdf`로 텍스트를 추출합니다.
- Word: `python-docx`로 문단/표 텍스트를 추출합니다.
- Excel: `openpyxl` read-only 모드로 시트/셀을 추출합니다.
- PowerPoint: `python-pptx`로 슬라이드 텍스트를 추출합니다.
- 이미지, 실행파일 등 텍스트를 추출할 수 없는 바이너리는 경고를 표시하고 AI Context에서 제외합니다.

## Agent 설계 인터뷰

- 인터뷰 입력창 위에 `참고 파일 선택`을 추가했습니다.
- 선택한 파일은 매 인터뷰 요청에서 요구사항 근거 Context로 전달됩니다.
- Workflow 설계로 넘어갈 때도 동일 Attachment Context를 전달하여 설계 단계에서 참고 문서가 사라지지 않습니다.

## LLM 대화형 코드 편집

- 하단 LLM 코드 편집 패널에 `참고 파일 선택`을 추가했습니다.
- 파일 단위 편집에서는 현재 수정 대상 파일 + 등록 참고 파일을 함께 분석합니다.
- Notebook 편집에서도 TARGET Cell Context + 등록 참고 파일을 함께 분석합니다.
- 프로젝트 단위 편집에서는 자동 관련 파일 분석 + 사용자가 명시적으로 등록한 참고 파일을 함께 사용합니다.
- 참고 파일 자체는 프로젝트 밖 파일일 수 있으나 직접 수정 대상으로 사용하지 않습니다.

## Codex

- 오른쪽 Codex Composer에 `참고 파일 선택`을 추가했습니다.
- 선택한 파일은 Backend가 텍스트 Context로 정규화한 뒤 `turn/start`의 사용자 입력에 함께 전달합니다.
- 프로젝트 밖 참고 문서도 Codex sandbox에 직접 경로 권한을 주지 않고 내용만 전달하므로 분석할 수 있습니다.
- 메시지를 쓰지 않고 파일만 등록한 경우에도 전송할 수 있으며 `첨부한 참고 파일의 내용을 분석하고 핵심 내용을 정리해줘.`를 기본 요청으로 사용합니다.

## 보안/안정성

- 임의 API 경로 입력만으로 외부 로컬 파일을 읽는 기능은 제공하지 않습니다.
- 사용자가 네이티브 파일 선택창을 통해 명시적으로 고른 파일만 Registry에 등록됩니다.
- 파일이 등록 후 삭제/이동되거나 크기 제한을 넘으면 AI 호출 전에 경고하고 제외합니다.
- 분석 모듈이 없거나 지원하지 않는 형식은 전체 AI 요청을 실패시키지 않고 해당 첨부만 제외합니다.
