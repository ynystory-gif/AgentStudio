from __future__ import annotations

import asyncio
import json
import math
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable


STT_SAMPLE_RATE = 16_000
STT_SAMPLE_WIDTH_BYTES = 2  # signed PCM16 mono
LIVE_WINDOW_SECONDS = 6.0
LIVE_OVERLAP_SECONDS = 1.2
LIVE_HOLDBACK_SECONDS = 0.7
LIVE_MIN_NEW_AUDIO_SECONDS = 1.8


def _language_code(value: str) -> str:
    text = str(value or "ko-KR").strip().lower()
    if text.startswith("ko"):
        return "ko"
    if text.startswith("en"):
        return "en"
    if text.startswith("ja"):
        return "ja"
    if text.startswith("zh"):
        return "zh"
    return text.split("-")[0] or "ko"


def _normalized_text(value: str) -> str:
    return "".join(ch.casefold() for ch in str(value or "") if ch.isalnum())


def _confidence_from_logprob(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    try:
        return round(max(0.0, min(1.0, math.exp(number))), 4)
    except (OverflowError, ValueError):
        return None


class FasterWhisperRuntime:
    """Lazy, process-wide faster-whisper model runtime.

    The default device is CPU so opening the memo/STT tool never enables GPU by surprise.
    Users can explicitly opt in with AGENTSTUDIO_STT_DEVICE=cuda.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._lock = asyncio.Lock()
        self._loaded_config: tuple[str, str, str] | None = None
        self._last_error = ""

    def config(self) -> dict[str, str]:
        model_name = str(os.getenv("AGENTSTUDIO_STT_MODEL", "small") or "small").strip()
        device = str(os.getenv("AGENTSTUDIO_STT_DEVICE", "cpu") or "cpu").strip().lower()
        compute_type = str(
            os.getenv(
                "AGENTSTUDIO_STT_COMPUTE_TYPE",
                "float16" if device == "cuda" else "int8",
            )
            or ("float16" if device == "cuda" else "int8")
        ).strip()
        return {"model": model_name, "device": device, "compute_type": compute_type}

    async def ensure_model(self, notify: Callable[[dict[str, Any]], Awaitable[None]] | None = None) -> Any:
        cfg = self.config()
        desired = (cfg["model"], cfg["device"], cfg["compute_type"])
        if self._model is not None and self._loaded_config == desired:
            return self._model

        async with self._lock:
            if self._model is not None and self._loaded_config == desired:
                return self._model
            if notify:
                await notify({
                    "type": "status",
                    "status": "MODEL_LOADING",
                    "message": f"faster-whisper {cfg['model']} 모델 준비 중…",
                    **cfg,
                })
            try:
                from faster_whisper import WhisperModel
            except Exception as exc:  # pragma: no cover - depends on local installation
                self._last_error = f"faster-whisper를 불러올 수 없습니다: {exc}"
                raise RuntimeError(
                    "faster-whisper가 설치되지 않았습니다. SYSTEM_ADMIN에서 Backend 의존성을 설치/갱신한 뒤 다시 시작하세요."
                ) from exc

            def _load() -> Any:
                return WhisperModel(
                    cfg["model"],
                    device=cfg["device"],
                    compute_type=cfg["compute_type"],
                )

            try:
                self._model = await asyncio.to_thread(_load)
                self._loaded_config = desired
                self._last_error = ""
            except Exception as exc:
                self._model = None
                self._loaded_config = None
                self._last_error = str(exc)
                raise RuntimeError(f"faster-whisper 모델 준비 실패: {exc}") from exc
            return self._model

    def status(self) -> dict[str, Any]:
        cfg = self.config()
        return {
            "ok": True,
            "engine": "faster-whisper",
            "loaded": self._model is not None,
            "loaded_config": list(self._loaded_config) if self._loaded_config else None,
            "last_error": self._last_error,
            **cfg,
        }


faster_whisper_runtime = FasterWhisperRuntime()


class LiveSttSession:
    """Backend PCM streaming session with overlap/VAD and stop-time full refinement."""

    def __init__(
        self,
        send_json: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        project_root: Path,
        language: str = "ko-KR",
        sample_rate: int = STT_SAMPLE_RATE,
    ) -> None:
        self.send_json = send_json
        self.project_root = Path(project_root)
        self.language = _language_code(language)
        self.sample_rate = int(sample_rate or STT_SAMPLE_RATE)
        if self.sample_rate != STT_SAMPLE_RATE:
            raise ValueError(f"지원 sample rate는 {STT_SAMPLE_RATE}Hz입니다.")

        handle = tempfile.NamedTemporaryFile(prefix="agentstudio_live_stt_", suffix=".pcm", delete=False)
        self._pcm_path = Path(handle.name)
        self._pcm_file = handle
        self._send_lock = asyncio.Lock()
        self._processor_task: asyncio.Task | None = None
        self._closed = False
        self._stop_requested = False
        self._refine_requested = False
        self._total_samples = 0
        self._cursor_sample = 0
        self._committed_until_ms = 0
        self._committed_texts: list[str] = []
        self._live_segments: list[dict[str, Any]] = []
        self._model_ready = asyncio.Event()
        self._model_error = ""

    async def _send(self, payload: dict[str, Any]) -> None:
        if self._closed:
            return
        async with self._send_lock:
            try:
                await self.send_json(payload)
            except Exception:
                self._closed = True

    async def start(self) -> None:
        await self._send({
            "type": "status",
            "status": "CONNECTED",
            "message": "Backend Audio Stream 연결됨 · faster-whisper 준비 중…",
            "engine": "faster-whisper",
            "sampleRate": self.sample_rate,
        })
        self._processor_task = asyncio.create_task(self._processor_loop(), name=f"live-stt-{uuid.uuid4().hex[:8]}")

    def append_pcm(self, chunk: bytes) -> None:
        if self._closed or self._stop_requested or not chunk:
            return
        usable = len(chunk) - (len(chunk) % STT_SAMPLE_WIDTH_BYTES)
        if usable <= 0:
            return
        data = chunk[:usable]
        self._pcm_file.write(data)
        self._pcm_file.flush()
        self._total_samples += usable // STT_SAMPLE_WIDTH_BYTES

    def _read_pcm_samples(self, start_sample: int, end_sample: int):
        import numpy as np

        start = max(0, int(start_sample))
        end = max(start, int(end_sample))
        length = end - start
        if length <= 0:
            return np.empty((0,), dtype=np.float32)
        with self._pcm_path.open("rb") as stream:
            stream.seek(start * STT_SAMPLE_WIDTH_BYTES)
            raw = stream.read(length * STT_SAMPLE_WIDTH_BYTES)
        if not raw:
            return np.empty((0,), dtype=np.float32)
        pcm = np.frombuffer(raw, dtype="<i2").astype(np.float32)
        return pcm / 32768.0

    @staticmethod
    def _rms(audio) -> float:
        if getattr(audio, "size", 0) <= 0:
            return 0.0
        try:
            import numpy as np

            return float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
        except Exception:
            return 0.0

    def _is_duplicate(self, text: str) -> bool:
        normalized = _normalized_text(text)
        if not normalized:
            return True
        for prior in self._committed_texts[-5:]:
            prev = _normalized_text(prior)
            if not prev:
                continue
            if normalized == prev:
                return True
            if len(normalized) >= 8 and (normalized in prev or prev in normalized):
                return True
        return False

    def _transcribe_window_sync(self, model: Any, audio, window_start_ms: int) -> tuple[list[dict[str, Any]], str]:
        segments_iter, _info = model.transcribe(
            audio,
            language=self.language,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 300,
                "speech_pad_ms": 260,
            },
            condition_on_previous_text=False,
            word_timestamps=False,
        )
        rows: list[dict[str, Any]] = []
        for segment in segments_iter:
            text = str(getattr(segment, "text", "") or "").strip()
            if not text:
                continue
            start_ms = window_start_ms + int(max(0.0, float(getattr(segment, "start", 0.0))) * 1000)
            end_ms = window_start_ms + int(max(0.0, float(getattr(segment, "end", 0.0))) * 1000)
            rows.append({
                "text": text,
                "startMs": start_ms,
                "endMs": max(start_ms, end_ms),
                "confidence": _confidence_from_logprob(getattr(segment, "avg_logprob", None)),
            })
        partial = rows[-1]["text"] if rows else ""
        return rows, partial

    async def _processor_loop(self) -> None:
        model: Any = None
        try:
            model = await faster_whisper_runtime.ensure_model(self._send)
            self._model_ready.set()
            cfg = faster_whisper_runtime.config()
            await self._send({
                "type": "ready",
                "engine": "faster-whisper",
                "message": f"STT 연결됨 · faster-whisper {cfg['model']} · {cfg['device']}",
                "sampleRate": self.sample_rate,
                **cfg,
            })
        except Exception as exc:
            self._model_error = str(exc)
            self._model_ready.set()
            await self._send({
                "type": "error",
                "code": "STT_BACKEND_UNAVAILABLE",
                "message": self._model_error,
                "fallbackAllowed": True,
            })
            return

        window_samples = int(LIVE_WINDOW_SECONDS * self.sample_rate)
        overlap_samples = int(LIVE_OVERLAP_SECONDS * self.sample_rate)
        holdback_samples = int(LIVE_HOLDBACK_SECONDS * self.sample_rate)
        min_new_samples = int(LIVE_MIN_NEW_AUDIO_SECONDS * self.sample_rate)

        while not self._closed:
            total = self._total_samples
            remaining = total - self._cursor_sample
            if not self._stop_requested and remaining < min_new_samples:
                await asyncio.sleep(0.18)
                continue
            if self._stop_requested and remaining <= 0:
                return

            end_sample = min(total, self._cursor_sample + window_samples)
            start_sample = max(0, self._cursor_sample - overlap_samples)
            if end_sample <= start_sample:
                if self._stop_requested:
                    return
                await asyncio.sleep(0.18)
                continue

            audio = await asyncio.to_thread(self._read_pcm_samples, start_sample, end_sample)
            rms = self._rms(audio)
            window_start_ms = int(start_sample * 1000 / self.sample_rate)
            window_end_ms = int(end_sample * 1000 / self.sample_rate)

            # Cheap energy VAD avoids invoking Whisper continuously for clear silence;
            # faster-whisper's Silero VAD remains enabled during actual transcription.
            if rms < 0.0015:
                await self._send({"type": "level", "rms": round(rms, 6), "speech": False})
                self._cursor_sample = end_sample if self._stop_requested else max(self._cursor_sample + 1, end_sample - holdback_samples)
                continue

            await self._send({"type": "level", "rms": round(rms, 6), "speech": True})
            try:
                rows, _partial = await asyncio.to_thread(self._transcribe_window_sync, model, audio, window_start_ms)
            except Exception as exc:
                await self._send({"type": "warning", "message": f"실시간 STT 구간 처리 실패: {exc}"})
                self._cursor_sample = end_sample if self._stop_requested else max(self._cursor_sample + 1, end_sample - holdback_samples)
                continue

            commit_boundary_ms = window_end_ms if self._stop_requested else max(window_start_ms, window_end_ms - int(LIVE_HOLDBACK_SECONDS * 1000))
            for row in rows:
                if row["endMs"] > commit_boundary_ms:
                    continue
                if row["endMs"] <= self._committed_until_ms + 80:
                    continue
                if self._is_duplicate(row["text"]):
                    self._committed_until_ms = max(self._committed_until_ms, row["endMs"])
                    continue
                segment = {
                    "id": f"live-{uuid.uuid4().hex}",
                    "text": row["text"],
                    "createdAt": "",
                    "offsetMs": row["startMs"],
                    "endOffsetMs": row["endMs"],
                    "confidence": row["confidence"],
                    "source": "faster-whisper",
                    "refined": False,
                }
                self._live_segments.append(segment)
                self._committed_texts.append(row["text"])
                self._committed_until_ms = max(self._committed_until_ms, row["endMs"])
                await self._send({"type": "final", "segment": segment})

            pending_rows = [row for row in rows if row["endMs"] > commit_boundary_ms]
            pending_text = " ".join(str(row.get("text") or "").strip() for row in pending_rows).strip()
            if pending_rows and pending_text:
                partial_start_ms = min(int(row.get("startMs") or 0) for row in pending_rows)
                partial_end_ms = max(int(row.get("endMs") or partial_start_ms) for row in pending_rows)
                confidences = [
                    float(row["confidence"])
                    for row in pending_rows
                    if row.get("confidence") is not None
                ]
                partial_segment = {
                    "id": f"partial-{partial_start_ms}-{partial_end_ms}",
                    "text": pending_text,
                    "createdAt": "",
                    "offsetMs": partial_start_ms,
                    "endOffsetMs": partial_end_ms,
                    "confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
                    "source": "faster-whisper",
                    "refined": False,
                    "provisional": True,
                }
            else:
                partial_segment = None
            await self._send({
                "type": "partial",
                "text": pending_text,
                "segment": partial_segment,
                "windowStartMs": window_start_ms,
                "windowEndMs": window_end_ms,
                "commitBoundaryMs": commit_boundary_ms,
            })
            self._cursor_sample = end_sample if self._stop_requested else max(self._cursor_sample + 1, end_sample - holdback_samples)

    def _refine_sync(self, model: Any) -> list[dict[str, Any]]:
        import numpy as np

        self._pcm_file.flush()
        audio = np.fromfile(self._pcm_path, dtype="<i2").astype(np.float32)
        if audio.size <= 0:
            return []
        audio /= 32768.0
        segments_iter, _info = model.transcribe(
            audio,
            language=self.language,
            beam_size=3,
            best_of=3,
            temperature=0.0,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 300,
                "speech_pad_ms": 320,
            },
            condition_on_previous_text=False,
            word_timestamps=False,
        )
        rows: list[dict[str, Any]] = []
        for segment in segments_iter:
            text = str(getattr(segment, "text", "") or "").strip()
            if not text:
                continue
            start_ms = int(max(0.0, float(getattr(segment, "start", 0.0))) * 1000)
            end_ms = int(max(0.0, float(getattr(segment, "end", 0.0))) * 1000)
            rows.append({
                "id": f"refined-{uuid.uuid4().hex}",
                "text": text,
                "createdAt": "",
                "offsetMs": start_ms,
                "endOffsetMs": max(start_ms, end_ms),
                "confidence": _confidence_from_logprob(getattr(segment, "avg_logprob", None)),
                "source": "faster-whisper",
                "refined": True,
            })
        return rows

    async def finish(self, refine: bool = True) -> list[dict[str, Any]]:
        if self._stop_requested:
            return self._live_segments
        self._stop_requested = True
        self._refine_requested = bool(refine)
        self._pcm_file.flush()

        if self._processor_task:
            try:
                await asyncio.wait_for(self._processor_task, timeout=45.0)
            except asyncio.TimeoutError:
                self._processor_task.cancel()
            except Exception:
                pass

        if not refine or self._model_error:
            await self._send({"type": "stopped", "refined": False, "segments": self._live_segments})
            return self._live_segments

        model = await faster_whisper_runtime.ensure_model(self._send)
        duration_ms = int(self._total_samples * 1000 / self.sample_rate)
        await self._send({
            "type": "refine_status",
            "status": "RUNNING",
            "message": "녹음 전체를 다시 분석해 누락/오인식 문장을 정밀 보정하고 있습니다…",
            "durationMs": duration_ms,
        })
        try:
            refined = await asyncio.to_thread(self._refine_sync, model)
            await self._send({
                "type": "refined",
                "segments": refined,
                "rangeStartMs": 0,
                "rangeEndMs": duration_ms,
                "durationMs": duration_ms,
                "message": f"정밀 보정 완료 · {len(refined)}개 구간",
            })
            return refined
        except Exception as exc:
            await self._send({
                "type": "refine_status",
                "status": "ERROR",
                "message": f"정밀 보정 실패: {exc}",
            })
            await self._send({"type": "stopped", "refined": False, "segments": self._live_segments})
            return self._live_segments

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except BaseException:
                pass
        try:
            self._pcm_file.close()
        except Exception:
            pass
        try:
            self._pcm_path.unlink(missing_ok=True)
        except Exception:
            pass


def live_stt_runtime_status() -> dict[str, Any]:
    return {
        **faster_whisper_runtime.status(),
        "sample_rate": STT_SAMPLE_RATE,
        "live_window_seconds": LIVE_WINDOW_SECONDS,
        "overlap_seconds": LIVE_OVERLAP_SECONDS,
        "holdback_seconds": LIVE_HOLDBACK_SECONDS,
        "vad": "energy-gate + faster-whisper/Silero VAD",
        "final_refinement": True,
    }
