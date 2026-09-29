from dataclasses import dataclass, field

from haystack.dataclasses import ChatMessage, ChatRole

_DEFAULT_TITLE = "New chat"
_HELP = (
    "/new [title]   start a chat\n"
    "/list          list chats\n"
    "/use <id>      switch chat\n"
    "/history       show this chat\n"
    "/help          show commands\n"
    "quit           leave"
)


@dataclass
class Chat:
    id: int
    title: str
    messages: list[ChatMessage] = field(default_factory=list)


class Session:
    """In-memory chats for one REPL process. Each chat owns its own messages."""

    def __init__(self) -> None:
        self._chats: dict[int, Chat] = {}
        self._next_id = 1
        self.current = self.new(_DEFAULT_TITLE)

    def new(self, title: str) -> Chat:
        chat = Chat(id=self._next_id, title=title.strip() or _DEFAULT_TITLE)
        self._chats[chat.id] = chat
        self._next_id += 1
        self.current = chat
        return chat

    def switch(self, chat_id: int) -> Chat | None:
        chat = self._chats.get(chat_id)
        if chat is None:
            return None
        self.current = chat
        return chat

    def format_list(self) -> str:
        lines = []
        for chat in self._chats.values():
            marker = "*" if chat.id == self.current.id else " "
            lines.append(
                f"{marker} {chat.id}  {chat.title}  ({len(chat.messages)} messages)"
            )
        return "\n".join(lines)


def without_leading_system(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Drop the system prompt the Agent prepends on every run."""
    index = 0
    while index < len(messages) and messages[index].is_from(ChatRole.SYSTEM):
        index += 1
    return messages[index:]


def format_history(messages: list[ChatMessage]) -> str:
    if not messages:
        return "(empty)"
    lines: list[str] = []
    for message in messages:
        if message.is_from(ChatRole.USER):
            lines.append(f"you: {message.text or ''}")
            continue
        if message.is_from(ChatRole.ASSISTANT):
            if message.text:
                lines.append(f"sentinel: {message.text}")
            for call in message.tool_calls or []:
                lines.append(f"  call {call.tool_name}")
            continue
        result = message.tool_call_result
        if result is not None:
            origin = result.origin.tool_name if result.origin else "tool"
            text = " ".join(str(result.result).split())
            if len(text) > 240:
                text = text[:239] + "…"
            lines.append(f"  {origin}: {text}")
            continue
        if message.text:
            lines.append(message.text)
    return "\n".join(lines) if lines else "(empty)"


def apply_command(session: Session, line: str) -> str | None:
    """Handle a slash command. Return None when ``line`` is a chat message."""
    if not line.startswith("/"):
        return None
    body = line[1:].strip()
    name, _, rest = body.partition(" ")
    name = name.lower()
    rest = rest.strip()
    if name in {"help", "?"}:
        if rest:
            return "/help takes no arguments"
        return _HELP
    if name == "new":
        chat = session.new(rest)
        return f"Chat {chat.id} · {chat.title}"
    if name == "list":
        if rest:
            return "/list takes no arguments"
        return session.format_list()
    if name == "use":
        parts = rest.split()
        if len(parts) != 1:
            return "Usage: /use <id>"
        try:
            chat_id = int(parts[0])
        except ValueError:
            return f"Chat id must be an integer, got {parts[0]!r}"
        chat = session.switch(chat_id)
        if chat is None:
            return f"No chat {chat_id}."
        return f"Chat {chat.id} · {chat.title}"
    if name == "history":
        if rest:
            return "/history takes no arguments"
        return format_history(session.current.messages)
    if not name:
        return _HELP
    return f"Unknown command /{name}.\n{_HELP}"
