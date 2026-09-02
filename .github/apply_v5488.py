from pathlib import Path

app = Path('frontend/src/App.jsx')
text = app.read_text(encoding='utf-8')
if "AGENTSTUDIO_FRONTEND_VERSION='5.488'" not in text:
    text = text.replace("const AGENTSTUDIO_FRONTEND_VERSION='5.487'", "const AGENTSTUDIO_FRONTEND_VERSION='5.488'", 1)
func = text.index('const executeNotebookPythonCode=async')
start = text.index('      let result=null', func)
end = text.index("      const stdout=String(result?.stdout||'')", start)
if 'packageManagementMode' not in text[start:end]:
    new_block = r'''      let result=null
      const pythonExecutionPayload={
        root:workspaceRoot,
        relative_path:normalizedPath,
        code:executableCode,
        mode:mode==='full'?'full':'selection',
        session_id:runtimeSessionId,
        capture_last_expression:true,
        notebook_mode:true,
        cell_index:Number(cellIndex),
      }
      // v5.488: package-management magics can replace packages used by the
      // persistent Notebook worker while they run. Route these cells through
      // the normal request/response endpoint instead of the NDJSON rich-output
      // stream so a successful pip subprocess cannot leave the browser waiting
      // for a stream-final packet that never arrives.
      const packageManagementMode=String(executableCode||'')
        .split(/\r?\n/)
        .some(rawLine=>{
          const line=String(rawLine||'').trim()
          if(!line||line.startsWith('#')) return false
          return /^%pip(?:\s|$)/i.test(line)
            || /^!\s*(?:pip|pip3)(?:\.exe)?(?:\s|$)/i.test(line)
            || /^!\s*(?:python|python3|py)(?:\.exe)?\s+-m\s+pip(?:\s|$)/i.test(line)
        })

      if(packageManagementMode){
        term.write('\x1b[36m[패키지 설치 중] Notebook 스트리밍 보호 모드로 실행합니다. 설치가 끝날 때까지 기다려 주세요.\x1b[0m\r\n')
        result=await api('/python/execute',{
          method:'POST',
          body:JSON.stringify(pythonExecutionPayload)
        })
        if(result?.ok){
          term.write('\x1b[32m[패키지 설치 완료] 다음 셀부터 갱신된 프로젝트 환경을 사용합니다.\x1b[0m\r\n')
        }
      }else{
        const streamResponse=await apiFetch('/python/execute/stream',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify(pythonExecutionPayload)
        })
        if(!streamResponse.ok){
          const detail=await streamResponse.text()
          throw new Error(`Notebook 스트리밍 실행 실패 (${streamResponse.status}): ${detail||streamResponse.statusText}`)
        }
        if(!streamResponse.body){
          result=await api('/python/execute',{
            method:'POST',
            body:JSON.stringify(pythonExecutionPayload)
          })
        }else{
          const reader=streamResponse.body.getReader()
          const decoder=new TextDecoder('utf-8')
          let buffer=''
          const consumePacket=(packet)=>{
            if(!packet||typeof packet!=='object') return
            if(packet.type==='event'){
              try{ onOutputEvent?.(packet.event||{}) }catch{}
            }else if(packet.type==='result'){
              result=packet.result||null
            }
          }
          while(true){
            const {value,done}=await reader.read()
            buffer+=decoder.decode(value||new Uint8Array(),{stream:!done})
            let newlineIndex=buffer.indexOf('\n')
            while(newlineIndex>=0){
              const line=buffer.slice(0,newlineIndex).trim()
              buffer=buffer.slice(newlineIndex+1)
              if(line){
                try{ consumePacket(JSON.parse(line)) }catch{}
              }
              newlineIndex=buffer.indexOf('\n')
            }
            if(done) break
          }
          const tail=buffer.trim()
          if(tail){
            try{ consumePacket(JSON.parse(tail)) }catch{}
          }
        }
        if(!result){
          // Do not automatically re-run arbitrary Python here: a second run can
          // duplicate DB INSERTs, file writes, API calls, or other side effects.
          // Reset only the persistent worker so the next manual cell execution
          // starts from a clean session and report the recovery accurately.
          let recovered=false
          try{
            const recovery=await api('/python/reset',{
              method:'POST',
              body:JSON.stringify({root:workspaceRoot,session_id:runtimeSessionId})
            })
            recovered=!!recovery?.ok
          }catch{}
          result={
            ok:false,
            stdout:'',
            stderr:'',
            error_type:'NotebookStreamingRecovered',
            error_message:recovered
              ? 'Notebook 스트림의 최종 결과가 누락되어 Python 세션을 자동 복구했습니다. 중복 실행 방지를 위해 해당 셀은 자동 재실행하지 않았습니다. 셀을 다시 실행해 주세요.'
              : 'Notebook 스트림의 최종 결과가 누락되었습니다. 자동 재실행은 부작용 방지를 위해 수행하지 않았습니다. 셀을 다시 실행해 주세요.',
            traceback:'',
            session_recovered:recovered,
          }
        }
      }

'''
    text = text[:start] + new_block + text[end:]
