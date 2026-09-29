from haystack.components.agents import Agent
from haystack.skill_stores.file_system import FileSystemSkillStore
from haystack.tools import AgentTool, SkillToolset

from sentinel.config import Settings
from sentinel.core.compaction import compaction_hooks
from sentinel.core.llm import chat_generator
from sentinel.core.logger import TraceLogger, merge_hooks
from sentinel.core.retriever import Retriever
from sentinel.hooks import HITL_HOOK
from sentinel.tools.cli_linux import linux_cli
from sentinel.tools.cli_sonic import sonic_cli


SKILLS_DIRNAME = "skills"

_SONIC_SKILL_PROMPT = (
    "You are a SONiC specialist. A loaded skill's instructions may list "
    "commands to run; execute those with run_sonic_cli (SONiC CLI) or "
    "run_linux_cli (Linux/host commands), in the order the skill gives. "
    "Never invent command output. If no skill covers the task, say so "
    "plainly instead of guessing."
)

_SONIC_CLI_PROMPT = (
    "You are a SONiC CLI specialist. "
    "Derive the correct SONiC CLI command for the given task, then use "
    "run_sonic_cli to execute it. Do not invent commands."
)

_LINUX_CLI_PROMPT = (
    "You are a Linux host CLI specialist. "
    "Propose the Linux command to inspect host state, then run_linux_cli to "
    "execute it. Do not invent destructive commands."
)

_COORDINATOR_PROMPT = (
    "You are Sentinel, the coordinator for on-device SONiC assistance. "
    "Delegate: sonic_skill to understand or debug any SONiC-specific topic "
    "(for example VRRP) using a loaded skill playbook and live commands; "
    "sonic_cli to look up and run a one-off SONiC command; linux_cli to run "
    "a one-off Linux command that inspects host state. "
    "You do not load skills or run commands yourself. "
    "Synthesize specialist replies for the user. "
    "Command execution requires human approval."
)


def _specialist(
    settings: Settings,
    *,
    name: str,
    tools: list,
    system_prompt: str,
    trace: TraceLogger,
    hooks: dict | None = None,
) -> Agent:
    return Agent(
        chat_generator=chat_generator(settings),
        tools=tools,
        system_prompt=system_prompt,
        max_agent_steps=settings.max_agent_steps,
        tool_concurrency_limit=1,
        hooks=merge_hooks({"before_llm": compaction_hooks(settings, trace, name)}, hooks),
    )


def build_agent(settings: Settings, retriever: Retriever) -> Agent:
    trace = TraceLogger()

    skills = SkillToolset(FileSystemSkillStore(settings.data_dir / SKILLS_DIRNAME))

    sonic_skill_agent = AgentTool(
        agent=_specialist(
            settings,
            name="sonic_skill",
            tools=[skills, sonic_cli(), linux_cli()],
            system_prompt=_SONIC_SKILL_PROMPT,
            trace=trace,
            hooks=merge_hooks(
                trace.hooks("sonic_skill"),
                {"before_tool": [HITL_HOOK]},
            ),
        ),
        name="sonic_skill",
        description=(
            "Understand or debug any SONiC-specific topic (for example "
            "VRRP, and whatever other skills are added later) using its "
            "loaded skill playbook plus live SONiC and Linux commands. Use "
            "for skill-backed troubleshooting, not one-off CLI lookups."
        ),
    )
    sonic_cli_agent = AgentTool(
        agent=_specialist(
            settings,
            name="sonic_cli",
            tools=[sonic_cli()],
            system_prompt=_SONIC_CLI_PROMPT,
            trace=trace,
            hooks=merge_hooks(
                trace.hooks("sonic_cli"),
                {"before_tool": [HITL_HOOK]},
            ),
        ),
        name="sonic_cli",
        description=(
            "Find and run the SONiC CLI command for an operational task. "
            "Use when the user needs a show or config command."
        ),
    )
    linux_cli_agent = AgentTool(
        agent=_specialist(
            settings,
            name="linux_cli",
            tools=[linux_cli()],
            system_prompt=_LINUX_CLI_PROMPT,
            trace=trace,
            hooks=merge_hooks(
                trace.hooks("linux_cli"),
                {"before_tool": [HITL_HOOK]},
            ),
        ),
        name="linux_cli",
        description=(
            "Run a Linux command to inspect host state "
            "(interfaces, processes, files, logs)."
        ),
    )
    return Agent(
        chat_generator=chat_generator(settings),
        tools=[sonic_skill_agent, sonic_cli_agent, linux_cli_agent],
        system_prompt=_COORDINATOR_PROMPT,
        max_agent_steps=settings.max_agent_steps,
        tool_concurrency_limit=1,
        hooks=merge_hooks(
            {"before_llm": compaction_hooks(settings, trace, "coordinator")},
            trace.hooks("coordinator"),
        ),
    )
