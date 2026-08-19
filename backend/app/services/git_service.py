from app.services.local_control import run_command

async def git_status(root: str):
    return await run_command("git status --short", root)

async def git_diff(root: str):
    return await run_command("git diff --no-ext-diff", root)

async def checkpoint(root: str, label: str = "agentstudio-checkpoint"):
    status = await run_command("git rev-parse --is-inside-work-tree", root)
    if status["returncode"] != 0:
        return {"ok": False, "message": "Git 저장소가 아닙니다."}
    head = await run_command("git rev-parse HEAD", root)
    return {"ok": True, "head": head["output"].strip(), "label": label}

async def rollback_hard(root: str, commit: str):
    return await run_command(f'git reset --hard "{commit}"', root)
