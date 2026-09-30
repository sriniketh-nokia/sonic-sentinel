from sentinel.tools.run import run_cli

MAX_COMMANDS = 8


def run_commands(commands: list[str]) -> str:
    if not isinstance(commands, list) or not commands:
        raise ValueError("commands must be a non-empty list of command strings")
    if len(commands) > MAX_COMMANDS:
        raise ValueError(
            f"At most {MAX_COMMANDS} commands per call, got {len(commands)}. "
            "Split them into one skill step at a time."
        )
    cleaned: list[str] = []
    for command in commands:
        if not isinstance(command, str) or not command.strip():
            raise ValueError("Each command must be a non-empty string")
        cleaned.append(command.strip())
    blocks: list[str] = []
    for command in cleaned:
        try:
            output = run_cli(command)
        except ValueError as exc:
            output = str(exc)
        blocks.append(f"$ {command}\n{output}")
    return "\n\n".join(blocks)
