from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


checks: list[tuple[str, bool]] = []

def check(name: str, condition: bool) -> None:
    checks.append((name, bool(condition)))


app = text("frontend/src/App.jsx")
provider = text("frontend/src/components/media/MediaSessionProvider.tsx")
memo = text("frontend/src/components/memo/ProjectMemoPanel.tsx")
css = text("frontend/src/styles.css")
routes = text("backend/app/api/routes.py")
main = text("backend/app/main.py")
service = text("backend/app/services/live_stt_service.py")
requirements = text("backend/requirements.txt")
env_example = text("backend/.env.example")
codex = text("backend/app/services/codex_app_server_service.py")
readme = text("README_V5_479.md")

check("frontend version 5.479", "AGENTSTUDIO_FRONTEND_VERSION='5.479'" in app)
check("backend FastAPI version 5.479", 'version="5.479"' in main)
check("health version 5.479", '"version": "5.479"' in routes)
check("Codex client version 5.479", 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.479"' in codex)
check("health build marker", "+BackendFasterWhisperStreamingStt+SttOverlapVad+StopTimeTranscriptRefinement" in routes)

check("faster-whisper dependency", "faster-whisper>=1.1.1" in requirements)
check("numpy dependency", "numpy>=1.26" in requirements)
check("CPU default STT device", 'AGENTSTUDIO_STT_DEVICE", "cpu"' in service)
check("STT env example", "AGENTSTUDIO_STT_MODEL=small" in env_example and "AGENTSTUDIO_STT_DEVICE=cpu" in env_example)
check("lazy faster-whisper import", "from faster_whisper import WhisperModel" in service and "ensure_model" in service)
check("PCM 16k", "STT_SAMPLE_RATE = 16_000" in service and "TARGET_STT_SAMPLE_RATE = 16_000" in provider)
check("overlap window", "LIVE_OVERLAP_SECONDS = 1.2" in service)
check("holdback window", "LIVE_HOLDBACK_SECONDS = 0.7" in service)
check("energy VAD", "rms < 0.0015" in service)
check("Silero/faster-whisper VAD", "vad_filter=True" in service and "min_silence_duration_ms" in service)
check("live WebSocket endpoint", '@router.websocket("/media-stt/stream")' in routes)
check("binary PCM receive", 'message.get("bytes")' in routes and "session.append_pcm" in routes)
check("WebSocket PCM send", "socket.send(pcm.buffer)" in provider)
check("screen audio supported", "new MediaStream(audioTracks)" in provider and "getAudioTracks()" in provider)
check("browser fallback only auxiliary", "startSpeechRecognitionFallback" in provider and "browser-speech-recognition" in provider)
check("external speaker echo cancellation disabled", "echoCancellation: false" in provider)
check("interim/final split", "type === 'partial'" in provider and "type === 'final'" in provider)
check("stop-time full refinement", "_refine_sync" in service and '"type": "refined"' in service and "beam_size=3" in service)
check("refined transcript replaces live transcript", "setTranscriptSegments(segments)" in provider and "transcriptSegmentsRef.current = segments" in provider)
check("transcript rich persistence", '"endOffsetMs": end_offset_ms' in routes and '"refined": item.get("refined") is True' in routes)
check("audio level meter", "project-live-audio-meter" in memo and "audioLevel" in provider)
check("STT health metrics", "sttReconnectCount" in memo and "sttDroppedChunks" in memo and "lastRecognizedAt" in memo)
check("refinement UI", "project-live-refine-status" in memo and "refineStatus === 'RUNNING'" in memo)
check("screen audio guidance updated", "탭 오디오 공유" in memo and "시스템 오디오 공유" in memo)
check("refined transcript badge", "segment.refined" in memo and ">보정</em>" in memo)
check("health CSS", ".project-live-health" in css and ".project-live-audio-meter" in css)
check("README current feature", "Backend Faster-Whisper Streaming STT" in readme)

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"{'PASS' if ok else 'FAIL'} - {name}")
print(f"\n{len(checks) - len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit("FAILED: " + ", ".join(failed))