app.write_text(text, encoding='utf-8')

service = Path('backend/app/services/python_execution_service.py')
text = service.read_text(encoding='utf-8')
if '"error_type": "PythonWorkerExited"' not in text:
    old = '''                    raise RuntimeError(
                        "Python 실행 세션이 프로토콜 응답 전에 종료되었습니다."
                        + (
                            f"\\n자식 프로세스 출력:\\n{''.join(native_output_parts)[-4000:]}"
                            if native_output_parts
                            else ""
                        )
                    )'''
    if text.count(old) != 2:
        raise SystemExit(f'expected 2 worker exit blocks, found {text.count(old)}')
    execute_replacement = '''                    # v5.488: preserve native output and discard a dead worker.
                    with self._sessions_lock:
                        self._sessions.pop(session.key, None)
                    response = {
                        "ok": False,
                        "stdout": "".join(native_output_parts),
                        "stderr": "",
                        "error_type": "PythonWorkerExited",
                        "error_message": "Python 실행 세션이 최종 응답 전에 종료되었습니다. 다음 실행은 새 세션에서 자동 시작됩니다.",
                        "traceback": "",
                        "session_recovered": True,
                    }
                    response_json = ""
                    break'''
    stream_replacement = '''                    # v5.488: keep NDJSON final-result semantics when the worker exits.
                    with self._sessions_lock:
                        self._sessions.pop(session.key, None)
                    response = {
                        "ok": False,
                        "stdout": "".join(native_output_parts),
                        "stderr": "",
                        "error_type": "PythonWorkerExited",
                        "error_message": "Python 실행 세션이 최종 응답 전에 종료되어 세션을 자동 복구했습니다. 다음 실행은 새 Python 세션에서 시작됩니다.",
                        "traceback": "",
                        "session_recovered": True,
                    }
                    break'''
    text = text.replace(old, execute_replacement, 1)
    text = text.replace(old, stream_replacement, 1)
    text = text.replace(
        '        native_output = "".join(native_output_parts)\n        if native_output:\n            # subprocess.run(..., capture_output=False) 같은 native 출력도 실행 결과에\n            # 포함해 사용자가 터미널에서 볼 수 있게 한다.\n            response["stdout"] = native_output + str(response.get("stdout") or "")',
        '        native_output = "".join(native_output_parts)\n        if native_output and not bool(response.get("session_recovered")):\n            # subprocess.run(..., capture_output=False) 같은 native 출력도 실행 결과에\n            # 포함해 사용자가 터미널에서 볼 수 있게 한다.\n            response["stdout"] = native_output + str(response.get("stdout") or "")', 1)
    text = text.replace(
        '        native_output = "".join(native_output_parts)\n        if native_output:\n            response["stdout"] = native_output + str(response.get("stdout") or "")',
        '        native_output = "".join(native_output_parts)\n        if native_output and not bool(response.get("session_recovered")):\n            response["stdout"] = native_output + str(response.get("stdout") or "")', 1)
