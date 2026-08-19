from __future__ import annotations

import asyncio
import os
import platform
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlparse

import httpx
from sqlalchemy import text

from app.core.config import get_settings
import app.core.database as database_core


GITHUB_OWNER = "andreiramani"
GITHUB_REPO = "pgvector_pgsql_windows"
GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
PREFERRED_TAG = "0.8.6_18"

ProgressFn = Callable[[int, str], Awaitable[None]]


async def _progress(cb: ProgressFn | None, value: int, message: str):
    if cb:
        await cb(value, message)


def _normalize_pgroot(value: str | Path | None) -> Path | None:
    if value is None:
        return None

    raw = str(value).strip().strip('"').strip("'")
    if not raw:
        return None

    while "\\\\" in raw:
        raw = raw.replace("\\\\", "\\")

    return Path(raw)


def validate_postgresql18_root(value: str | Path | None) -> dict:
    root = _normalize_pgroot(value)

    if root is None:
        return {
            "ok": False,
            "root": "",
            "psql": "",
            "message": "PostgreSQL 18 설치 경로가 비어 있습니다.",
        }

    exe = root / "bin" / "psql.exe"

    if not exe.exists():
        return {
            "ok": False,
            "root": str(root),
            "psql": str(exe),
            "message": f"psql.exe를 찾지 못했습니다: {exe}",
        }

    try:
        out = subprocess.check_output(
            [str(exe), "--version"],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        ).strip()
    except Exception as e:
        return {
            "ok": False,
            "root": str(root),
            "psql": str(exe),
            "message": f"psql.exe 실행 실패: {e}",
        }

    # Windows PostgreSQL 예:
    # psql (PostgreSQL) 18.4
    match = re.search(
        r"PostgreSQL\)?\s+(\d+)(?:\.\d+)?",
        out,
        re.IGNORECASE,
    )

    if not match:
        return {
            "ok": False,
            "root": str(root),
            "psql": str(exe),
            "version": out,
            "message": f"PostgreSQL 버전을 해석하지 못했습니다: {out}",
        }

    major = int(match.group(1))

    if major != 18:
        return {
            "ok": False,
            "root": str(root),
            "psql": str(exe),
            "version": out,
            "major_version": major,
            "message": f"PostgreSQL 18이 아닙니다: {out}",
        }

    return {
        "ok": True,
        "root": str(root),
        "psql": str(exe),
        "version": out,
        "major_version": major,
        "message": f"PostgreSQL 18 경로 확인 완료: {root} ({out})",
    }


def _registry_roots() -> list[Path]:
    roots: list[Path] = []

    if os.name != "nt":
        return roots

    try:
        import winreg

        for base in (
            r"SOFTWARE\PostgreSQL\Installations",
            r"SOFTWARE\WOW6432Node\PostgreSQL\Installations",
        ):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as parent:
                    count, _, _ = winreg.QueryInfoKey(parent)

                    for i in range(count):
                        child_name = winreg.EnumKey(parent, i)

                        with winreg.OpenKey(parent, child_name) as child:
                            try:
                                value, _ = winreg.QueryValueEx(
                                    child,
                                    "Base Directory",
                                )
                                p = Path(value)
                                if p.exists():
                                    roots.append(p)
                            except OSError:
                                pass
            except OSError:
                pass
    except Exception:
        pass

    return roots


def detect_postgresql18_root(
    explicit_root: str | None = None,
) -> Path | None:
    """
    PostgreSQL 18 경로 탐색 우선순위:
    1. 사용자 입력값
    2. 저장된 POSTGRESQL18_ROOT
    3. PATH의 psql.exe
    4. Windows Registry

    특정 드라이브/폴더는 하드코딩하지 않습니다.
    """
    candidates: list[Path] = []

    if explicit_root:
        p = _normalize_pgroot(explicit_root)
        if p:
            candidates.append(p)

    configured = (get_settings().postgresql18_root or "").strip()
    if configured:
        p = _normalize_pgroot(configured)
        if p:
            candidates.append(p)

    psql = shutil.which("psql")
    if psql:
        candidates.append(Path(psql).resolve().parent.parent)

    candidates.extend(_registry_roots())

    seen = set()
    for candidate in candidates:
        key = str(candidate).strip().rstrip("\\/").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        checked = validate_postgresql18_root(candidate)
        if checked["ok"]:
            return Path(checked["root"])

    return None



