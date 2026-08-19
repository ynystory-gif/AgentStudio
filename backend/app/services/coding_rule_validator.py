from __future__ import annotations

import ast
import re

from app.services.coding_rule_selector import coding_rules_for_request


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*=\s*[\"'][^\"']+[\"']"),
    re.compile(r"ANTHROPIC_API_KEY\s*=\s*[\"'][^\"']+[\"']"),
]



def _validate_python_async_patterns(
    content: str,
    path: str,
) -> list[dict]:
    if not path.lower().endswith(".py"):
        return []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    violations = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.async_depth = 0

        def visit_AsyncFunctionDef(self, node):
            self.async_depth += 1
            self.generic_visit(node)
            self.async_depth -= 1

        def visit_Call(self, node):
            if self.async_depth > 0:
                func = node.func

                # llm.invoke(), chain.invoke() 등
                if isinstance(func, ast.Attribute):
                    if func.attr in {"invoke", "batch", "stream"}:
                        violations.append({
                            "rule_id": "CS-067",
                            "severity": "error",
                            "message": (
                                f"async def 내부에서 동기 .{func.attr}() 호출이 발견되었습니다. "
                                f"비동기 대응 메서드 사용 여부를 확인하세요. (line {getattr(node, 'lineno', '?')})"
                            ),
                        })

                    if (
                        isinstance(func.value, ast.Name)
                        and func.value.id == "time"
                        and func.attr == "sleep"
                    ):
                        violations.append({
                            "rule_id": "CS-068",
                            "severity": "error",
                            "message": (
                                "async def 내부에서 time.sleep() 사용이 발견되었습니다. "
                                f"await asyncio.sleep()으로 변경하세요. (line {getattr(node, 'lineno', '?')})"
                            ),
                        })

                    if (
                        isinstance(func.value, ast.Name)
                        and func.value.id == "asyncio"
                        and func.attr == "run"
                    ):
                        violations.append({
                            "rule_id": "CS-078",
                            "severity": "error",
                            "message": (
                                "async def 내부에서 asyncio.run() 중첩 호출이 발견되었습니다. "
                                f"await를 사용하세요. (line {getattr(node, 'lineno', '?')})"
                            ),
                        })

            self.generic_visit(node)

    Visitor().visit(tree)
    return violations



def _validate_fastapi_structure(
    content: str,
    path: str,
) -> list[dict]:
    normalized = path.replace("\\", "/").casefold()
    violations = []

    if normalized.endswith("/app/main.py") or normalized.endswith("app/main.py"):
        suspicious = [
            "ChatOpenAI(",
            ".ainvoke(",
            ".invoke(",
            "ChatPromptTemplate",
            "@tool",
        ]

        if any(token in content for token in suspicious):
            violations.append({
                "rule_id": "CS-082",
                "severity": "warning",
                "message": "app/main.py에 LLM/프롬프트/Tool 로직이 포함되어 있습니다. main.py는 앱 초기화와 라우터 등록 중심으로 유지하세요.",
            })

    if "/routers/" in normalized:
        suspicious = [
            "ChatOpenAI(",
            "ChatPromptTemplate",
            ".ainvoke(",
            ".invoke(",
        ]

        if any(token in content for token in suspicious):
            violations.append({
                "rule_id": "CS-083",
                "severity": "warning",
                "message": "routers 계층에 LLM 비즈니스 로직이 포함되어 있습니다. services 계층으로 이동하는 것을 권장합니다.",
            })

    if "/services/" in normalized:
        if "from app.routers" in content or "from app.main" in content:
            violations.append({
                "rule_id": "CS-086",
                "severity": "error",
                "message": "services 계층이 routers/main을 역방향으로 import하고 있습니다.",
            })

    if "allow_origins=[\"*\"]" in content or "allow_origins=['*']" in content:
        violations.append({
            "rule_id": "CS-099",
            "severity": "warning",
            "message": "CORS allow_origins=['*']가 발견되었습니다. 운영 환경에서는 실제 허용 Origin만 지정하세요.",
        })

    if "--reload" in content and ("production" in normalized or "prod" in normalized):
        violations.append({
            "rule_id": "CS-110",
            "severity": "warning",
            "message": "운영 관련 파일에 uvicorn --reload가 포함되어 있습니다.",
        })

    return violations