service.write_text(text, encoding='utf-8')

main = Path('backend/app/main.py')
text = main.read_text(encoding='utf-8')
text = text.replace('version="5.487"', 'version="5.488"', 1)
main.write_text(text, encoding='utf-8')

routes = Path('backend/app/api/routes.py')
text = routes.read_text(encoding='utf-8')
text = text.replace('"version": "5.487"', '"version": "5.488"', 1)
if 'NotebookStreamingRecovery+PackageInstallProtectedExecution' not in text:
    text = text.replace('TranscriptCollectionRefineCompleteStatus"}', 'TranscriptCollectionRefineCompleteStatus+NotebookStreamingRecovery+PackageInstallProtectedExecution"}', 1)
routes.write_text(text, encoding='utf-8')

readme = Path('README.md')
text = readme.read_text(encoding='utf-8')
entry = '''## v5.488

### v5.488
- Notebook의 `%pip`, `!pip`, `!python -m pip` 패키지 설치 셀은 Rich Output NDJSON 스트림 대신 보호된 일반 실행 경로를 사용합니다.
- 패키지 설치 중/완료 상태를 표시하고, Worker 비정상 종료 시 실제 native 출력을 보존한 `PythonWorkerExited` 결과와 세션 자동 복구를 제공합니다.
- 일반 Notebook 스트림 최종 결과 누락 시 세션을 자동 Reset합니다. DB INSERT·파일 쓰기·API 호출 중복 방지를 위해 임의 셀 자체는 자동 재실행하지 않습니다.
- v5.487 이미지 Preview와 Notebook Rich Image Output 기능을 그대로 유지합니다.

'''
if not text.startswith('## v5.488'):
    readme.write_text(entry + text, encoding='utf-8')

Path('README_V5_488_NotebookStreamingRecovery.md').write_text('''# THEANOVA AgentStudio v5.488 - NotebookStreamingRecovery

- `%pip`, `!pip`, `!python -m pip` 셀 비스트리밍 보호 실행
- 패키지 설치 진행/완료 상태 표시
- Worker 비정상 종료 시 실제 native 출력 보존 및 세션 자동 복구
- NDJSON 최종 result 누락 시 세션 reset, 임의 셀 자동 재실행 방지
- v5.487 이미지 Preview / Notebook Rich Image Output 유지
''', encoding='utf-8')

Path('backend/validate_v5488_notebook_streaming_recovery_contract.py').write_text('''from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/"frontend/src/App.jsx").read_text(encoding="utf-8")
service=(ROOT/"backend/app/services/python_execution_service.py").read_text(encoding="utf-8")
main=(ROOT/"backend/app/main.py").read_text(encoding="utf-8")
routes=(ROOT/"backend/app/api/routes.py").read_text(encoding="utf-8")
checks={
    "frontend":"AGENTSTUDIO_FRONTEND_VERSION='5.488'" in app,
    "backend":'version="5.488"' in main,
    "health":'"version": "5.488"' in routes,
    "pip":"packageManagementMode" in app and "[패키지 설치 중]" in app,
    "recovery":"NotebookStreamingRecovered" in app and "'/python/reset'" in app,
    "safe":"중복 실행 방지를 위해 해당 셀은 자동 재실행하지 않았습니다" in app,
    "worker":service.count('"error_type": "PythonWorkerExited"')>=2,
}
failed=[k for k,v in checks.items() if not v]
for k,v in checks.items(): print(f"[{'OK' if v else 'FAIL'}] {k}")
if failed: raise SystemExit(', '.join(failed))
print('v5.488 contract: PASS')
''', encoding='utf-8')