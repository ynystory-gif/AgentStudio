from pathlib import Path

root = Path(__file__).resolve().parents[2]


def rw(rel: str, old: str, new: str, count: int = -1) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing patch anchor: {rel}: {old[:120]!r}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


rw("frontend/src/App.jsx", "const AGENTSTUDIO_FRONTEND_VERSION='5.491'", "const AGENTSTUDIO_FRONTEND_VERSION='5.492'")
rw("backend/app/main.py", 'version="5.491"', 'version="5.492"')
rw("backend/app/api/routes.py", '"version": "5.491"', '"version": "5.492"')

memo = "frontend/src/components/memo/ProjectMemoPanel.tsx"
rw(
    memo,
    "  const [liveSummarySegmentCount, setLiveSummarySegmentCount] = useState(0)\n",
    "  const [liveSummarySegmentCount, setLiveSummarySegmentCount] = useState(0)\n"
    "  const [liveFileSaving, setLiveFileSaving] = useState<'' | 'TRANSCRIPT' | 'SUMMARY'>('')\n"
    "  const [liveSavedFile, setLiveSavedFile] = useState<{ kind: 'TRANSCRIPT' | 'SUMMARY'; path: string; relativePath: string } | null>(null)\n",
)
rw(
    memo,
    "    setLiveSummarySegmentCount(0)\n    setSelectedId('')\n",
    "    setLiveSummarySegmentCount(0)\n    setLiveFileSaving('')\n    setLiveSavedFile(null)\n    setSelectedId('')\n",
    1,
)

insert_anchor = "  const visibleMemos = useMemo(() => {\n"
functions = """  const persistLiveTextFile = async (kind: 'TRANSCRIPT' | 'SUMMARY', text: string) => {
    const content = String(text || '').trim()
    if (!projectRoot) throw new Error('프로젝트를 먼저 선택하세요.')
    if (!content) throw new Error(kind === 'SUMMARY' ? '저장할 요약정리 내용이 없습니다.' : '저장할 실시간 Transcript가 없습니다.')
    const result = await api<{ path?: string; relative_path?: string }>('/media-stt/save-text', {
      method: 'POST',
      body: JSON.stringify({ root: projectRoot, kind: kind.toLowerCase(), text: content })
    })
    const savedPath = String(result?.path || '').trim()
    const relativePath = String(result?.relative_path || '').trim()
    if (!savedPath) throw new Error('Backend가 저장된 파일 경로를 반환하지 않았습니다.')
    setLiveSavedFile({ kind, path: savedPath, relativePath })
    setStatus(`${kind === 'SUMMARY' ? '요약정리' : '실시간 Transcript'} 텍스트 파일을 저장했습니다.`)
    return savedPath
  }

  const saveLiveTranscriptFile = async () => {
    if (liveFileSaving) return
    const transcript = String(mediaSession.transcriptText || '').trim()
    if (!transcript) {
      setStatus('저장할 실시간 Transcript가 없습니다.')
      return
    }
    setLiveFileSaving('TRANSCRIPT')
    try {
      await persistLiveTextFile('TRANSCRIPT', transcript)
    } catch (saveError) {
      setStatus(`실시간 Transcript 파일 저장 실패: ${String((saveError as Error)?.message || saveError)}`)
    } finally {
      setLiveFileSaving('')
    }
  }

  const saveLiveSummaryFile = async () => {
    if (liveFileSaving || liveSummaryLoading) return
    const transcript = String(mediaSession.transcriptText || '').trim()
    if (!transcript) {
      setStatus('요약정리할 실시간 Transcript가 없습니다.')
      return
    }
    setLiveFileSaving('SUMMARY')
    setLiveSummaryError('')
    try {
      const result = await api<{ summary?: string; truncated?: boolean }>('/media-stt/summarize', {
        method: 'POST',
        body: JSON.stringify({ root: projectRoot, transcript })
      })
      const summary = String(result?.summary || '').trim()
      if (!summary) throw new Error('요약 결과가 비어 있습니다.')
      setLiveSummary(summary)
      setLiveSummarySegmentCount(mediaSession.transcriptSegments.length)
      await persistLiveTextFile('SUMMARY', summary)
    } catch (saveError) {
      const message = String((saveError as Error)?.message || saveError)
      setLiveSummaryError(`요약정리 파일 저장 실패: ${message}`)
      setStatus(`요약정리 파일 저장 실패: ${message}`)
    } finally {
      setLiveFileSaving('')
    }
  }

"""
rw(memo, insert_anchor, functions + insert_anchor, 1)

