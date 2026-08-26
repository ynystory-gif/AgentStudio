# v5.350 Valid Notebook Create Fix

## 문제

프로젝트 파일 영역의 `새 파일` 기능은 모든 확장자를 동일하게 0 byte 파일로 생성했습니다.
일반 텍스트 파일에는 문제가 없지만 `.ipynb`는 JSON 문서이므로 빈 파일은 유효한 Jupyter Notebook이 아닙니다.
그 결과 생성 직후 Notebook Editor가 `Unexpected end of JSON input`을 표시했습니다.

## 수정

- Backend `create_file()`가 `.ipynb` 확장자를 감지합니다.
- 신규 Notebook에는 nbformat 4 / minor 4 구조와 빈 Python code cell 1개를 기록합니다.
- 작성 직후 Notebook payload를 다시 검증한 뒤에만 생성 성공을 반환합니다.
- 구버전에서 남은 0 byte Notebook은 동일 생성 요청 시 자동 복구합니다.
- 이미 내용이 있는 Notebook은 절대 덮어쓰지 않습니다.
- 생성 결과에는 size / mtime / sha256을 반환합니다.

## 기본 생성 형식

```json
{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
```

## 검증

`backend/validate_v5350_valid_notebook_create_contract.py`에서 신규 Notebook 생성, JSON 구조, 빈 Code Cell, SHA-256, 일반 파일 0 byte 유지, 구버전 0 byte Notebook 복구, 비어 있지 않은 기존 Notebook 미덮어쓰기를 검증합니다.
