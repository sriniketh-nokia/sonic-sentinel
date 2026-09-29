import json
import sys
from typing import Any, TextIO

from haystack.components.agents.state import State
from haystack.hooks import hook


def _clip(text: str, n: int = 240) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _message_text(value: Any) -> str:
    if isinstance(value, dict):
        content = value.get("content", "")
        return content if isinstance(content, str) else str(content)
    text = getattr(value, "text", None)
    return text if isinstance(text, str) else str(value)


def _fmt_args(arguments: dict[str, Any]) -> str:
    if "query" in arguments:
        return f"query={_clip(arguments['query'])!r}"
    if "command" in arguments:
        return f"command={arguments['command']!r}"
    messages = arguments.get("messages")
    if isinstance(messages, list) and messages:
        return f"task={_clip(_message_text(messages[0]))!r}"
    return _clip(json.dumps(arguments, default=str))


def merge_hooks(*maps: dict | None) -> dict:
    out: dict = {}
    for mapping in maps:
        if not mapping:
            continue
        for point, hooks in mapping.items():
            out.setdefault(point, []).extend(hooks)
    return out


class TraceLogger:
    def __init__(self, stream: TextIO = sys.stderr) -> None:
        self.stream = stream

    def _write(self, name: str, line: str) -> None:
        print(f"  · [{name}] {line}", file=self.stream, flush=True)

    def compacted(self, name: str, strategy: str, before: int, after: int, step: int) -> None:
        span = f"{before}→{after}" if before != after else str(before)
        self._write(name, f"compact {strategy}: {span} msgs (step {step})")

    def hooks(self, name: str) -> dict:
        logger = self

        @hook
        def before_llm(state: State) -> None:
            step = int(state.data.get("step_count") or 0) + 1
            logger._write(name, f"thinking (step {step})")

        @hook
        def before_tool(state: State) -> None:
            messages = state.data.get("messages") or []
            last = messages[-1] if messages else None
            if last is None:
                return
            reasoning = getattr(last, "reasoning", None)
            text = getattr(reasoning, "reasoning_text", None)
            if text:
                logger._write(name, f"reason: {_clip(text, 400)}")
            for call in last.tool_calls or []:
                logger._write(name, f"→ {call.tool_name} {_fmt_args(call.arguments)}")

        @hook
        def after_tool(state: State) -> None:
            results = []
            for message in reversed(state.data.get("messages") or []):
                result = message.tool_call_result
                if result is None:
                    break
                results.append(result)
            for result in reversed(results):
                origin = result.origin.tool_name if result.origin else "tool"
                logger._write(name, f"← {origin} {_clip(result.result, 320)}")

        @hook
        def on_exit(state: State) -> None:
            reason = state.data.get("exit_reason") or "text"
            logger._write(name, f"done ({reason})")

        return {
            "before_llm": [before_llm],
            "before_tool": [before_tool],
            "after_tool": [after_tool],
            "on_exit": [on_exit],
        }
