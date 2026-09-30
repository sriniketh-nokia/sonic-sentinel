from haystack.tools import Tool

from sentinel.tools.cli_commands import MAX_COMMANDS, run_commands


def commands_cli() -> Tool:
    return Tool(
        name="run_commands",
        description=(
            "Run several read-only commands from one skill step after the user "
            f"approves, at most {MAX_COMMANDS} commands. "
            "Pass them in the order the skill gives. "
            "Use this instead of one call per command. "
            "Do not use it for configuration changes or interactive vtysh."
        ),
        parameters={
            "type": "object",
            "properties": {
                "commands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Read-only commands from a single skill step, "
                        "in playbook order."
                    ),
                }
            },
            "required": ["commands"],
        },
        function=run_commands,
    )
