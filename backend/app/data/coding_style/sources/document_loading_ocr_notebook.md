# Source Note — 2-2. 문서_로딩_OCR.ipynb

## Source scope

- 실제 Notebook: `2-2. 문서_로딩_OCR.ipynb`
- 분석 셀: 44개 (Code 22 / Markdown 22)
- 목적: 교육용 OCR/문서 로딩 예제의 좋은 실행 패턴을 AgentStudio의 **생성 Agent 운영 코드 스타일**로 일반화한다.
- 원문 Notebook 전체를 Prompt에 복사하지 않고 재사용 가능한 규칙만 Registry로 승격한다.

## Agent 생성 규칙으로 채택한 패턴

1. **Preflight before mutation**
   - `platform.system()`으로 macOS CUDA 불가 조건을 먼저 확인한다.
   - `shutil.which("nvidia-smi")`로 NVIDIA Runtime 준비 여부를 환경 변경 전에 확인한다.
   - `installed_version()`으로 CPU/GPU Paddle 패키지 상태를 확인한다.
   - 조건이 맞지 않으면 기존 환경을 변경하지 않았음을 알리고 중단한다.

2. **Non-destructive environment conflict handling**
   - CPU `paddlepaddle`과 GPU `paddlepaddle-gpu` 충돌 시 기존 Paddle을 자동 삭제하지 않고 별도 GPU 가상환경 사용을 안내한다.
   - AgentStudio 생성 Agent에서는 이 원칙을 일반화하여 패키지/설정/사용자 파일의 무단 삭제·덮어쓰기를 금지한다.

3. **Quality-gated fallback**
   - `load_pdf_with_ocr()`는 먼저 `PyPDFLoader` 결과의 페이지별 글자 수와 평균 글자 수를 계산한다.
   - `average_characters >= minimum_chars_per_page`이면 Text Layer 결과를 사용한다.
   - 품질이 부족할 때만 PDF 페이지를 렌더링해 EasyOCR로 전환한다.
   - Text/OCR 어느 경로든 최종적으로 `Document` 목록을 반환한다.

4. **Resource cleanup**
   - OCR fallback에서 `pymupdf.open()`으로 연 PDF는 `try/finally`에서 `close()`한다.
   - 기존 CS-157 리소스 수명주기 규칙과 결합해 운영 Agent에 적용한다.

5. **Metadata preservation**
   - OCR `Document`에 `source`, `page`, `page_number`, `loader`를 보존한다.
   - 개별 OCR 이미지 예제에는 `image_path`도 추적한다.

6. **Post-condition validation**
   - 최종 mission에서 반환 키, mode, Document 수, source metadata를 `assert`로 확인한다.
   - 운영 Agent에서는 assert만 의존하지 않고 Pydantic/Validator/명시적 예외로 승격한다.

7. **Controlled benchmark**
   - `PADDLE_COMMON_OPTIONS`를 CPU/GPU 양쪽에 동일 적용한다.
   - 동일 OCR 이미지로 비교한다.
   - 초기화 시간, 첫 추론(Cold), 워밍업 추론(Warm)을 구분해 측정한다.

## 그대로 채택하지 않는 교육/환경 특수 패턴

- `warnings.filterwarnings("ignore")`
  - 운영 Agent 전역 경고 숨김으로 채택하지 않는다. 기존 CS-162 유지.
- Notebook Runtime의 `%pip install`
  - 생성 Agent 운영 코드에서 요청 처리 중 자동 패키지 설치하는 기본 패턴으로 사용하지 않는다.
- OpenCV 배포판을 `uv pip uninstall` 후 재설치하는 Notebook 특수 정리
  - 특정 실습환경 복구 로직으로 보고 일반 Agent가 기존 사용자 환경을 자동 변경하는 규칙으로 승격하지 않는다.
  - 필요하면 격리 venv/컨테이너 또는 사용자 승인 절차를 사용한다.
- `urlretrieve()`로 모델 파일을 URL에서 바로 저장
  - 운영 Agent에서는 Version/Revision 고정, 다운로드 상태, 파일 검증, 가능하면 Checksum을 추가한다.
- `Path("result")`, 현재 작업 폴더의 모델/이미지 경로
  - 생성 Agent에서는 Settings 기반 Cache/Temp/Output 경로 정책을 우선한다.
- `return {"documents": ..., "mode": ...}`
  - 교육 예제로는 간단하지만 운영 Agent의 핵심 Service는 Pydantic/dataclass/TypedDict 등 Typed Result Contract를 우선한다.
- `print(...)`
  - Notebook 교육 출력은 유지할 수 있지만 Production Agent에서는 구조화 Logging/상태 이벤트를 우선한다.

## Registry mapping

- CS-163 실행 전 Preflight 검증
- CS-164 기존 환경 비파괴 변경
- CS-165 품질 기준 기반 Fallback
- CS-166 핵심 결과 Typed Contract
- CS-167 외부 Artifact 다운로드 검증
- CS-168 비교 Benchmark 조건 통제
- CS-169 조치 가능한 오류 메시지
