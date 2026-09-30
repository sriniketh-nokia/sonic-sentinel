from haystack.components.agents import Agent
from haystack.skill_stores.file_system import FileSystemSkillStore
from haystack.tools import SkillToolset

from sentinel.config import Settings
from sentinel.core.compaction import compaction_hooks
from sentinel.core.llm import chat_generator
from sentinel.core.logger import TraceLogger, merge_hooks
from sentinel.core.retriever import Retriever
from sentinel.hooks import HITL_HOOK
from sentinel.tools.cli_batch import commands_cli
from sentinel.tools.cli_linux import linux_cli
from sentinel.tools.cli_sonic import sonic_cli


SKILLS_DIRNAME = "skills"

_SYSTEM_PROMPT = (
    "You are Sentinel, an on-device assistant for SONiC. "
    "Load a skill when the task is SONiC-specific troubleshooting that a skill "
    "covers (for example VRRP) and follow that skill's playbook. "
    "When one skill step lists several read-only commands, pass them all in one "
    "run_commands call, in the order the skill gives. Do not call the tool once "
    "per command. "
    "Use run_sonic_cli for a single SONiC CLI command and run_linux_cli for a "
    "single Linux command. Keep configuration changes and interactive vtysh on "
    "those single-command tools. Do not invent commands or destructive commands. "
    "Never invent command output. If no skill covers the task, say so plainly "
    "instead of guessing. "
    "Command execution requires human approval."
)


def build_agent(settings: Settings, _retriever: Retriever) -> Agent:
    trace = TraceLogger()
    skills = SkillToolset(FileSystemSkillStore(settings.data_dir / SKILLS_DIRNAME))
    return Agent(
        chat_generator=chat_generator(settings),
        tools=[skills, commands_cli(), sonic_cli(), linux_cli()],
        system_prompt=_SYSTEM_PROMPT,
        max_agent_steps=settings.max_agent_steps,
        tool_concurrency_limit=1,
        hooks=merge_hooks(
            {"before_llm": compaction_hooks(settings, trace, "sentinel")},
            trace.hooks("sentinel"),
            {"before_tool": [HITL_HOOK]},
        ),
    )
