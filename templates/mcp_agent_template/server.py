from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Generated Agent MCP")

@mcp.tool()
def hello(name: str) -> str:
    """사용자에게 인사합니다."""
    return f"안녕하세요, {name}님."

if __name__ == "__main__":
    mcp.run()
