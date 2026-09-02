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

# Live STT is intentionally a rolling-context recognizer.  The previous
# implementation started a new transcription after only 1.8 seconds of new
# audio, which meant Whisper often received roughly three seconds of useful
# Korean sentence context.  Keep a full recent window and move it forward in
# small steps instead.
LIVE_WINDOW_SECONDS = 6.0
LIVE_STEP_SECONDS = 1.4
LIVE_INITIAL_CONTEXT_SECONDS = 2.8
LIVE_HOLDBACK_SECONDS = 1.0
LIVE_RMS_SILENCE_THRESHOLD = float(os.getenv("AGENTSTUDIO_STT_RMS_THRESHOLD", "0.0010") or "0.0010")
LIVE_PROMPT_MAX_CHARS = 420
LIVE_DUPLICATE_TIME_TOLERANCE_MS = 900


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

    The default device is CPU so opening the memo/STT tool never enables GPU by
    surprise. Users can explicitly opt in with AGENTSTUDIO_STT_DEVICE=cuda.
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

    async def ensure_model(
        self,
        notify: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> Any:
        cfg = self.config()
        desired = (cfg["model"], cfg["device"], cfg["compute_type"])
        if self._model is not None and self._loaded_config == desired:
            return self._model

        async with self._lock:
            if self._model is not None and self._loaded_config == desired:
                return self._model
            if notify:
                await notify(
                    {
                        "type": "status",
                        "status": "MODEL_LOADING",
                        "message": f"faster-whisper {cfg['model']} 모델 준비 중…",
                        **cfg,
                    }
                )
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
    """Backend PCM streaming session with rolling context and stop-time refinement."""

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

        handle = tempfile.NamedTemporaryFile(
            prefix="agentstudio_live_stt_",
            suffix=".pcm",
            delete=False,
        )
        self._pcm_path = Path(handle.name)
        self._pcm_file = handle
        self._send_lock = asyncio.Lock()
        self._processor_task: asyncio.Task | None = None
        self._closed = False
        self._stop_requested = False
        self._refine_requested = False
        self._total_samples = 0

        # _cursor_sample now means "last rolling-window end already processed".
        # This is different from the old start-cursor semantics and guarantees
        # that every live recognition receives up to LIVE_WINDOW_SECONDS of the
        # latest audio rather than a short ~3 second fragment.
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
        await self._send(
            {
                "type": "status",
                "status": "CONNECTED",
                "message": "Backend Audio Stream 연결됨 · faster-whisper 준비 중…",
                "engine": "faster-whisper",
                "sampleRate": self.sample_rate,
            }
        )
        self._processor_task = asyncio.create_task(
            self._processor_loop(),
            name=f"live-stt-{uuid.uuid4().hex[:8]}",
        )

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

    def _recent_prompt(self) -> str:
        """Return a short, already-committed context prompt for Korean continuity."""
        if not self._committed_texts:
            return ""
        prompt = " ".join(self._committed_texts[-6:]).strip()
        if len(prompt) > LIVE_PROMPT_MAX_CHARS:
            prompt = prompt[-LIVE_PROMPT_MAX_CHARS:]
        return prompt

    @staticmethod
    def _ranges_near(
        start_a: int,
        end_a: int,
        start_b: int,
        end_b: int,
        tolerance_ms: int = LIVE_DUPLICATE_TIME_TOLERANCE_MS,
    ) -> bool:
        return start_a <= end_b + tolerance_ms and start_b <= end_a + tolerance_ms

    def _is_duplicate(self, text: str, start_ms: int, end_ms: int) -> bool:
        """Reject only an actual repeated segment in the same time neighborhood.

        The old code treated substring containment as a duplicate.  That dropped
        valid expansions such as "인공지능 기술은" ->
        "인공지능 기술은 빠르게 발전하고 있습니다".  Text containment alone
        must never be enough to remove a newly recognized sentence.
        """
        normalized = _normalized_text(text)
        if not normalized:
            return True

        for prior in self._live_segments[-6:]:
            prev = _normalized_text(str(prior.get("text") or ""))
            if not prev or normalized != prev:
                continue
            prior_start = int(prior.get("offsetMs") or 0)
            prior_end = int(prior.get("endOffsetMs") or prior_start)
            if self._ranges_near(start_ms, end_ms, prior_start, prior_end):
                return True
        return False

    def _trim_committed_prefix(self, text: str) -> str:
        """Keep the newly extended suffix instead of throwing the whole row away.

        Rolling windows may return a segment that starts with the tail of an
        already committed segment and then continues with new words.  Remove
        only the repeated prefix when it can be identified safely.
        """
        current = str(text or "").strip()
        if not current:
            return ""

        current_words = current.split()
        for prior_text in reversed(self._committed_texts[-4:]):
            prior = str(prior_text or "").strip()
            if not prior:
                continue

            if current == prior:
                return ""
            if current.startswith(prior) and len(current) > len(prior):
                suffix = current[len(prior):].lstrip(" ,.!?·:;-/")
                if suffix:
                    return suffix

            prior_words = prior.split()
            max_overlap = min(len(prior_words), len(current_words))
            for size in range(max_overlap, 0, -1):
                left = " ".join(prior_words[-size:])
                right = " ".join(current_words[:size])
                if _normalized_text(left) != _normalized_text(right):
                    continue
                suffix = " ".join(current_words[size:]).strip()
                if suffix:
                    return suffix
                return ""
        return current

    def _transcribe_window_sync(
        self,
        model: Any,
        audio,
        window_start_ms: int,
        prompt: str = "",
    ) -> tuple[list[dict[str, Any]], str]:
        transcribe_kwargs: dict[str, Any] = {
            "language": self.language,
            "beam_size": 2,
            "best_of": 2,
            "temperature": 0.0,
            "vad_filter": True,
            "vad_parameters": {
                # External lectures and speaker audio have short natural pauses.
                # A slightly longer silence threshold prevents over-fragmentation.
                "min_silence_duration_ms": 500,
                "speech_pad_ms": 360,
            },
            # Avoid recursive hallucination from previous decoder state.  Recent
            # committed text is supplied explicitly as a short initial prompt.
            "condition_on_previous_text": False,
            "word_timestamps": False,
        }
        if prompt:
            transcribe_kwargs["initial_prompt"] = prompt

        segments_iter, _info = model.transcribe(audio, **transcribe_kwargs)
        rows: list[dict[str, Any]] = []
        for segment in segments_iter:
            text = str(getattr(segment, "text", "") or "").strip()
            if not text:
                continue
            start_ms = window_start_ms + int(
                max(0.0, float(getattr(segment, "start", 0.0))) * 1000
            )
            end_ms = window_start_ms + int(
                max(0.0, float(getattr(segment, "end", 0.0))) * 1000
            )
            rows.append(
                {
                    "text": text,
                    "startMs": start_ms,
                    "endMs": max(start_ms, end_ms),
                    "confidence": _confidence_from_logprob(
                        getattr(segment, "avg_logprob", None)
                    ),
                }
            )
        partial = rows[-1]["text"] if rows else ""
        return rows, partial

    async def _processor_loop(self) -> None:
        model: Any = None
        try:
            model = await faster_whisper_runtime.ensure_model(self._send)
            self._model_ready.set()
            cfg = faster_whisper_runtime.config()
            await self._send(
                {
                    "type": "ready",
                    "engine": "faster-whisper",
                    "message": f"STT 연결됨 · faster-whisper {cfg['model']} · {cfg['device']}",
                    "sampleRate": self.sample_rate,
                    "liveWindowSeconds": LIVE_WINDOW_SECONDS,
                    "liveStepSeconds": LIVE_STEP_SECONDS,
                    **cfg,
                }
            )
        except Exception as exc:
            self._model_error = str(exc)
            self._model_ready.set()
            await self._send(
                {
                    "type": "error",
                    "code": "STT_BACKEND_UNAVAILABLE",
                    "message": self._model_error,
                    "fallbackAllowed": True,
                }
            )
            return

        window_samples = int(LIVE_WINDOW_SECONDS * self.sample_rate)
        step_samples = int(LIVE_STEP_SECONDS * self.sample_rate)
        initial_samples = int(LIVE_INITIAL_CONTEXT_SECONDS * self.sample_rate)
        final_pass_done = False

        while not self._closed:
            total = self._total_samples

            if self._stop_requested:
                # Always run one final rolling window even when the latest live
                # pass already reached total.  This releases the holdback tail.
                if final_pass_done or total <= 0:
                    return
                final_pass_done = True
            else:
                if self._cursor_sample <= 0:
                    if total < initial_samples:
                        await asyncio.sleep(0.14)
                        continue
                elif total - self._cursor_sample < step_samples:
                    await asyncio.sleep(0.14)
                    continue

            end_sample = total
            start_sample = max(0, end_sample - window_samples)
            if end_sample <= start_sample:
                if self._stop_requested:
                    return
                await asyncio.sleep(0.14)
                continue

            audio = await asyncio.to_thread(
                self._read_pcm_samples,
                start_sample,
                end_sample,
            )
            rms = self._rms(audio)
            window_start_ms = int(start_sample * 1000 / self.sample_rate)
            window_end_ms = int(end_sample * 1000 / self.sample_rate)

            # Cheap energy VAD avoids Whisper calls for clear silence.  The
            # threshold is intentionally lower than before so quieter external
            # speaker audio is less likely to disappear.
            if rms < LIVE_RMS_SILENCE_THRESHOLD:
                await self._send(
                    {
                        "type": "level",
                        "rms": round(rms, 6),
                        "speech": False,
                    }
                )
                self._cursor_sample = end_sample
                if self._stop_requested:
                    return
                continue

            await self._send(
                {
                    "type": "level",
                    "rms": round(rms, 6),
                    "speech": True,
                }
            )
            try:
                rows, _partial = await asyncio.to_thread(
                    self._transcribe_window_sync,
                    model,
                    audio,
                    window_start_ms,
                    self._recent_prompt(),
                )
            except Exception as exc:
                await self._send(
                    {
                        "type": "warning",
                        "message": f"실시간 STT 구간 처리 실패: {exc}",
                    }
                )
                self._cursor_sample = end_sample
                if self._stop_requested:
                    return
                continue

            commit_boundary_ms = (
                window_end_ms
                if self._stop_requested
                else max(
                    window_start_ms,
                    window_end_ms - int(LIVE_HOLDBACK_SECONDS * 1000),
                )
            )

            for row in rows:
                row_start = int(row.get("startMs") or 0)
                row_end = int(row.get("endMs") or row_start)
                if row_end > commit_boundary_ms:
                    continue
                if row_end <= self._committed_until_ms + 80:
                    continue

                original_text = str(row.get("text") or "").strip()
                candidate_text = self._trim_committed_prefix(original_text)
                if not candidate_text:
                    self._committed_until_ms = max(self._committed_until_ms, row_end)
                    continue

                candidate_start = max(row_start, self._committed_until_ms)
                if self._is_duplicate(candidate_text, candidate_start, row_end):
                    self._committed_until_ms = max(self._committed_until_ms, row_end)
                    continue

                segment = {
                    "id": f"live-{uuid.uuid4().hex}",
                    "text": candidate_text,
                    "createdAt": "",
                    "offsetMs": candidate_start,
                    "endOffsetMs": row_end,
                    "confidence": row.get("confidence"),
                    "source": "faster-whisper",
                    "refined": False,
                }
                self._live_segments.append(segment)
                self._committed_texts.append(candidate_text)
                self._committed_until_ms = max(self._committed_until_ms, row_end)
                await self._send({"type": "final", "segment": segment})

            pending_rows = [row for row in rows if int(row.get("endMs") or 0) > commit_boundary_ms]
            pending_text = " ".join(
                str(row.get("text") or "").strip() for row in pending_rows
            ).strip()
            if pending_rows and pending_text:
                partial_start_ms = min(int(row.get("startMs") or 0) for row in pending_rows)
                partial_end_ms = max(
                    int(row.get("endMs") or partial_start_ms) for row in pending_rows
                )
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
                    "confidence": (
                        round(sum(confidences) / len(confidences), 4)
                        if confidences
                        else None
                    ),
                    "source": "faster-whisper",
                    "refined": False,
                    "provisional": True,
                }
            else:
                partial_segment = None

            await self._send(
                {
                    "type": "partial",
                    "text": pending_text,
                    "segment": partial_segment,
                    "windowStartMs": window_start_ms,
                    "windowEndMs": window_end_ms,
                    "commitBoundaryMs": commit_boundary_ms,
                }
            )
            self._cursor_sample = end_sample

            if self._stop_requested:
                return

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
            beam_size=4,
            best_of=4,
            temperature=0.0,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 500,
                "speech_pad_ms": 400,
            },
            # Full-recording refinement benefits from the previous decoded text
            # and is not latency-sensitive like the live path.
            condition_on_previous_text=True,
            word_timestamps=False,
        )
        rows: list[dict[str, Any]] = []
        for segment in segments_iter:
            text = str(getattr(segment, "text", "") or "").strip()
            if not text:
                continue
            start_ms = int(max(0.0, float(getattr(segment, "start", 0.0))) * 1000)
            end_ms = int(max(0.0, float(getattr(segment, "end", 0.0))) * 1000)
            rows.append(
                {
                    "id": f"refined-{uuid.uuid4().hex}",
                    "text": text,
                    "createdAt": "",
                    "offsetMs": start_ms,
                    "endOffsetMs": max(start_ms, end_ms),
                    "confidence": _confidence_from_logprob(
                        getattr(segment, "avg_logprob", None)
                    ),
                    "source": "faster-whisper",
                    "refined": True,
                }
            )
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
            await self._send(
                {
                    "type": "stopped",
                    "refined": False,
                    "segments": self._live_segments,
                }
            )
            return self._live_segments

        model = await faster_whisper_runtime.ensure_model(self._send)
        duration_ms = int(self._total_samples * 1000 / self.sample_rate)
        await self._send(
            {
                "type": "refine_status",
                "status": "RUNNING",
                "message": "녹음 전체를 다시 분석해 누락/오인식 문장을 정밀 보정하고 있습니다…",
                "durationMs": duration_ms,
            }
        )
        try:
            refined = await asyncio.to_thread(self._refine_sync, model)
            await self._send(
                {
                    "type": "refined",
                    "segments": refined,
                    "rangeStartMs": 0,
                    "rangeEndMs": duration_ms,
                    "durationMs": duration_ms,
                    "message": f"정밀 보정 완료 · {len(refined)}개 구간",
                }
            )
            return refined
        except Exception as exc:
            await self._send(
                {
                    "type": "refine_status",
                    "status": "ERROR",
                    "message": f"정밀 보정 실패: {exc}",
                }
            )
            await self._send(
                {
                    "type": "stopped",
                    "refined": False,
                    "segments": self._live_segments,
                }
            )
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
        "live_step_seconds": LIVE_STEP_SECONDS,
        "initial_context_seconds": LIVE_INITIAL_CONTEXT_SECONDS,
        "holdback_seconds": LIVE_HOLDBACK_SECONDS,
        "rms_silence_threshold": LIVE_RMS_SILENCE_THRESHOLD,
        "vad": "energy-gate + faster-whisper/Silero VAD",
        "context_prompt": True,
        "safe_temporal_dedup": True,
        "final_refinement": True,
    }
