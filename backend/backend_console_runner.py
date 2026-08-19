from __future__ import annotations

import argparse
import os
import subprocess
import sys
import signal
from pathlib import Path


def _stream_process(proc: subprocess.Popen, log_file):
    assert proc.stdout is not None

    while True:
        raw = proc.stdout.readline()
        if not raw:
            break

        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        else:
            text = raw

        # Write directly to the current console as Unicode text.
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except UnicodeEncodeError:
            sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
            sys.stdout.buffer.flush()

        log_file.write(text)
        log_file.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    backend_dir = Path(__file__).resolve().parent
    run_server = backend_dir / "run_server.py"
    log_path = Path(args.log).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = [
        sys.executable,
        str(run_server),
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]

    print("[START] FastAPI Backend")
    print(f"[LOG] {log_path}")
    print()

    with log_path.open("a", encoding="utf-8", newline="") as log_file:
        proc = subprocess.Popen(
            cmd,
            cwd=str(backend_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=None,
            bufsize=0,
        )

        try:
            _stream_process(proc, log_file)
            return_code = proc.wait()
        except KeyboardInterrupt:
            try:
                proc.send_signal(
                    getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM)
                )
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            return_code = proc.wait()

    print()
    if return_code == 0:
        print("[DONE] Backend exited normally.")
    else:
        print(f"[FAILED] Backend exited. ExitCode={return_code}")
        print(f"[LOG] {log_path}")

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
