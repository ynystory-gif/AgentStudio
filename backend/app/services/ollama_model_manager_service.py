from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.entities import AppSetting

LATEST_RECOMMENDED_MODEL = "qwen3.5:4b"


def _candidate_ollama_executables() -> list[str]:
    candidates: list[str] = []
    for name in ("ollama.exe", "ollama"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidates.append(str(Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe"))
    for drive in ("C", "D", "E", "F", "G"):
        candidates.append(f"{drive}:\\Ollama\\App\\ollama.exe")
    seen: set[str] = set()
    result: list[str] = []
    for raw in candidates:
        value = str(raw or "").strip()
        key = value.lower()
        if value and key not in seen and Path(value).exists():
            seen.add(key)
            result.append(value)
    return result


async def _pc_setting(key: str) -> str:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AppSetting).where(
                    AppSetting.pc_name == pc_name,
                    AppSetting.key == key,
                )
            )
        ).scalar_one_or_none()
        return str(row.value or "").strip() if row else ""


async def _set_pc_setting(key: str, value: str) -> None:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AppSetting).where(
                    AppSetting.pc_name == pc_name,
                    AppSetting.key == key,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            session.add(AppSetting(pc_name=pc_name,key=key,value=value,is_secret=False,updated_at=datetime.utcnow()))
        else:
            row.value=value;row.updated_at=datetime.utcnow()
        await session.commit()


def _free_loopback_port(start: int = 11435) -> int:
    for port in range(start,start+30):
        sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1",port))
            return port
        except OSError:
            pass
        finally:
            sock.close()
    raise RuntimeError("임시 Ollama 다운로드 서버용 포트를 찾지 못했습니다.")


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url,timeout=2) as response:
            return 200 <= int(response.status) < 500
    except Exception:
        return False


async def _wait_ollama(base_url: str,seconds: int=25) -> bool:
    for _ in range(max(1,seconds*2)):
        if await asyncio.to_thread(_http_ok,f"{base_url.rstrip('/')}/api/tags"):
            return True
        await asyncio.sleep(.5)
    return False


def _persist_windows_ollama_models(path: str) -> None:
    if os.name != "nt":
        return
    try:
        subprocess.run(["setx","OLLAMA_MODELS",path],capture_output=True,text=True,timeout=15,check=False)
    except Exception:
        pass


async def _restart_local_ollama(ollama_exe: str, model_root: Path, base_url: str) -> bool:
    parsed=urlparse(base_url)
    host=(parsed.hostname or "127.0.0.1").lower()
    port=int(parsed.port or 11434)
    if host not in {"127.0.0.1","localhost","::1"}:
        return False
    env=os.environ.copy()
    env["OLLAMA_MODELS"]=str(model_root)
    env["OLLAMA_HOST"]=f"127.0.0.1:{port}"
    if os.name=="nt":
        await asyncio.to_thread(subprocess.run,["taskkill","/IM","ollama.exe","/F"],capture_output=True,text=True,timeout=15,check=False)
        flags=0
        for name in ("CREATE_NEW_PROCESS_GROUP","DETACHED_PROCESS","CREATE_NO_WINDOW"):
            flags|=int(getattr(subprocess,name,0))
        await asyncio.to_thread(subprocess.Popen,[ollama_exe,"serve"],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL,creationflags=flags)
    else:
        await asyncio.create_subprocess_exec(ollama_exe,"serve",stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,env=env,start_new_session=True)
    return await _wait_ollama(f"http://127.0.0.1:{port}",30)


async def get_recommended_model_status() -> dict:
    settings=get_settings()
    common_root=(await _pc_setting("COMMON_MODELS_ROOT") or str(settings.common_models_root or "").strip() or str(os.environ.get("COMMON_MODELS_ROOT","") or "").strip())
    current_model=(await _pc_setting("OLLAMA_MODEL") or str(settings.ollama_model or "").strip())
    ollama_exe=next(iter(_candidate_ollama_executables()),"")
    return {"ok":True,"recommended_model":LATEST_RECOMMENDED_MODEL,"current_model":current_model,"common_models_root":common_root,"ollama_executable":ollama_exe,"ready":bool(common_root and ollama_exe),"pc_name":current_pc_name()}