old_actions = """          <div className=\"project-live-transcript-head-actions\">
            <span>{mediaSession.transcriptSegments.length}{mediaSession.interimSegment ? '+1' : ''}개 구간</span>
            <button type=\"button\" className=\"summary\" onClick={() => void summarizeLiveTranscript()} disabled={!mediaSession.transcriptText.trim() || liveSummaryLoading}>{liveSummaryLoading ? '요약 중…' : '✦ 요약정리'}</button>
          </div>"""
new_actions = """          <div className=\"project-live-transcript-head-actions\">
            <span>{mediaSession.transcriptSegments.length}{mediaSession.interimSegment ? '+1' : ''}개 구간</span>
            <button type=\"button\" className=\"save-file\" onClick={() => void saveLiveTranscriptFile()} disabled={!mediaSession.transcriptText.trim() || Boolean(liveFileSaving)}>{liveFileSaving === 'TRANSCRIPT' ? '저장 중…' : '💾 파일 저장'}</button>
            <button type=\"button\" className=\"save-file summary-file\" onClick={() => void saveLiveSummaryFile()} disabled={!mediaSession.transcriptText.trim() || Boolean(liveFileSaving) || liveSummaryLoading}>{liveFileSaving === 'SUMMARY' ? '요약·저장 중…' : '💾 요약 파일 저장'}</button>
            <button type=\"button\" className=\"summary\" onClick={() => void summarizeLiveTranscript()} disabled={!mediaSession.transcriptText.trim() || liveSummaryLoading || Boolean(liveFileSaving)}>{liveSummaryLoading ? '요약 중…' : '✦ 요약정리'}</button>
          </div>"""
rw(memo, old_actions, new_actions, 1)

summary_anchor = "      {(liveSummary || liveSummaryLoading || liveSummaryError) && (\n"
saved_path_ui = """      {liveSavedFile && (
        <div className=\"project-live-save-path\" title={liveSavedFile.path}>
          <strong>{liveSavedFile.kind === 'SUMMARY' ? '요약 파일 저장 경로' : 'Transcript 파일 저장 경로'}</strong>
          <code>{liveSavedFile.path}</code>
        </div>
      )}

"""
rw(memo, summary_anchor, saved_path_ui + summary_anchor, 1)

styles = root / "frontend/src/styles.css"
styles.write_text(
    styles.read_text(encoding="utf-8")
    + """

/* v5.492 Live Transcript text-file persistence */
.project-live-transcript-head-actions>button.save-file{
  min-height:27px;
  border:1px solid #3f6f55;
  border-radius:6px;
  background:#153927;
  color:#d8f5e4;
  font-size:13px;
  font-weight:800;
  white-space:nowrap;
}
.project-live-transcript-head-actions>button.save-file:hover:not(:disabled){background:#1b4a32;border-color:#55956f;}
.project-live-transcript-head-actions>button.save-file.summary-file{border-color:#665f93;background:#2a2749;color:#e5e0ff;}
.project-live-transcript-head-actions>button.save-file.summary-file:hover:not(:disabled){background:#37315f;border-color:#7f75b5;}
.project-live-save-path{
  display:grid;
  gap:5px;
  margin:7px 0 9px;
  padding:8px 10px;
  border:1px solid #2c5b43;
  border-radius:6px;
  background:#0d2519;
  color:#cce8d7;
}
.project-live-save-path strong{font-size:13px;color:#8fd0a8;}
.project-live-save-path code{display:block;overflow-wrap:anywhere;word-break:break-all;white-space:normal;font:12px/1.45 Consolas,monospace;color:#dbe9e1;}
@media(max-width:1100px){
  .project-live-transcript-head-actions{flex-wrap:wrap;justify-content:flex-start;}
}
""",
    encoding="utf-8",
)

