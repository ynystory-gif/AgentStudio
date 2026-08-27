from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.services import gpu_runtime_manager as gpu

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
PANEL = (ROOT / "frontend" / "src" / "components" / "system" / "SystemRuntimePanels.tsx").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
OLLAMA = (ROOT / "backend" / "app" / "services" / "ollama_runtime_manager.py").read_text(encoding="utf-8")
LOCAL = (ROOT / "backend" / "app" / "services" / "local_control.py").read_text(encoding="utf-8")

checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.376'" in APP,
    "gpu start button": "GPU 시작" in PANEL,
    "gpu stop button": ">GPU 정지<" in PANEL,
    "gpu recommendation alert": "GPU 가속 사용을 권장하는 작업입니다" in APP,
    "gpu start after confirmation": "'/settings/gpu/runtime/start'" in APP,
    "design guard": "actionLabel:'설계 검토'" in APP,
    "development guard": "actionLabel:redevelopment?'재개발 시작':'개발 시작'" in APP,
    "gpu status endpoint": '"/settings/gpu/runtime/status"' in ROUTES,
    "gpu start endpoint": '"/settings/gpu/runtime/start"' in ROUTES,
    "gpu stop endpoint": '"/settings/gpu/runtime/stop"' in ROUTES,
    "gpu recommendation endpoint": '"/settings/gpu/recommendation"' in ROUTES,
    "ollama gpu environment": "gpu_runtime_environment(os.environ.copy())" in OLLAMA,
    "test command gpu environment": "env=gpu_runtime_environment(os.environ.copy())" in LOCAL,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("FAIL v5.376 GPU acceleration UI/API contract: " + ", ".join(failed))

original_query = gpu._query_nvidia
original_state = gpu.STATE_FILE
try:
    with tempfile.TemporaryDirectory() as tmp:
        gpu.STATE_FILE = Path(tmp) / "gpu_runtime.json"
        gpu._query_nvidia = lambda: [{
            "index": 0,
            "name": "Test GPU",
            "memory_total_mb": 8192,
            "memory_used_mb": 0,
            "utilization_percent": 0,
            "driver_version": "test",
        }]

        stopped = gpu.set_gpu_runtime_enabled(False)
        assert stopped["available"] is True and stopped["enabled"] is False
        env = gpu.gpu_runtime_environment({})
        assert env["CUDA_VISIBLE_DEVICES"] == "-1"
        assert env["AGENTSTUDIO_GPU_ACCELERATION"] == "0"

        started = gpu.set_gpu_runtime_enabled(True)
        assert started["enabled"] is True
        env = gpu.gpu_runtime_environment({"CUDA_VISIBLE_DEVICES": "-1"})
        assert "CUDA_VISIBLE_DEVICES" not in env
        assert env["AGENTSTUDIO_GPU_ACCELERATION"] == "1"

        ollama = gpu.gpu_recommendation(request="일반 Agent", ai_mode="ollama", phase="design")
        assert ollama["recommended"] and "Ollama 로컬 LLM 전용 모드" in ollama["reasons"]

        embedding = gpu.gpu_recommendation(request="pgvector 로컬 임베딩 검색 Agent", ai_mode="openai", phase="development")
        assert embedding["recommended"] and "로컬 Embedding 모델 사용" in embedding["reasons"]

        media = gpu.gpu_recommendation(request="이미지 분석 AI Agent를 테스트한다", ai_mode="openai", phase="development")
        assert media["recommended"] and "이미지/영상 AI Agent 테스트" in media["reasons"]
finally:
    gpu._query_nvidia = original_query
    gpu.STATE_FILE = original_state

print("PASS v5.376 GPU Acceleration Recommendation + Control contract")