async def download_and_apply_recommended_model() -> dict:
    status=await get_recommended_model_status()
    common_root=str(status.get("common_models_root") or "").strip()
    if not common_root:
        raise ValueError("공통 모델 관리 경로(COMMON_MODELS_ROOT)가 설정되어 있지 않습니다. 시스템 관리에서 공통 모델 경로를 먼저 저장하세요.")
    ollama_exe=str(status.get("ollama_executable") or "").strip()
    if not ollama_exe:
        raise RuntimeError("Ollama 실행 파일을 찾을 수 없습니다. Ollama 설치/실행 경로를 확인하세요.")

    settings=get_settings()
    model_root=Path(common_root).expanduser().resolve()
    model_root.mkdir(parents=True,exist_ok=True)

    # A running Ollama server owns the storage path. Download through a temporary
    # AgentStudio-owned server so qwen3.5:4b is guaranteed to land in the user's
    # COMMON_MODELS_ROOT rather than a hidden default Ollama directory.
    temp_port=_free_loopback_port()
    temp_base=f"http://127.0.0.1:{temp_port}"
    temp_env=os.environ.copy();temp_env["OLLAMA_MODELS"]=str(model_root);temp_env["OLLAMA_HOST"]=f"127.0.0.1:{temp_port}"
    serve=await asyncio.create_subprocess_exec(ollama_exe,"serve",stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,env=temp_env)
    output=""
    try:
        if not await _wait_ollama(temp_base):
            raise RuntimeError("공통 모델 경로용 임시 Ollama 서버를 시작하지 못했습니다.")
        pull_env=temp_env.copy();pull_env["OLLAMA_HOST"]=temp_base
        process=await asyncio.create_subprocess_exec(ollama_exe,"pull",LATEST_RECOMMENDED_MODEL,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,env=pull_env)
        stdout,_=await process.communicate();output=stdout.decode("utf-8",errors="replace") if stdout else ""
        if process.returncode!=0:
            raise RuntimeError(f"{LATEST_RECOMMENDED_MODEL} 다운로드 실패 (ExitCode={process.returncode}): {output[-4000:]}")
    finally:
        if serve.returncode is None:
            serve.terminate()
            try:await asyncio.wait_for(serve.wait(),timeout=5)
            except Exception:
                try:serve.kill()
                except Exception:pass

    await _set_pc_setting("COMMON_MODELS_ROOT",str(model_root))
    await _set_pc_setting("OLLAMA_MODEL",LATEST_RECOMMENDED_MODEL)
    os.environ["COMMON_MODELS_ROOT"]=str(model_root);os.environ["OLLAMA_MODELS"]=str(model_root);os.environ["OLLAMA_MODEL"]=LATEST_RECOMMENDED_MODEL
    _persist_windows_ollama_models(str(model_root))
    get_settings.cache_clear()

    restarted=await _restart_local_ollama(ollama_exe,model_root,str(settings.ollama_base_url or "http://127.0.0.1:11434"))
    if not restarted:
        raise RuntimeError("모델 다운로드는 완료되었지만 현재 Ollama 서버를 공통 모델 경로로 재기동하지 못했습니다. SYSTEM_ADMIN.cmd를 다시 실행하면 다운로드된 qwen3.5:4b를 그대로 사용할 수 있습니다.")

    return {"ok":True,"message":f"{LATEST_RECOMMENDED_MODEL}을 공통 모델 경로에 다운로드하고 Ollama 서버를 같은 경로로 재기동하여 현재 PC 기본 모델로 적용했습니다.","model":LATEST_RECOMMENDED_MODEL,"common_models_root":str(model_root),"pc_name":current_pc_name(),"output_tail":output[-2000:],"ollama_restarted":True}
