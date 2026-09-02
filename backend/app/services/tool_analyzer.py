from dataclasses import dataclass

@dataclass
class ToolAnalysis:
    category: str
    subcategory: str
    capability: str
    risk_level: int
    requires_confirmation: bool

RULES = [
    (("read", "get", "list", "status", "find", "search"), "FILE", "READ", "read", 0),
    (("write", "save", "create_file"), "FILE", "WRITE", "file_write", 1),
    (("delete", "remove"), "FILE", "DELETE", "file_delete", 4),
    (("exec", "command", "shell", "terminal"), "TERMINAL", "EXECUTE", "command_execute", 2),
    (("kill", "stop_process", "restart_process"), "PROCESS", "CONTROL", "process_control", 3),
    (("git", "commit", "branch", "diff", "push", "pull"), "GIT", "SOURCE_CONTROL", "git", 2),
    (("query", "database", "sql"), "DATABASE", "QUERY", "database_query", 2),
    (("browser", "http", "web", "url"), "WEB", "NAVIGATE", "web_access", 1),
    (("upload", "send", "publish"), "EXTERNAL", "WRITE", "external_write", 3),
    (("mcp", "tool"), "MCP", "TOOL", "mcp_tool", 1),
]

def analyze_tool(name: str, description: str = "") -> ToolAnalysis:
    text = f"{name} {description}".lower()

    # v5.437: Blender MCP is a first-class 3D Tool category.  Do this before the
    # generic FILE/WEB/MCP rules because names such as render_scene/add_mesh do
    # not necessarily contain the literal word "mcp". Script/Python execution
    # remains high-risk even when it belongs to the Blender server.
    blender_strong_signals = (
        "blender", "mesh", "viewport", "render_scene", "geometry node",
        "add cube", "add object", "scene object", "keyframe", "timeline",
        "bpy.", "blend file", "gltf", "glb export", "fbx export",
    )
    if any(token in text for token in blender_strong_signals):
        destructive = any(token in text for token in ("delete", "remove", "purge"))
        script_exec = any(token in text for token in ("python", "script", "exec", "execute code"))
        risk = 4 if script_exec else 3 if destructive else 1
        subcategory = "SCRIPT_EXECUTION" if script_exec else "SCENE_MUTATION" if destructive else "SCENE_TOOL"
        capability = "blender_script_execute" if script_exec else "blender_scene_control"
        return ToolAnalysis("3D", subcategory, capability, risk, risk >= 3)

    for keywords, category, subcategory, capability, risk in RULES:
        if any(k in text for k in keywords):
            return ToolAnalysis(category, subcategory, capability, risk, risk >= 3)
    return ToolAnalysis("UNKNOWN", "UNKNOWN", "unknown", 1, False)


async def analyze_tool_with_llm(name: str, description: str = "") -> dict:
    """기본 규칙 분석 + Ollama 의미 분석. 비용이 들지 않는 로컬 모델 전용."""
    from langchain_core.messages import SystemMessage, HumanMessage
    from app.services.model_router import model_for_task, LLMTask
    base = analyze_tool(name, description)
    llm = model_for_task(LLMTask.TOOL_CLASSIFICATION)
    result = await llm.ainvoke([
        SystemMessage(content=(
            "MCP Tool을 분류하십시오. category, capability, 위험요인을 짧게 설명하십시오. "
            "실제 실행은 하지 마십시오."
        )),
        HumanMessage(content=f"Tool: {name}\nDescription: {description}")
    ])
    return {**base.__dict__, "ollama_analysis": str(result.content)}
