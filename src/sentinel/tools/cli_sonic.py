from haystack.tools import Tool

from sentinel.tools.run import run_cli


def sonic_cli() -> Tool:
    return Tool(
        name="run_sonic_cli",
        description=(
            "Execute a SONiC CLI command (show or config) after the user approves. "
            "Pass the full command string, for example 'show vlan brief'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The SONiC CLI command to run.",
                }
            },
            "required": ["command"],
        },
        function=run_cli,
    )
