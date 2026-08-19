from app.services.agent_workflow import build_workflow

def main() -> None:
    graph = build_workflow(checkpointer=None)
    print("[완료되었습니다] Agent Workflow LangGraph compile 성공")
    print(f"Compiled graph type: {type(graph).__name__}")

if __name__ == "__main__":
    main()
