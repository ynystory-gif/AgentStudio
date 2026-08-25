from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_ROUTER = ROOT / "app" / "services" / "model_router.py"
SETTINGS = ROOT / "app" / "services" / "settings_service.py"
CONFIG = ROOT / "app" / "core" / "config.py"
CODEX = ROOT / "app" / "services" / "codex_app_server_service.py"
ROUTES = ROOT / "app" / "api" / "routes.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def source(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def main() -> None:
    router = source(MODEL_ROUTER)
    settings = source(SETTINGS)
    config = source(CONFIG)
    codex = source(CODEX)
    routes = source(ROUTES)

    require('candidates = ["ollama"]' in router, "adaptive route must start with Ollama")
    require('candidates.append("openai")' in router, "adaptive route must support OpenAI fallback")
    require('candidates.append("codex")' in router, "adaptive route must support Codex fallback")
    require('task in CODEX_ELIGIBLE_TASKS' in router, "Codex must be restricted to eligible higher-value tasks")
    require('LLMTask.REQUIREMENTS_ANALYSIS' in router and 'LLMTask.CODE_GENERATION' in router, "requirements/coding tasks must be routable")
    require('run_text_completion' in router, "Codex text-provider adapter must be wired into model routing")

    require('"CODEX_ENABLED"' in settings, "CODEX_ENABLED must be persisted")
    require('"AI_PROVIDER_STRATEGY"' in settings, "AI_PROVIDER_STRATEGY must be persisted")
    require('"CODEX_ENABLED": "false"' in settings, "Codex must be opt-in by default")
    require('"AI_PROVIDER_STRATEGY": "ollama_first"' in settings, "Ollama-first must be default")
    require('ai_provider_strategy: str = "ollama_first"' in config, "config must default to ollama_first")
    require('codex_enabled: bool = False' in config, "config must default Codex to disabled")

    require('"account/rateLimits/read"' in codex, "Codex quota display must use app-server rate-limit API")
    require('"ephemeral": True' in codex, "fallback Codex threads must be ephemeral")
    require('"approvalPolicy": "never"' in codex, "fallback Codex threads must not request write approval")
    require('"sandbox": "read-only"' in codex, "fallback Codex threads must be read-only")
    require('"sandboxPolicy": {"type": "readOnly", "networkAccess": False}' in codex, "fallback Codex turns must be read-only with network disabled")
    require('"text_elements": []' in codex, "Codex text input must include current required text_elements field")

    require('codex_app_server_manager.shutdown_sync' in routes, "turning Codex off must stop its app-server immediately")
    require('operation="project_code_edit"' in routes, "project edits must pass project root into adaptive/Codex routing context")

    print("[adaptive-ai-contract] Ollama-first with OpenAI/Codex fallback wiring: OK")
    print("[adaptive-ai-contract] Codex opt-in master setting + immediate stop: OK")
    print("[adaptive-ai-contract] Codex read-only ephemeral generic fallback: OK")
    print("[adaptive-ai-contract] Codex rate-limit usage endpoint wiring: OK")
    print("[adaptive-ai-contract] project edit context propagation: OK")


if __name__ == "__main__":
    main()