def _release_from_json(release: dict) -> dict | None:
    """
    GitHub Release JSON에서 PostgreSQL 18용 Windows pgvector ZIP 자산을 추출합니다.
    draft/prerelease는 제외하고 PostgreSQL 18용 ZIP만 선택합니다.
    """
    if not isinstance(release, dict):
        return None

    if release.get("draft") or release.get("prerelease"):
        return None

    tag = str(release.get("tag_name", "") or "")
    name = str(release.get("name", "") or "")

    # 저장소 release naming 변화에 대비해 tag/name/asset 이름을 모두 검사
    assets = release.get("assets") or []
    if not isinstance(assets, list):
        return None

    zip_assets = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue

        asset_name = str(asset.get("name", "") or "")
        lower_name = asset_name.lower()

        if not lower_name.endswith(".zip"):
            continue

        # PostgreSQL 18 관련 asset 우선
        is_pg18 = (
            "18" in lower_name
            or "_18" in tag.lower()
            or "postgresql 18" in name.lower()
            or "pgsql18" in lower_name
            or "pg18" in lower_name
        )

        if is_pg18:
            zip_assets.append(asset)

    if not zip_assets:
        return None

    # 이름에 18이 명시된 ZIP을 우선
    zip_assets.sort(
        key=lambda a: (
            "18" not in str(a.get("name", "")).lower(),
            str(a.get("name", "")).lower(),
        )
    )

    asset = zip_assets[0]
    download_url = str(asset.get("browser_download_url", "") or "")
    asset_name = str(asset.get("name", "") or "")

    if not download_url or not asset_name:
        return None

    return {
        "tag": tag,
        "release_name": name,
        "asset_name": asset_name,
        "download_url": download_url,
        "size": int(asset.get("size", 0) or 0),
        "html_url": str(release.get("html_url", "") or ""),
        "source": f"{GITHUB_OWNER}/{GITHUB_REPO}",
    }


async def latest_pg18_windows_release() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "THEANOVA-AgentStudio",
    }

    timeout = httpx.Timeout(20.0, connect=8.0)

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        # 1. 검증된 preferred tag 우선
        try:
            res = await client.get(
                f"{GITHUB_API_BASE}/releases/tags/{PREFERRED_TAG}"
            )

            if res.status_code == 200:
                item = _release_from_json(res.json())
                if item:
                    return item
        except Exception:
            pass

        # 2. 목록 fallback
        res = await client.get(
            f"{GITHUB_API_BASE}/releases",
            params={"per_page": 30},
        )
        res.raise_for_status()

        for release in res.json():
            item = _release_from_json(release)
            if item:
                return item

    raise RuntimeError(
        "GitHub에서 PostgreSQL 18용 Windows pgvector ZIP 릴리스를 찾지 못했습니다."
    )


