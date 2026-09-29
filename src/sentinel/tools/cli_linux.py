from haystack.tools import Tool

from sentinel.tools.run import run_cli


def linux_cli() -> Tool:
    return Tool(
        name="run_linux_cli",
        description=(
            "Execute a Linux command to inspect host state after the user approves. "
            "Pass the full command string, for example 'ip link show'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The Linux command to run.",
                }
            },
            "required": ["command"],
        },
        function=run_cli,
    )
