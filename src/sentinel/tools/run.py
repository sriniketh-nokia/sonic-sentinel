import shlex
import subprocess
from os import environ

_TIMEOUT_SECONDS = 30.0
_MAX_CHARS = 8000
_HOST_NSENTER = ("nsenter", "-t", "1", "-m", "-u", "-i", "-n", "--")


def _run_on_host() -> bool:
    return environ.get("SENTINEL_RUN_ON_HOST", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def run_cli(command: str) -> str:
    if not isinstance(command, str) or not command.strip():
        raise ValueError("Command must be a non-empty string")
    command = command.strip()
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"Invalid command: {exc}") from exc
    if not argv:
        raise ValueError("Command must be a non-empty string")
    if _run_on_host():
        argv = [*_HOST_NSENTER, *argv]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return f"Command not found: {argv[0]}"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {_TIMEOUT_SECONDS}s: {command}"
    output = ((completed.stdout or "") + (completed.stderr or "")).strip() or (
        "(no output)"
    )
    if completed.returncode != 0:
        output = f"exit {completed.returncode}\n{output}"
    if len(output) > _MAX_CHARS:
        output = output[: _MAX_CHARS - 1] + "…"
    return output
