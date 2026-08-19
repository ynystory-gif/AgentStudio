# v5.136 LangGraph Compile Fix

## 오류

Backend 시작 시 다음 오류가 발생했습니다.

`ValueError: Found edge starting at unknown node 'build_artifact_validation'`

## 원인

v5.135에서 다음 Edge는 추가되었지만:

`settings_validation -> build_artifact_validation -> environment_configuration`

`build_workflow()`의 `graph.add_node()` 등록이 누락되었습니다.

## 수정

다음 Node 등록을 추가했습니다.

```python
graph.add_node(
    "build_artifact_validation",
    build_artifact_validation_node,
)
```

또한 `backend/validate_agent_workflow.py`를 추가했습니다.

실행:

```powershell
cd backend
python .\validate_agent_workflow.py
```

정상 결과:

```text
[완료되었습니다] Agent Workflow LangGraph compile 성공
```

앞으로는 Python 문법 검사뿐 아니라 LangGraph Graph compile 검증도 별도로 수행할 수 있습니다.