async def _download(
    url: str,
    target: Path,
    progress_cb: ProgressFn | None = None,
):
    headers = {
        "User-Agent": "THEANOVA-AgentStudio",
    }

    timeout = httpx.Timeout(
        180.0,
        connect=15.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        async with client.stream("GET", url) as res:
            res.raise_for_status()

            total = int(res.headers.get("content-length") or 0)
            received = 0

            with target.open("wb") as f:
                async for chunk in res.aiter_bytes(512 * 1024):
                    f.write(chunk)
                    received += len(chunk)

                    if total > 0:
                        pct = 20 + int((received / total) * 25)
                        await _progress(
                            progress_cb,
                            min(pct, 45),
                            f"pgvector 다운로드 중... "
                            f"{received // 1024} KB / {total // 1024} KB",
                        )


def _find_install_files(
    extract_root: Path,
) -> tuple[Path, Path, list[Path]]:
    dll = next(
        iter(extract_root.rglob("vector.dll")),
        None,
    )
    control = next(
        iter(extract_root.rglob("vector.control")),
        None,
    )
    sql_files = sorted(
        extract_root.rglob("vector--*.sql")
    )

    if not dll:
        raise RuntimeError(
            "다운로드 패키지에서 vector.dll을 찾지 못했습니다."
        )

    if not control:
        raise RuntimeError(
            "다운로드 패키지에서 vector.control을 찾지 못했습니다."
        )

    if not sql_files:
        raise RuntimeError(
            "다운로드 패키지에서 vector SQL 파일을 찾지 못했습니다."
        )

    return dll, control, sql_files


def _ps_quote(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _elevated_copy(
    pgroot: Path,
    dll: Path,
    control: Path,
    sql_files: list[Path],
    temp_dir: Path,
):
    """
    관리자 권한으로 PostgreSQL 설치 폴더에 pgvector 파일을 복사합니다.

    중요:
    이전 버전은 관리자 PowerShell이 temp 폴더에 만든 result 파일을
    일반 Backend 프로세스가 다시 읽으면서 PermissionError가 발생할 수 있었습니다.

    v5.10부터는 result 파일을 사용하지 않고:
    1. UAC PowerShell의 exit code
    2. 실제 목적지 파일 존재 여부
    로 설치 성공을 판정합니다.
    """
    script = temp_dir / "install_pgvector_admin.ps1"

    sql_array = ",\n".join(
        _ps_quote(p)
        for p in sql_files
    )

    script.write_text(
        f"""
$ErrorActionPreference = 'Stop'

$pgroot = {_ps_quote(pgroot)}
$dll = {_ps_quote(dll)}
$control = {_ps_quote(control)}

$sqlFiles = @(
{sql_array}
)

try {{
    $libDir = Join-Path $pgroot 'lib'
    $extDir = Join-Path $pgroot 'share\\extension'

    if (-not (Test-Path $libDir)) {{
        throw "PostgreSQL lib folder not found: $libDir"
    }}

    if (-not (Test-Path $extDir)) {{
        throw "PostgreSQL extension folder not found: $extDir"
    }}

    Copy-Item -Force $dll (Join-Path $libDir 'vector.dll')
    Copy-Item -Force $control (Join-Path $extDir 'vector.control')

    foreach ($sql in $sqlFiles) {{
        Copy-Item -Force `
            $sql `
            (Join-Path $extDir ([IO.Path]::GetFileName($sql)))
    }}

    exit 0
}}
catch {{
    Write-Error $_.Exception.Message
    exit 1
}}
""",
        encoding="utf-8-sig",
    )

    argument_list = (
        f'-NoProfile -ExecutionPolicy Bypass '
        f'-File "{script}"'
    )

    escaped = argument_list.replace("'", "''")

    launcher = (
        "$p = Start-Process powershell.exe "
        "-Verb RunAs -Wait -PassThru "
        f"-ArgumentList '{escaped}'; "
        "exit $p.ExitCode"
    )

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            launcher,
        ],
        timeout=240,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Windows 관리자 권한(UAC) 설치가 취소되었거나 "
            "pgvector 파일 복사에 실패했습니다."
        )

    # 관리자 프로세스가 종료된 뒤 실제 목적지 파일을 확인합니다.
    installed_dll = pgroot / "lib" / "vector.dll"
    installed_control = pgroot / "share" / "extension" / "vector.control"

    missing = []

    if not installed_dll.exists():
        missing.append(str(installed_dll))

    if not installed_control.exists():
        missing.append(str(installed_control))

    # SQL 파일도 최소 1개 이상 설치되었는지 확인
    installed_sql = list(
        (pgroot / "share" / "extension").glob("vector--*.sql")
    )

    if not installed_sql:
        missing.append(
            str(pgroot / "share" / "extension" / "vector--*.sql")
        )

    if missing:
        raise RuntimeError(
            "UAC 설치 프로세스는 종료됐지만 pgvector 설치 파일을 "
            "확인하지 못했습니다: "
            + " | ".join(missing)
        )


