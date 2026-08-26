# v5.353 Large Architecture Visual PPT Export

## 목표
PPT 아키텍처를 작은 이모지/보조 아이콘이 아니라, 첨부 예시처럼 카드와 레이어의 중심을 차지하는 큰 대표 그래픽으로 표현합니다.

## 변경 사항
- 26종 Generic Architecture Large Visual Asset Pack을 로컬 번들로 추가했습니다.
- User, Desktop/Web, Mobile, Internet, API, Security, Agent, Workflow, LLM, MCP, Tool, Database, Redis/Cache, Vector DB, Storage, Cloud, Server, Kubernetes, Network, Report, Terminal, Code, 상태 아이콘을 제공합니다.
- Vendor 공식 로고 대신 기능을 직관적으로 표현하는 Generic Architecture Illustration을 기본으로 사용합니다.
- 프로젝트 구성 요소 이름/설명에서 기술 의미를 분석해 대표 그래픽을 자동 매핑합니다.
- 매핑되지 않는 구성 요소는 Generic Component Visual로 안전하게 대체합니다.
- 아이콘 파일 누락/손상 시 PPT Export 전체가 실패하지 않고 네이티브 PowerPoint fallback 카드로 계속 생성됩니다.
- 큰 그래픽은 PowerPoint의 개별 Picture Object로 삽입되어 이동/크기조정/삭제가 가능합니다.
- 박스, 텍스트, 연결선은 기존처럼 PowerPoint Native Shape/Text로 유지합니다.

## Architecture PPT
### Design Architecture
Client/Interface → Agent/Service → Data/Platform의 3개 레이어에 큰 대표 그래픽을 배치합니다.

### Platform Architecture
User/Desktop/Mobile/Internet → Frontend/Interface → FastAPI/Security/API → Agent/Workflow/LLM/MCP/Tool을 큰 그래픽 중심으로 구성합니다.

### Foundation & Infrastructure
가독성을 위해 별도 슬라이드로 분리하여 LLM, Execution, Persistence, Project State와 Cloud, Server, Kubernetes, Storage, Network를 큰 그래픽으로 표현합니다.

## 기타 탭
Workflow, 실행 결과, 분석 리포트에도 각 슬라이드 성격을 나타내는 큰 대표 Visual을 Header 영역에 추가했습니다.

## 호환성
- PowerPoint 16:9 Widescreen
- python-pptx 기반
- 인터넷 연결 없이 동작
- Runtime 추가 이미지 라이브러리 불필요