routes = root / "backend/app/api/routes.py"
route_text = routes.read_text(encoding="utf-8")
if '@router.post("/media-stt/save-text")' in route_text:
    raise SystemExit("save-text endpoint already exists unexpectedly")
route_text += """

# v5.492: Persist live STT transcript/summary as user-visible UTF-8 text files.
@router.post(\"/media-stt/save-text\")
async def save_media_stt_text_file(request: Request):
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f\"잘못된 저장 요청입니다: {exc}\") from exc

    project_root = str((payload or {}).get(\"root\") or \"\").strip()
    content = str((payload or {}).get(\"text\") or \"\").strip()
    kind = str((payload or {}).get(\"kind\") or \"transcript\").strip().casefold()
    if not project_root:
        raise HTTPException(status_code=400, detail=\"프로젝트 경로가 없습니다.\")
    if not content:
        raise HTTPException(status_code=400, detail=\"저장할 텍스트가 없습니다.\")
    if kind not in {\"transcript\", \"summary\"}:
        raise HTTPException(status_code=400, detail=\"지원하지 않는 저장 종류입니다.\")
    if len(content.encode(\"utf-8\")) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail=\"텍스트 파일은 최대 20MB까지 저장할 수 있습니다.\")

    stamp = datetime.now().strftime(\"%Y%m%d_%H%M%S\")
    prefix = \"live_summary\" if kind == \"summary\" else \"live_transcript\"
    base = Path(project_root).expanduser().resolve()
    relative = Path(\"recordings\") / f\"{prefix}_{stamp}.txt\"
    target = (base / relative).resolve()
    sequence = 2
    while target.exists():
        relative = Path(\"recordings\") / f\"{prefix}_{stamp}_{sequence}.txt\"
        target = (base / relative).resolve()
        sequence += 1

    try:
        saved_text = content if content.endswith(\"\\n\") else content + \"\\n\"
        await write_file(str(target), saved_text, force=True)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f\"텍스트 파일 저장 실패: {exc}\") from exc

    return {
        \"ok\": True,
        \"kind\": kind,
        \"path\": str(target),
        \"relative_path\": relative.as_posix(),
        \"encoding\": \"utf-8\",
        \"bytes\": len(saved_text.encode(\"utf-8\")),
    }
"""
routes.write_text(route_text, encoding="utf-8")

for old in root.glob("README_V5_*.md"):
    old.unlink()
(root / "README_V5_492_LiveTranscriptTextFileSave.md").write_text(
    """# THEANOVA AgentStudio v5.492 - LiveTranscriptTextFileSave

- 메모 > 실시간 기록에 `파일 저장` 버튼 추가
- 현재 실시간 Transcript 전체를 프로젝트 `recordings/` 폴더의 UTF-8 `.txt` 파일로 저장
- `요약 파일 저장` 버튼은 현재 Transcript를 최신 내용으로 요약한 뒤 `.txt`로 저장
- 저장 성공 후 실제 절대 경로를 실시간 기록 화면에 표시
- 동일 초에 여러 번 저장하면 `_2`, `_3` 방식으로 충돌 없이 저장
- Backend 저장 경로는 기존 프로젝트 허용 경로 검사(`write_file`)를 그대로 사용
""",
    encoding="utf-8",
)
with (root / "README.md").open("a", encoding="utf-8") as fh:
    fh.write(
        "\n\n## v5.492 Live Transcript Text File Save\n"
        "실시간 STT Transcript와 요약정리를 프로젝트 recordings 폴더에 UTF-8 TXT로 저장하고 실제 저장 경로를 UI에 표시합니다.\n"
    )
