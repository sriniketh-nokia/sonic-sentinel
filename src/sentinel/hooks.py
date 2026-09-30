from haystack.hooks.human_in_the_loop import (
    AlwaysAskPolicy,
    BlockingConfirmationStrategy,
    ConfirmationHook,
    SimpleConsoleUI,
)

_EXECUTE_STRATEGY = BlockingConfirmationStrategy(
    confirmation_policy=AlwaysAskPolicy(),
    confirmation_ui=SimpleConsoleUI(),
)

HITL_HOOK = ConfirmationHook(
    confirmation_strategies={
        ("run_commands", "run_sonic_cli", "run_linux_cli"): _EXECUTE_STRATEGY,
    }
)