def _database_target_from_url(database_url: str) -> dict:
    """
    AgentStudio DATABASE_URL에서 DB 접속 대상(host/port/database)을 추출합니다.
    사용자/비밀번호는 관리자 입력값으로 별도 받습니다.
    """
    raw = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(raw)

    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 5432,
        "database": (parsed.path or "/postgres").lstrip("/") or "postgres",
    }


async def _activate_extension_with_admin(
    pgroot: Path,
    admin_user: str,
    admin_password: str,
    database_url: str,
) -> dict:
    """
    PostgreSQL 관리자 계정으로 psql.exe를 실행하여 vector extension을 활성화합니다.

    관리자 비밀번호는 환경변수 PGPASSWORD로 자식 psql 프로세스에만 전달하며
    파일/.env/로그에 저장하지 않습니다.
    """
    if not admin_user.strip():
        return {
            "ok": False,
            "message": "PostgreSQL 관리자 사용자명이 비어 있습니다.",
        }

    if not admin_password:
        return {
            "ok": False,
            "message": "PostgreSQL 관리자 비밀번호가 비어 있습니다.",
        }

    target = _database_target_from_url(database_url)
    psql = pgroot / "bin" / "psql.exe"

    if not psql.exists():
        return {
            "ok": False,
            "message": f"psql.exe를 찾지 못했습니다: {psql}",
        }

    env = os.environ.copy()
    env["PGPASSWORD"] = admin_password
    env["PGCONNECT_TIMEOUT"] = "10"

    sql = (
        "CREATE EXTENSION IF NOT EXISTS vector; "
        "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"
    )

    args = [
        str(psql),
        "-X",
        "-v", "ON_ERROR_STOP=1",
        "-h", target["host"],
        "-p", str(target["port"]),
        "-U", admin_user,
        "-d", target["database"],
        "-c", sql,
    ]

    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            args,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception as e:
        return {
            "ok": False,
            "message": f"관리자 계정으로 CREATE EXTENSION 실행 실패: {e}",
        }

    # 비밀번호는 어느 결과에도 포함하지 않습니다.
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    if proc.returncode != 0:
        detail = stderr or stdout or f"psql 종료 코드 {proc.returncode}"
        return {
            "ok": False,
            "message": f"관리자 DB 활성화 실패: {detail}",
        }

    version_match = re.search(
        r"vector\s*\|\s*([0-9][0-9A-Za-z.\-_]*)",
        stdout,
        re.IGNORECASE,
    )
    version = version_match.group(1) if version_match else ""

    return {
        "ok": True,
        "version": version,
        "message": (
            f"pgvector {version} DB 활성화 완료"
            if version
            else "pgvector DB 활성화 완료"
        ),
        "database": target["database"],
        "host": target["host"],
        "port": target["port"],
        "admin_user": admin_user,
    }


async def _extension_status() -> dict:
    try:
        async with database_core.engine.connect() as conn:
            version = await conn.scalar(
                text(
                    "SELECT extversion FROM pg_extension "
                    "WHERE extname='vector'"
                )
            )
        return {
            "ok": bool(version),
            "version": version or "",
            "message": (
                f"pgvector {version} 활성화됨"
                if version
                else "pgvector extension이 아직 활성화되지 않았습니다."
            ),
        }
    except Exception as e:
        return {
            "ok": False,
            "version": "",
            "message": f"pgvector 상태 확인 실패: {e}",
        }


