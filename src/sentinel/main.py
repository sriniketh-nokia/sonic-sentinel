import argparse
import sys
from pathlib import Path

from haystack.components.agents import Agent
from haystack.dataclasses import ChatMessage
from openai import APIConnectionError, APITimeoutError

from sentinel.agent import SKILLS_DIRNAME, build_agent
from sentinel.chat import Session, apply_command, without_leading_system
from sentinel.config import Settings
from sentinel.core.cleaner import clean_documents
from sentinel.core.ingest import Ingest
from sentinel.core.reader import can_read, read
from sentinel.core.retriever import Retriever


def _source_files(data_dir: Path) -> list[Path]:
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Knowledge directory does not exist: {data_dir}")
    skills_dir = data_dir / SKILLS_DIRNAME
    files = [
        path
        for path in sorted(data_dir.rglob("*"))
        if path.is_file()
        and not path.name.startswith(".")
        and can_read(path)
        and skills_dir not in path.parents
    ]
    if not files:
        raise FileNotFoundError(f"No supported knowledge files found in {data_dir}")
    return files


def _boot_store(data_dir: Path) -> Ingest:
    ingester = Ingest()
    written = 0
    for path in _source_files(data_dir):
        written += ingester.ingest(clean_documents(read(path)))
    print(f"Indexed {written} documents from {data_dir}", file=sys.stderr)
    return ingester


def _render(result: dict) -> str:
    last = result.get("last_message")
    if last is None:
        return ""
    text = getattr(last, "text", None)
    if text:
        return text
    return str(last)


def ask(
    agent: Agent,
    question: str,
    llm_base_url: str,
    history: list[ChatMessage] | None = None,
) -> list[ChatMessage]:
    try:
        result = agent.run(
            messages=[*(history or []), ChatMessage.from_user(question)]
        )
    except APIConnectionError as exc:
        raise SystemExit(
            f"Cannot reach the LLM at {llm_base_url}. "
            "Start llama-server first."
        ) from exc
    except APITimeoutError as exc:
        raise SystemExit(
            f"Timed out waiting for the LLM at {llm_base_url}."
        ) from exc
    print(_render(result))
    returned = result.get("messages") or []
    return without_leading_system(list(returned))


def repl(agent: Agent, llm_base_url: str) -> None:
    session = Session()
    chat = session.current
    print(f"Sentinel. Chat {chat.id} · {chat.title}")
    print("Type a question, /help, or quit.")
    while True:
        chat = session.current
        try:
            line = input(f"[{chat.id} {chat.title}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line.lower() in {"q", "quit", "exit"}:
            return
        reply = apply_command(session, line)
        if reply is not None:
            print(reply)
            continue
        chat.messages = ask(agent, line, llm_base_url, chat.messages)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sentinel — SONiC on-device assistant"
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Question to ask once. Omit for an interactive prompt.",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    ingester = _boot_store(settings.data_dir)
    agent = build_agent(settings, Retriever(ingester.document_store))
    agent.warm_up()

    question = " ".join(args.question).strip()
    if question:
        ask(agent, question, settings.llm_base_url)
        return
    repl(agent, settings.llm_base_url)


if __name__ == "__main__":
    main()
