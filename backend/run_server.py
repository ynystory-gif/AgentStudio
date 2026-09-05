from __future__ import annotations

import argparse
import asyncio
import os
import selectors
import sys

import uvicorn


def build_selector_loop():
    """
    Windows Psycopg async compatibility loop.
    This is intentionally explicit instead of relying only on
    WindowsSelectorEventLoopPolicy.
    """
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.new_event_loop()


async def serve(host: str, port: int, reload: bool = False) -> None:
    config = uvicorn.Config(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        loop="asyncio",
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    # Explicit loop factory is the same pattern that successfully connected
    # Psycopg on this Windows machine.
    if sys.platform == "win32":
        try:
            asyncio.run(
                serve(args.host, args.port, args.reload),
                loop_factory=build_selector_loop,
            )
            return
        except TypeError:
            # Compatibility fallback for Python versions whose asyncio.run()
            # does not accept loop_factory.
            loop = build_selector_loop()
            try:
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    serve(args.host, args.port, args.reload)
                )
            finally:
                loop.close()
            return

    asyncio.run(serve(args.host, args.port, args.reload))


if __name__ == "__main__":
    main()