async def install_pgvector_windows18(
    progress_cb: ProgressFn | None = None,
    postgresql_root: str | None = None,
    admin_user: str = "",
    admin_password: str = "",
    database_url: str = "",
):
    if (
        os.name != "nt"
        or platform.system().lower() != "windows"
    ):
        raise RuntimeError(
            "Windows 전용 설치 기능입니다."
        )

    await _progress(
        progress_cb,
        5,
        "PostgreSQL 18 설치 경로를 확인합니다.",
    )

    pgroot = detect_postgresql18_root(
        postgresql_root
    )

    if not pgroot:
        checked = validate_postgresql18_root(
            postgresql_root
            or get_settings().postgresql18_root
        )

        raise RuntimeError(
            checked.get("message")
            or (
                "PostgreSQL 18 설치 경로가 저장되지 않았습니다. "
                "시스템 관리에서 경로를 입력하고 저장하세요."
            )
        )

    await _progress(
        progress_cb,
        10,
        f"PostgreSQL 18 경로 확인: {pgroot}",
    )

    await _progress(
        progress_cb,
        15,
        "PostgreSQL 18용 pgvector 릴리스를 확인합니다.",
    )

    release = await latest_pg18_windows_release()

    await _progress(
        progress_cb,
        18,
        f"설치 패키지 확인: "
        f"{release['release_name']} / {release['asset_name']}",
    )

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix="agentstudio_pgvector_"
        )
    )

    try:
        archive = temp_dir / release["asset_name"]

        await _progress(
            progress_cb,
            20,
            "pgvector ZIP을 다운로드합니다.",
        )

        await _download(
            release["download_url"],
            archive,
            progress_cb,
        )

        await _progress(
            progress_cb,
            48,
            "다운로드 ZIP을 검증합니다.",
        )

        if (
            not archive.exists()
            or archive.stat().st_size == 0
        ):
            raise RuntimeError(
                "다운로드된 pgvector ZIP 파일이 비어 있습니다."
            )

        extract_root = temp_dir / "extracted"
        extract_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            with zipfile.ZipFile(
                archive,
                "r",
            ) as z:
                bad = z.testzip()

                if bad:
                    raise RuntimeError(
                        f"ZIP 손상 파일: {bad}"
                    )

                z.extractall(extract_root)

        except zipfile.BadZipFile as e:
            raise RuntimeError(
                f"다운로드 파일이 정상 ZIP이 아닙니다: {e}"
            )

        dll, control, sql_files = (
            _find_install_files(
                extract_root
            )
        )

        await _progress(
            progress_cb,
            60,
            (
                "설치 파일 검증 완료. "
                "Windows 관리자 권한(UAC)을 기다립니다."
            ),
        )

        await asyncio.to_thread(
            _elevated_copy,
            pgroot,
            dll,
            control,
            sql_files,
            temp_dir,
        )

        await _progress(
            progress_cb,
            82,
            "PostgreSQL 폴더에 pgvector 파일 설치 완료",
        )

        await _progress(
            progress_cb,
            90,
            "PostgreSQL 관리자 계정으로 CREATE EXTENSION vector 실행 중",
        )

        if not database_url:
            database_url = get_settings().database_url

        activation = await _activate_extension_with_admin(
            pgroot=pgroot,
            admin_user=admin_user,
            admin_password=admin_password,
            database_url=database_url,
        )

        if not activation["ok"]:
            raise RuntimeError(
                "pgvector 바이너리 설치는 완료되었지만 DB 활성화에 실패했습니다: "
                + activation["message"]
            )

        await _progress(
            progress_cb,
            98,
            activation["message"],
        )

        return {
            "ok": True,
            "message": activation["message"],
            "postgresql_root": str(pgroot),
            "release": release,
            "extension": activation,
            "note": (
                "Windows 사전 빌드 패키지는 "
                "andreiramani/pgvector_pgsql_windows "
                "커뮤니티 릴리스를 사용합니다."
            ),
        }

    finally:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )
