# AgentStudio v2 Architecture

## Main Flow
Requirement Interview → LangGraph Workflow → Plan → Git Checkpoint → Approval → Patch → Test → Review

## LangGraph
- StateGraph
- PostgreSQL Checkpointer
- interrupt()/resume for Human Approval
- thread_id based durable state

## MCP
- Streamable HTTP discovery
- initialize
- tools/list
- Tool Analyzer
- Category / Capability / Risk

## Memory
- SESSION
- PROJECT
- KNOWLEDGE

## Safety
- Allowed project roots
- Risk based approval
- Git checkpoint
- Sandbox module
- destructive actions should require explicit approval

## Async UX
- REST for short calls
- WebSocket for Jobs
- subprocess runs asynchronously
