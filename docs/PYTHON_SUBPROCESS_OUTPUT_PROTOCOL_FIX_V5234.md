# Python Subprocess Output Protocol Fix v5.234

## Problem
Persistent Python F5/F8 execution used Worker stdout as a raw one-line JSON control channel.
When user code ran a child process such as `docker`, `git`, or `npm` without `capture_output=True`, the child inherited the Worker stdout handle. Its normal text output (for example `db-pg`) arrived before the Worker JSON response and the Backend attempted `json.loads()` on that text, causing `Expecting value: line 1 column 1 (char 0)`.

## Fix
- Frame Worker control responses with `__AGENTSTUDIO_PY_RESPONSE_V1__`.
- Read Worker output until the framed response is found instead of assuming the first stdout line is JSON.
- Preserve all preceding native child-process output and merge it into the user-visible Python stdout result.
- Merge Worker stderr into the drained stdout stream so verbose child processes cannot block on an unread stderr pipe.
- Convert malformed internal protocol JSON into a RuntimeError instead of leaking JSONDecodeError as HTTP 400.

## Expected behavior
Code such as:

```python
import subprocess
subprocess.run(["docker", "stop", "db-pg"])
subprocess.run(["docker", "start", "db-pg"])
```

can print native Docker output while AgentStudio still receives the framed execution result correctly.
