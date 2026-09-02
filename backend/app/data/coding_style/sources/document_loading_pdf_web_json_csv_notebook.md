# 문서 로딩 PDF · 웹 · JSON · CSV Notebook 코딩 스타일 추출

사용자가 제공한 `2. 문서_로딩_1_PDF_웹_JSON_CSV.ipynb`의 실제 코드 작성 방식에서 Agent 개발 코드에 재사용 가치가 있는 패턴만 구조화합니다.

## 반영 패턴
- `PDF_PATH`, `WEB_URL`, `OCR_PDF_PATH`처럼 입력·경로·설정을 핵심 처리와 구분합니다.
- `pdf_docs`, `json_docs`, `csv_docs`, `ocr_target_document`처럼 단계와 역할이 드러나는 이름을 사용합니다.
- 설정/입력 → 로딩 → 처리 → 검증 → 결과 확인 순서를 유지합니다.
- 문서 수·`page_content`·필수 구조를 다음 단계 전에 검증합니다. 운영 Agent에서는 assert만 의존하지 않고 Validator/예외 처리로 승격합니다.
- 외부 HTTP 호출은 `timeout`, `raise_for_status()`와 업무 상태 코드를 함께 확인합니다.
- 선택적 API Key 누락은 명시적 Skip/비활성 경로로 처리합니다.
- `with pdfplumber.open(...)`, `with pymupdf.open(...)`처럼 리소스 수명주기를 안전하게 관리합니다.
- `metadata_func`, `Document(metadata=...)`처럼 source/page/id/date/tags를 유지합니다.
- 대량 입력에는 `lazy_load()`/iterator를 고려합니다.
- UTF-8, 공백, None 등 외부 데이터 경계를 최소 정규화합니다.

## 그대로 복사하지 않는 교육용 패턴
- `print` 중심 확인은 운영 서비스에서는 Logging/Metric/Trace로 바꿀 수 있습니다.
- `warnings.filterwarnings("ignore")`를 운영 Agent 기본 코드에 적용하지 않습니다.
- 실습용 고정 파일명·페이지·예상 건수는 Settings/입력/테스트 Fixture로 분리합니다.
- 작은 예제를 불필요하게 Service/Class로 과도하게 추상화하지 않습니다.
