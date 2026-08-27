# v5.376 GPU Acceleration Recommendation Control

## 목적

AgentStudio는 GPU를 필수 실행 조건으로 만들지 않습니다. 다만 다음 작업은 GPU 가속 사용을 권장합니다.

- AI 모드를 `Ollama`로 고정하여 로컬 LLM만 사용하는 설계/개발
- 로컬 Embedding 모델을 사용하는 Vector/RAG/pgvector 작업
- 이미지/영상 AI Agent 생성·분석·테스트

GPU 가속이 정지된 상태에서 위 작업을 시작하면 권장 확인창을 표시합니다. 사용자가 **확인**을 누르면 GPU 가속을 시작한 뒤 원래 작업을 계속합니다.

## 설정 화면

`설정 > GPU 가속`에서 다음 버튼을 제공합니다.

- **GPU 시작**: AgentStudio 관리 작업에서 GPU 가속 사용
- **GPU 정지**: GPU 가속을 사용하지 않고 가능한 작업을 CPU 모드로 실행
- **상태 새로고침**: NVIDIA GPU/VRAM/사용률 상태 확인

GPU 시작/정지는 물리 GPU의 전원을 제어하지 않습니다.

## Ollama

AgentStudio가 직접 시작한 Ollama 서버는 GPU 모드 변경 시 안전하게 재시작합니다.
사용자가 별도로 실행한 외부 Ollama 프로세스는 강제 종료하지 않습니다.

## 생성 Agent 테스트

Agent Factory의 테스트 명령에는 GPU 모드가 환경변수로 전달됩니다.
GPU 정지 상태에서는 CUDA/ROCm 장치를 숨겨 CPU 모드 실행을 유도합니다.
