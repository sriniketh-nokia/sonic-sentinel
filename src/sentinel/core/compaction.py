from haystack.components.agents.state import State
from haystack.hooks.compaction import (
    CompactionHook,
    SlidingWindowCompactor,
    ToolResultPruningCompactor,
)

from sentinel.config import Settings
from sentinel.core.logger import TraceLogger

_STRATEGIES = {
    ToolResultPruningCompactor: "ToolResultPruning",
    SlidingWindowCompactor: "SlidingWindow",
}


class _TracingCompactionHook(CompactionHook):
    def __init__(self, trace: TraceLogger, name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._trace = trace
        self._name = name

    def run(self, state: State) -> None:
        before = state.data.get("messages")
        super().run(state)
        after = state.data.get("messages")
        if after is before:
            return
        step = int(state.data.get("step_count") or 0) + 1
        self._trace.compacted(
            self._name,
            _STRATEGIES[type(self.compactor)],
            len(before or []),
            len(after or []),
            step,
        )


def compaction_hooks(settings: Settings, trace: TraceLogger, name: str) -> list[CompactionHook]:
    """Prune old tool results, then drop old turns if the window is still full."""
    return [
        _TracingCompactionHook(
            trace,
            name,
            compactor=compactor,
            context_window=settings.context_window,
            compact_at=settings.compact_at,
            compact_to=settings.compact_to,
        )
        for compactor in (ToolResultPruningCompactor(), SlidingWindowCompactor())
    ]
