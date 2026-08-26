# v5.349 Notebook Top-Level Await Support

## 문제

AgentStudio Notebook은 Persistent Python Worker로 Code 셀을 실행하지만 기존 Worker가 셀 소스를 일반 `compile(..., mode="exec")`로 컴파일했습니다. 따라서 Jupyter에서는 정상인 아래 코드가 AgentStudio에서만 실패했습니다.

```python
async def get_summary_async(text: str) -> str:
    result = await llm.ainvoke(f"요약: {text}")
    return result.content

result = await get_summary_async("오늘 회의에서 나온 이야기입니다.")
print(result)
```

오류: `SyntaxError: 'await' outside function`

## 수정

- Notebook 실행에만 `ast.PyCF_ALLOW_TOP_LEVEL_AWAIT` compile flag를 적용합니다.
- compile 결과가 awaitable이면 Worker 내부의 Persistent asyncio event loop에서 완료될 때까지 실행합니다.
- 마지막 표현식 캡처 경로도 동일한 top-level await 규칙을 사용합니다.
- 일반 `.py` Editor 실행에는 flag를 적용하지 않아 Python 스크립트 문법을 그대로 유지합니다.
- 기존 Notebook Persistent namespace, `%pip`, `!command`, `%%writefile`, traceback cell pseudo filename 동작을 유지합니다.

## 회귀 검증

`backend/validate_v5349_notebook_top_level_await_contract.py`에서 다음을 검증합니다.

1. Notebook 셀 최상위 await 성공
2. await 반환값의 마지막 표현식 캡처 성공
3. 셀 간 persistent namespace 유지
4. 일반 `.py` 모드의 최상위 await는 계속 SyntaxError
