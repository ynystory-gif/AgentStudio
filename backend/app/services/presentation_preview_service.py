from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_PRESENTATION_EXTENSIONS = {".ppt", ".pptx"}


class PresentationPreviewError(RuntimeError):
    def __init__(self, message: str, *, attempts: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts or []


@dataclass(frozen=True)
class PresentationPreviewResult:
    source_path: str
    source_relative_path: str
    source_sha256: str
    source_mtime_ns: int
    source_size: int
    preview_path: str
    preview_size: int
    converter: str
    cache_hit: bool
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_LOCKS_GUARD = threading.Lock()
_PREVIEW_LOCKS: dict[str, threading.Lock] = {}


def _preview_lock(key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _PREVIEW_LOCKS.setdefault(key, threading.Lock())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_pdf(path: Path) -> bool:
    if not path.exists() or not path.is_file() or path.stat().st_size < 5:
        return False
    try:
        with path.open("rb") as stream:
            return stream.read(5) == b"%PDF-"
    except OSError:
        return False


def _metadata_path(preview_dir: Path) -> Path:
    return preview_dir / "metadata.json"


def _load_metadata(preview_dir: Path) -> dict[str, Any]:
    path = _metadata_path(preview_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_metadata(preview_dir: Path, payload: dict[str, Any]) -> None:
    preview_dir.mkdir(parents=True, exist_ok=True)
    path = _metadata_path(preview_dir)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _cache_directory(project_root: Path, source_path: Path) -> Path:
    relative = source_path.relative_to(project_root).as_posix()
    key = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:24]
    return project_root / ".agentstudio" / "preview" / "presentations" / key


def _powershell_executable() -> str | None:
    candidates: list[str | None] = []
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if system_root:
        candidates.append(str(Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"))
    candidates.extend([
        shutil.which("powershell.exe"),
        shutil.which("powershell"),
    ])
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


def _ps_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _powerpoint_registration_info() -> dict[str, Any]:
    """Return non-secret PowerPoint COM registration diagnostics on Windows."""
    if os.name != "nt":
        return {"registered": False, "executable": "", "reason": "Windows가 아닙니다."}
    try:
        import winreg  # type: ignore

        clsid = ""
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"PowerPoint.Application\\CLSID") as key:
            clsid = str(winreg.QueryValueEx(key, None)[0] or "").strip()
        executable = ""
        if clsid:
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\\{clsid}\\LocalServer32") as key:
                    command = str(winreg.QueryValueEx(key, None)[0] or "").strip()
                if command:
                    # Office registration normally looks like: "C:\\...\\POWERPNT.EXE" /Automation
                    if command.startswith('"'):
                        executable = command.split('"', 2)[1]
                    else:
                        executable = command.split(" ", 1)[0]
            except OSError:
                pass
        return {
            "registered": bool(clsid),
            "clsid": clsid,
            "executable": executable,
            "executable_exists": bool(executable and Path(executable).exists()),
            "reason": "" if clsid else "PowerPoint.Application COM 등록을 찾지 못했습니다.",
        }
    except OSError:
        return {
            "registered": False,
            "executable": "",
            "reason": "PowerPoint.Application COM 등록을 찾지 못했습니다.",
        }
    except Exception as exc:
        return {
            "registered": False,
            "executable": "",
            "reason": f"PowerPoint 설치 확인 중 오류: {type(exc).__name__}",
        }


def _cscript_executable() -> str | None:
    if os.name != "nt":
        return None
    candidates: list[str | None] = []
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if system_root:
        candidates.append(str(Path(system_root) / "System32" / "cscript.exe"))
    candidates.extend([shutil.which("cscript.exe"), shutil.which("cscript")])
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


def _vbs_literal(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _convert_with_powerpoint_vbscript(source: Path, output_pdf: Path) -> dict[str, Any]:
    """Use Windows Script Host late-bound COM for PowerPoint PDF export.

    PowerShell can mis-bind Office methods with many optional arguments and treat
    ExportAsFixedFormat like a property. VBScript talks to IDispatch directly and
    avoids that binder problem on PowerPoint desktop installations.
    """
    cscript = _cscript_executable()
    if not cscript:
        return {
            "ok": False,
            "converter": "Microsoft PowerPoint",
            "reason": "Windows Script Host(cscript.exe)를 찾을 수 없습니다.",
            "unavailable": True,
            "method": "VBScript COM",
        }

    script_path = output_pdf.parent / "agentstudio_powerpoint_export.vbs"
    script_lines = [
        "Option Explicit",
        "On Error Resume Next",
        "Dim ppt, pres, fso, inputPath, outputPath, exportErr, exportDesc",
        f"inputPath = {_vbs_literal(str(source))}",
        f"outputPath = {_vbs_literal(str(output_pdf))}",
        'Set fso = CreateObject("Scripting.FileSystemObject")',
        'If fso.FileExists(outputPath) Then fso.DeleteFile outputPath, True',
        "Err.Clear",
        "",
        'WScript.Echo "STEP=COM_CREATE_VBS"',
        'Set ppt = CreateObject("PowerPoint.Application")',
        "If Err.Number <> 0 Then",
        '    WScript.Echo "ERROR_STEP=COM_CREATE_VBS"',
        '    WScript.Echo "ERROR_NUMBER=" & Err.Number',
        '    WScript.Echo "ERROR_MESSAGE=" & Err.Description',
        "    WScript.Quit 17",
        "End If",
        "Err.Clear",
        "ppt.DisplayAlerts = 1",
        "Err.Clear",
        "ppt.AutomationSecurity = 3",
        "Err.Clear",
        "",
        'WScript.Echo "STEP=OPEN_WRITABLE"',
        "Set pres = ppt.Presentations.Open(inputPath, 0, 0, 0)",
        "If Err.Number <> 0 Then",
        '    WScript.Echo "ERROR_STEP=OPEN_WRITABLE"',
        '    WScript.Echo "ERROR_NUMBER=" & Err.Number',
        '    WScript.Echo "ERROR_MESSAGE=" & Err.Description',
        "    ppt.Quit",
        "    WScript.Quit 17",
        "End If",
        "Err.Clear",
        "",
        'WScript.Echo "STEP=EXPORT_AS_FIXED_FORMAT_VBS"',
        "pres.ExportAsFixedFormat outputPath, 2",
        "If Err.Number <> 0 Then",
        "    exportErr = Err.Number",
        "    exportDesc = Err.Description",
        '    WScript.Echo "EXPORT_AS_FIXED_FORMAT_FAILED=" & exportDesc',
        "    Err.Clear",
        '    WScript.Echo "STEP=SAVE_AS_PDF_VBS"',
        '    If fso.FileExists(outputPath) Then fso.DeleteFile outputPath, True',
        "    Err.Clear",
        "    pres.SaveAs outputPath, 32",
        "    If Err.Number <> 0 Then",
        '        WScript.Echo "ERROR_STEP=SAVE_AS_PDF_VBS"',
        '        WScript.Echo "ERROR_NUMBER=" & Err.Number',
        '        WScript.Echo "ERROR_MESSAGE=" & Err.Description',
        "        pres.Close",
        "        ppt.Quit",
        "        WScript.Quit 17",
        "    End If",
        '    WScript.Echo "METHOD=SaveAsPDF-VBScript"',
        "Else",
        '    WScript.Echo "METHOD=ExportAsFixedFormat-VBScript"',
        "End If",
        "Err.Clear",
        "pres.Close",
        "ppt.Quit",
        "Set pres = Nothing",
        "Set ppt = Nothing",
        "Set fso = Nothing",
        "WScript.Quit 0",
        "",
    ]
    try:
        script_path.write_text("\r\n".join(script_lines), encoding="utf-16")
        completed = subprocess.run(
            [cscript, "//Nologo", str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="mbcs",
            errors="replace",
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "converter": "Microsoft PowerPoint",
            "reason": "PowerPoint VBScript COM PDF 변환이 120초 제한시간을 초과했습니다.",
            "method": "VBScript COM",
        }
    except Exception as exc:
        return {
            "ok": False,
            "converter": "Microsoft PowerPoint",
            "reason": f"PowerPoint VBScript COM 실행 실패: {type(exc).__name__}: {exc}",
            "method": "VBScript COM",
        }
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except OSError:
            pass

    output = (completed.stdout or "").strip()
    if completed.returncode == 0 and _is_pdf(output_pdf):
        method = "VBScript COM"
        for line in output.splitlines():
            if line.startswith("METHOD="):
                method = line.split("=", 1)[1].strip() or method
        return {
            "ok": True,
            "converter": "Microsoft PowerPoint",
            "method": method,
            "returncode": completed.returncode,
            "output": output[-1500:],
        }

    reason = "PowerPoint VBScript COM으로 PDF를 생성하지 못했습니다."
    error_step = ""
    error_message = ""
    for line in output.splitlines():
        if line.startswith("ERROR_STEP="):
            error_step = line.split("=", 1)[1].strip()
        elif line.startswith("ERROR_MESSAGE="):
            error_message = line.split("=", 1)[1].strip()
    if error_step or error_message:
        reason += f" {error_step}: {error_message}".rstrip()
    return {
        "ok": False,
        "converter": "Microsoft PowerPoint",
        "reason": reason,
        "method": "VBScript COM",
        "output": output[-3000:],
        "returncode": completed.returncode,
    }


def _convert_with_powerpoint_powershell(source: Path, output_pdf: Path) -> dict[str, Any]:
    """PowerShell fallback using reflection instead of direct COM method syntax."""
    powershell = _powershell_executable()
    if not powershell:
        return {
            "ok": False,
            "converter": "Microsoft PowerPoint",
            "reason": "Windows PowerShell을 찾을 수 없습니다.",
            "unavailable": True,
            "method": "PowerShell COM reflection",
        }

    script = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$inputPath = {_ps_literal(str(source))}
$outputPath = {_ps_literal(str(output_pdf))}
$ppt = $null
$presentation = $null
$method = ''
$invoke = [System.Reflection.BindingFlags]::InvokeMethod
try {{
    Write-Output 'STEP=COM_CREATE_PS'
    $pptType = [type]::GetTypeFromProgID('PowerPoint.Application')
    if ($null -eq $pptType) {{ throw 'PowerPoint.Application ProgID를 찾을 수 없습니다.' }}
    $ppt = [Activator]::CreateInstance($pptType)
    try {{ $ppt.DisplayAlerts = 1 }} catch {{}}
    try {{ $ppt.AutomationSecurity = 3 }} catch {{}}

    Write-Output 'STEP=OPEN_WRITABLE_PS'
    $presentation = $ppt.Presentations.Open($inputPath, 0, 0, 0)

    Write-Output 'STEP=EXPORT_AS_FIXED_FORMAT_REFLECTION'
    try {{
        $args = [object[]]@($outputPath, [int]2)
        $presentation.GetType().InvokeMember('ExportAsFixedFormat', $invoke, $null, $presentation, $args) | Out-Null
        $method = 'ExportAsFixedFormat-Reflection'
    }} catch {{
        Write-Output ('EXPORT_AS_FIXED_FORMAT_FAILED=' + $_.Exception.Message)
        if (Test-Path -LiteralPath $outputPath) {{ Remove-Item -LiteralPath $outputPath -Force -ErrorAction SilentlyContinue }}
        Write-Output 'STEP=SAVE_AS_PDF_REFLECTION'
        $args = [object[]]@($outputPath, [int]32)
        $presentation.GetType().InvokeMember('SaveAs', $invoke, $null, $presentation, $args) | Out-Null
        $method = 'SaveAsPDF-Reflection'
    }}

    for ($i = 0; $i -lt 50; $i++) {{
        if ((Test-Path -LiteralPath $outputPath) -and ((Get-Item -LiteralPath $outputPath).Length -gt 4)) {{ break }}
        Start-Sleep -Milliseconds 100
    }}
    Write-Output ('METHOD=' + $method)
}} catch {{
    Write-Output ('ERROR_TYPE=' + $_.Exception.GetType().FullName)
    Write-Output ('ERROR_MESSAGE=' + $_.Exception.Message)
    if ($_.Exception.HResult) {{ Write-Output ('HRESULT=0x' + ('{{0:X8}}' -f ($_.Exception.HResult -band 0xffffffff))) }}
    exit 17
}} finally {{
    if ($presentation -ne $null) {{
        try {{ $presentation.Close() }} catch {{}}
        try {{ [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($presentation) | Out-Null }} catch {{}}
    }}
    if ($ppt -ne $null) {{
        try {{ $ppt.Quit() }} catch {{}}
        try {{ [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($ppt) | Out-Null }} catch {{}}
    }}
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}}
""".strip()

    try:
        completed = subprocess.run(
            [
                powershell,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "converter": "Microsoft PowerPoint",
            "reason": "PowerPoint PowerShell COM 변환이 120초 제한시간을 초과했습니다.",
            "method": "PowerShell COM reflection",
        }
    except Exception as exc:
        return {
            "ok": False,
            "converter": "Microsoft PowerPoint",
            "reason": f"PowerPoint PowerShell COM 실행 실패: {type(exc).__name__}: {exc}",
            "method": "PowerShell COM reflection",
        }

    output = (completed.stdout or "").strip()
    if completed.returncode == 0 and _is_pdf(output_pdf):
        method = "PowerShell COM reflection"
        for line in output.splitlines():
            if line.startswith("METHOD="):
                method = line.split("=", 1)[1].strip() or method
        return {
            "ok": True,
            "converter": "Microsoft PowerPoint",
            "method": method,
            "returncode": completed.returncode,
            "output": output[-1500:],
        }

    reason = "PowerPoint PowerShell COM으로 PDF를 생성하지 못했습니다."
    error_message = ""
    for line in reversed(output.splitlines()):
        if line.startswith("ERROR_MESSAGE="):
            error_message = line.split("=", 1)[1].strip()
            break
    if error_message:
        reason += f" {error_message}"
    return {
        "ok": False,
        "converter": "Microsoft PowerPoint",
        "reason": reason,
        "method": "PowerShell COM reflection",
        "output": output[-3000:],
        "returncode": completed.returncode,
    }


def _convert_with_powerpoint(source: Path, output_pdf: Path) -> dict[str, Any]:
    if os.name != "nt":
        return {
            "ok": False,
            "converter": "Microsoft PowerPoint",
            "reason": "PowerPoint COM 변환은 Windows에서만 사용할 수 있습니다.",
            "unavailable": True,
        }

    registration = _powerpoint_registration_info()
    if not registration.get("registered"):
        return {
            "ok": False,
            "converter": "Microsoft PowerPoint",
            "reason": str(registration.get("reason") or "PowerPoint COM 등록을 찾지 못했습니다."),
            "unavailable": True,
            "powerpoint_executable": str(registration.get("executable") or ""),
        }

    staged_source = output_pdf.parent / f"agentstudio_source{source.suffix.lower()}"
    try:
        shutil.copy2(source, staged_source)
    except Exception as exc:
        return {
            "ok": False,
            "converter": "Microsoft PowerPoint",
            "reason": f"PowerPoint용 임시 원본 복사에 실패했습니다: {type(exc).__name__}: {exc}",
            "powerpoint_executable": str(registration.get("executable") or ""),
        }

    attempts: list[dict[str, Any]] = []
    vb_result = _convert_with_powerpoint_vbscript(staged_source, output_pdf)
    attempts.append(vb_result)
    if vb_result.get("ok"):
        vb_result["powerpoint_executable"] = str(registration.get("executable") or "")
        return vb_result

    try:
        output_pdf.unlink(missing_ok=True)
    except OSError:
        pass

    ps_result = _convert_with_powerpoint_powershell(staged_source, output_pdf)
    attempts.append(ps_result)
    if ps_result.get("ok"):
        ps_result["powerpoint_executable"] = str(registration.get("executable") or "")
        return ps_result

    reason = "PowerPoint COM으로 PDF를 생성하지 못했습니다."
    pieces = []
    outputs = []
    for item in attempts:
        method = str(item.get("method") or "COM")
        item_reason = str(item.get("reason") or "실패")
        pieces.append(f"{method}: {item_reason}")
        if item.get("output"):
            outputs.append(f"[{method}]\n{item.get('output')}")
    if pieces:
        reason += " " + " / ".join(pieces)
    return {
        "ok": False,
        "converter": "Microsoft PowerPoint",
        "reason": reason,
        "output": "\n\n".join(outputs)[-5000:],
        "returncode": ps_result.get("returncode"),
        "powerpoint_executable": str(registration.get("executable") or ""),
        "attempts": attempts,
    }

def _libreoffice_executable() -> str | None:
    candidates: list[str | None] = [
        os.environ.get("AGENTSTUDIO_LIBREOFFICE_PATH"),
        shutil.which("soffice"),
        shutil.which("libreoffice"),
    ]
    if os.name == "nt":
        program_files = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        for root in program_files:
            if root:
                base = Path(root)
                candidates.extend(
                    [
                        str(base / "LibreOffice" / "program" / "soffice.exe"),
                        str(base / "LibreOffice" / "program" / "soffice.com"),
                        str(base / "Programs" / "LibreOffice" / "program" / "soffice.exe"),
                        str(base / "Programs" / "LibreOffice" / "program" / "soffice.com"),
                    ]
                )
        try:
            import winreg  # type: ignore

            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for key_name in (
                    r"Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\soffice.exe",
                    r"Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\soffice.com",
                ):
                    try:
                        with winreg.OpenKey(hive, key_name) as key:
                            candidates.append(str(winreg.QueryValueEx(key, None)[0] or ""))
                    except OSError:
                        pass
        except Exception:
            pass
    for candidate in candidates:
        if candidate:
            path = Path(str(candidate).strip('"'))
            if path.exists() and path.is_file():
                return str(path)
    return None


def _convert_with_libreoffice(source: Path, output_pdf: Path, temp_root: Path) -> dict[str, Any]:
    executable = _libreoffice_executable()
    if not executable:
        return {
            "ok": False,
            "converter": "LibreOffice",
            "reason": "LibreOffice(soffice)를 찾을 수 없습니다.",
            "unavailable": True,
        }

    out_dir = temp_root / "libreoffice-output"
    profile_dir = temp_root / "libreoffice-profile"
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    # PowerPoint와 동일하게 입력을 ASCII 임시 경로로 복사해 한글/긴 경로 문제를 회피한다.
    staged_source = temp_root / f"agentstudio_source{source.suffix.lower()}"
    try:
        shutil.copy2(source, staged_source)
    except Exception:
        staged_source = source

    profile_uri = profile_dir.resolve().as_uri()
    command = [
        executable,
        "--headless",
        "--nologo",
        "--nodefault",
        "--nofirststartwizard",
        "--nolockcheck",
        f"-env:UserInstallation={profile_uri}",
        "--convert-to",
        "pdf:impress_pdf_Export",
        "--outdir",
        str(out_dir),
        str(staged_source),
    ]

    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "converter": "LibreOffice",
            "reason": "LibreOffice PDF 변환이 120초 제한시간을 초과했습니다.",
            "executable": executable,
        }
    except Exception as exc:
        return {
            "ok": False,
            "converter": "LibreOffice",
            "reason": f"LibreOffice 변환 실행 실패: {type(exc).__name__}: {exc}",
            "executable": executable,
        }

    candidates = [out_dir / f"{staged_source.stem}.pdf"]
    candidates.extend(sorted(out_dir.glob("*.pdf")))
    generated = next((item for item in candidates if _is_pdf(item)), None)

    if completed.returncode != 0 or generated is None:
        output = (completed.stdout or "").strip()
        return {
            "ok": False,
            "converter": "LibreOffice",
            "reason": "LibreOffice로 PDF를 생성하지 못했습니다.",
            "output": output[-3000:],
            "returncode": completed.returncode,
            "executable": executable,
        }

    shutil.copy2(generated, output_pdf)
    if not _is_pdf(output_pdf):
        return {
            "ok": False,
            "converter": "LibreOffice",
            "reason": "LibreOffice 결과 PDF 검증에 실패했습니다.",
            "executable": executable,
        }

    return {
        "ok": True,
        "converter": "LibreOffice",
        "returncode": completed.returncode,
        "executable": executable,
        "output": (completed.stdout or "").strip()[-1000:],
    }

def prepare_presentation_preview(
    project_root: str | Path,
    source_path: str | Path,
    *,
    force: bool = False,
) -> PresentationPreviewResult:
    root = Path(project_root).expanduser().resolve()
    source = Path(source_path).expanduser().resolve()

    try:
        source.relative_to(root)
    except ValueError as exc:
        raise PresentationPreviewError("프로젝트 밖의 PowerPoint 파일은 미리보기할 수 없습니다.") from exc

    if source.suffix.casefold() not in SUPPORTED_PRESENTATION_EXTENSIONS:
        raise PresentationPreviewError("PPT/PPTX 파일만 PowerPoint 미리보기를 사용할 수 있습니다.")
    if not source.exists() or not source.is_file():
        raise PresentationPreviewError(f"PowerPoint 파일을 찾을 수 없습니다: {source}")

    source_stat = source.stat()
    source_sha256 = _sha256_file(source)
    relative = source.relative_to(root).as_posix()
    preview_dir = _cache_directory(root, source)
    preview_pdf = preview_dir / "preview.pdf"
    lock_key = str(preview_dir).casefold() if os.name == "nt" else str(preview_dir)

    with _preview_lock(lock_key):
        metadata = _load_metadata(preview_dir)
        if (
            not force
            and _is_pdf(preview_pdf)
            and metadata.get("source_sha256") == source_sha256
            and int(metadata.get("source_size") or 0) == int(source_stat.st_size)
        ):
            return PresentationPreviewResult(
                source_path=str(source),
                source_relative_path=relative,
                source_sha256=source_sha256,
                source_mtime_ns=int(source_stat.st_mtime_ns),
                source_size=int(source_stat.st_size),
                preview_path=str(preview_pdf),
                preview_size=int(preview_pdf.stat().st_size),
                converter=str(metadata.get("converter") or "cache"),
                cache_hit=True,
                generated_at=str(metadata.get("generated_at") or ""),
            )

        preview_dir.mkdir(parents=True, exist_ok=True)
        attempts: list[dict[str, Any]] = []

        with tempfile.TemporaryDirectory(prefix="agentstudio-presentation-") as temp_name:
            temp_root = Path(temp_name)
            temp_pdf = temp_root / "preview.pdf"

            powerpoint_result = _convert_with_powerpoint(source, temp_pdf)
            attempts.append(powerpoint_result)
            converter = ""
            if powerpoint_result.get("ok"):
                converter = str(powerpoint_result.get("converter") or "Microsoft PowerPoint")
            else:
                try:
                    if temp_pdf.exists():
                        temp_pdf.unlink()
                except OSError:
                    pass
                libreoffice_result = _convert_with_libreoffice(source, temp_pdf, temp_root)
                attempts.append(libreoffice_result)
                if libreoffice_result.get("ok"):
                    converter = str(libreoffice_result.get("converter") or "LibreOffice")

            if not converter or not _is_pdf(temp_pdf):
                compact_attempts = []
                for item in attempts:
                    compact_attempts.append(
                        {
                            "converter": item.get("converter"),
                            "reason": item.get("reason", ""),
                            "unavailable": bool(item.get("unavailable")),
                            "returncode": item.get("returncode"),
                            "output": item.get("output", ""),
                        }
                    )
                reason_parts = []
                for item in compact_attempts:
                    converter_name = str(item.get("converter") or "변환기")
                    reason_text = str(item.get("reason") or "실패")
                    reason_parts.append(f"{converter_name}: {reason_text}")
                summary = " / ".join(reason_parts)
                raise PresentationPreviewError(
                    f"PowerPoint 미리보기를 생성하지 못했습니다. {summary}" if summary else "PowerPoint 미리보기를 생성하지 못했습니다.",
                    attempts=compact_attempts,
                )

            temp_target = preview_dir / "preview.pdf.tmp"
            shutil.copy2(temp_pdf, temp_target)
            if not _is_pdf(temp_target):
                try:
                    temp_target.unlink()
                except OSError:
                    pass
                raise PresentationPreviewError("생성된 PowerPoint 미리보기 PDF가 유효하지 않습니다.")
            temp_target.replace(preview_pdf)

        generated_at = datetime.now(timezone.utc).isoformat()
        metadata = {
            "source_relative_path": relative,
            "source_sha256": source_sha256,
            "source_mtime_ns": int(source_stat.st_mtime_ns),
            "source_size": int(source_stat.st_size),
            "preview_size": int(preview_pdf.stat().st_size),
            "converter": converter,
            "generated_at": generated_at,
            "original_modified": False,
        }
        _write_metadata(preview_dir, metadata)

        return PresentationPreviewResult(
            source_path=str(source),
            source_relative_path=relative,
            source_sha256=source_sha256,
            source_mtime_ns=int(source_stat.st_mtime_ns),
            source_size=int(source_stat.st_size),
            preview_path=str(preview_pdf),
            preview_size=int(preview_pdf.stat().st_size),
            converter=converter,
            cache_hit=False,
            generated_at=generated_at,
        )