def _validate_fastapi_dependency_security(
    content: str,
    path: str,
) -> list[dict]:
    normalized = path.replace("\\", "/").casefold()
    violations = []

    if "/routers/" in normalized:
        if "ChatOpenAI(" in content:
            violations.append({
                "rule_id": "CS-119",
                "severity": "warning",
                "message": "Router 내부에서 ChatOpenAI()를 직접 생성하고 있습니다. Depends 기반 dependency factory 분리를 검토하세요.",
            })

    if "exception_handler" in content:
        dangerous_patterns = [
            'content={"detail": str(exc)}',
            "content={'detail': str(exc)}",
            '"detail": str(exc)',
            "'detail': str(exc)",
        ]
        if any(pattern in content for pattern in dangerous_patterns):
            violations.append({
                "rule_id": "CS-124",
                "severity": "error",
                "message": "예외 원문 str(exc)를 클라이언트 응답에 직접 노출하고 있습니다.",
            })

    if "@lru_cache" in content:
        request_tokens = [
            "x_user_id",
            "Header(",
            "Request",
            "user_context",
            "session_id",
        ]
        if any(token in content for token in request_tokens):
            violations.append({
                "rule_id": "CS-120",
                "severity": "warning",
                "message": "요청/사용자별 상태가 포함된 dependency에 lru_cache 사용 가능성이 있습니다. lifecycle을 확인하세요.",
            })

    return violations



def _validate_streaming_patterns(
    content: str,
    path: str,
) -> list[dict]:
    normalized = path.replace("\\", "/").casefold()
    violations = []

    # FastAPI async streaming code에서 sync stream 사용
    if "async def " in content:
        if ".stream(" in content and ".astream(" not in content:
            violations.append({
                "rule_id": "CS-131",
                "severity": "error",
                "message": "async streaming 코드에서 동기 .stream() 사용 가능성이 있습니다. async for + .astream()을 사용하세요.",
            })

    # Streaming error에 exception 원문 노출
    dangerous = [
        'sse_event(str(e), event="error")',
        "sse_event(str(e), event='error')",
        'sse_event(str(exc), event="error")',
        "sse_event(str(exc), event='error')",
    ]
    if any(pattern in content for pattern in dangerous):
        violations.append({
            "rule_id": "CS-136",
            "severity": "error",
            "message": "SSE error event에 exception 원문을 직접 노출하고 있습니다.",
        })

    # StreamingResponse가 있는데 text/event-stream 누락
    if "StreamingResponse(" in content and "text/event-stream" not in content:
        violations.append({
            "rule_id": "CS-133",
            "severity": "warning",
            "message": "StreamingResponse 사용 시 SSE endpoint라면 media_type='text/event-stream' 계약을 확인하세요.",
        })

    # done event 힌트
    if (
        "text/event-stream" in content
        and 'event="done"' not in content
        and "event='done'" not in content
        and "event: done" not in content
    ):
        violations.append({
            "rule_id": "CS-134",
            "severity": "warning",
            "message": "SSE endpoint에서 명시적인 done event가 보이지 않습니다.",
        })

    # disconnect handling hint
    if "text/event-stream" in content and "CancelledError" not in content:
        violations.append({
            "rule_id": "CS-137",
            "severity": "warning",
            "message": "프로덕션 Streaming endpoint는 client disconnect/CancelledError 처리 여부를 확인하세요.",
        })

    return violations



def _validate_settings_security(
    content: str,
    path: str,
) -> list[dict]:
    normalized = path.replace("\\", "/").casefold()
    violations = []

    secret_tokens = (
        "api_key",
        "password",
        "token",
        "secret",
    )

    if (
        "/frontend/" in normalized
        or normalized.endswith((".jsx", ".tsx", ".js", ".ts"))
    ):
        patterns = [
            r'(?i)(api[_-]?key|password|token|secret)\s*[:=]\s*["\'][^"\']{8,}["\']',
        ]
        import re as _re
        for pattern in patterns:
            if _re.search(pattern, content):
                violations.append({
                    "rule_id": "CS-149",
                    "severity": "error",
                    "message": "Frontend 코드에 Secret 값이 하드코딩된 가능성이 있습니다.",
                })
                break

    if normalized.endswith(".env.example"):
        for line in content.splitlines():
            value = line.strip()
            if not value or value.startswith("#") or "=" not in value:
                continue
            key, raw = value.split("=", 1)
            if any(token in key.casefold() for token in secret_tokens):
                if raw.strip() not in ("", "your-key-here", "change-me"):
                    violations.append({
                        "rule_id": "CS-153",
                        "severity": "error",
                        "message": ".env.example에 실제 Secret처럼 보이는 값이 있습니다.",
                    })
                    break

    return violations


def validate_code_style(
    code: str,
    request: str = "",
    path: str = "",
    project_scope: bool = False,
) -> dict:
    content = code or ""
    violations = []

    selected = coding_rules_for_request(
        request=request,
        path=path,
        project_scope=project_scope,
    )

    for pattern in SECRET_PATTERNS:
        if pattern.search(content):
            violations.append({
                "rule_id": "CS-004",
                "severity": "error",
                "message": "API Key 또는 비밀값을 소스코드에 직접 작성하면 안 됩니다.",
            })
            break

    if path.lower().endswith(".py"):
        if (
            ("ChatOpenAI(" in content or "ChatAnthropic(" in content)
            and ".invoke(" in content
            and "SystemMessage" not in content
            and "HumanMessage" not in content
        ):
            violations.append({
                "rule_id": "CS-002",
                "severity": "warning",
                "message": "LLM 호출 코드에서 SystemMessage / HumanMessage 역할 분리를 권장합니다.",
            })

    if "ChatPromptTemplate" in content:
        # 흔한 오타/템플릿 오류를 정적 검사합니다.
        if re.search(r"\{\{[A-Za-z_][A-Za-z0-9_]*\}\}", content):
            violations.append({
                "rule_id": "CS-022",
                "severity": "warning",
                "message": "LangChain 템플릿 변수에 이중 중괄호가 발견되었습니다. {variable} 형식을 확인하세요.",
            })

    if "FewShotChatMessagePromptTemplate" in content:
        if '("human", "{input}")' not in content or '("ai", "{output}")' not in content:
            violations.append({
                "rule_id": "CS-018",
                "severity": "warning",
                "message": "Few-shot 예제의 human/ai 입력·출력 형식을 확인하세요.",
            })

    if "with_structured_output(" in content and "StrOutputParser(" in content:
        violations.append({
            "rule_id": "CS-041",
            "severity": "warning",
            "message": "with_structured_output 체인에 StrOutputParser가 함께 사용되었습니다. 출력 타입 계약을 확인하세요.",
        })

    if "class " in content and "BaseModel" in content:
        # Pydantic 모델이 있는데 Field(description=...)가 하나도 없다면 경고
        if "Field(" not in content or "description=" not in content:
            violations.append({
                "rule_id": "CS-037",
                "severity": "warning",
                "message": "Pydantic BaseModel에 Field(description=...) 설명이 충분한지 확인하세요.",
            })

    if "TypedDict" in content and "BaseModel" not in content:
        if any(token in path.casefold() for token in ["api", "schema", "request", "response"]):
            violations.append({
                "rule_id": "CS-036",
                "severity": "warning",
                "message": "API 경계 스키마에서 TypedDict만 사용 중입니다. 런타임 검증이 필요하면 Pydantic BaseModel을 고려하세요.",
            })

    if re.search(r"\beval\s*\(", content):
        violations.append({
            "rule_id": "CS-061",
            "severity": "error",
            "message": "프로덕션 Tool 코드에서 eval() 사용이 발견되었습니다. 안전한 파서/라이브러리로 교체하세요.",
        })

    if "@tool" in content:
        if "Args:" not in content or "Returns:" not in content:
            violations.append({
                "rule_id": "CS-050",
                "severity": "warning",
                "message": "@tool docstring에 Args/Returns 명세가 충분한지 확인하세요.",
            })

    if "ToolMessage(" in content and "tool_call_id=" not in content:
        violations.append({
            "rule_id": "CS-053",
            "severity": "error",
            "message": "ToolMessage에 tool_call_id 연결이 없습니다.",
        })

    if ".tool_calls[0]" in content and "if " not in content:
        violations.append({
            "rule_id": "CS-054",
            "severity": "warning",
            "message": "tool_calls[0] 직접 접근 전에 빈 tool_calls 분기 처리가 필요합니다.",
        })

    violations.extend(
        _validate_python_async_patterns(
            content=content,
            path=path,
        )
    )

    violations.extend(
        _validate_fastapi_structure(
            content=content,
            path=path,
        )
    )

    violations.extend(
        _validate_fastapi_dependency_security(
            content=content,
            path=path,
        )
    )

    violations.extend(
        _validate_streaming_patterns(
            content=content,
            path=path,
        )
    )

    violations.extend(
        _validate_settings_security(
            content=content,
            path=path,
        )
    )

    return {
        "ok": not any(x["severity"] == "error" for x in violations),
        "path": path,
        "selected_rule_ids": [
            rule.get("id")
            for rule in selected.get("rules") or []
        ],
        "violations": violations,
    }
