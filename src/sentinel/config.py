from dataclasses import dataclass
from os import environ
from pathlib import Path

_REPO_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_DEFAULT_LLAMA_CPP_PORT = 8888
_DEFAULT_LLM_MODEL = "Qwen3-4B-Instruct-2507"
_DEFAULT_LLM_TIMEOUT = 120.0
_DEFAULT_LLM_TEMPERATURE = 0.2
_DEFAULT_LLM_MAX_TOKENS = 1024
_DEFAULT_RETRIEVE_TOP_K = 4
_DEFAULT_HIT_CHARS = 1200
_DEFAULT_MAX_AGENT_STEPS = 8
_DEFAULT_CONTEXT_WINDOW = 8192
_DEFAULT_COMPACT_AT = 0.7
_DEFAULT_COMPACT_TO = 0.4


def _env_float(name: str, default: float) -> float:
    raw = environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    raw = environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value < 1:
        raise ValueError(f"{name} must be >= 1, got {value}")
    return value


def _compact_fraction(name: str, default: float) -> float:
    value = _env_float(name, default)
    if not 0 < value <= 1:
        raise ValueError(f"{name} must be > 0 and <= 1, got {value}")
    return value


def _llama_cpp_port() -> int:
    port = _env_int("SENTINEL_LLAMA_CPP_PORT", _DEFAULT_LLAMA_CPP_PORT)
    if port > 65535:
        raise ValueError(f"SENTINEL_LLAMA_CPP_PORT must be <= 65535, got {port}")
    return port


def _llm_base_url() -> str:
    explicit = environ.get("SENTINEL_LLM_BASE_URL")
    if explicit:
        return explicit
    return f"http://127.0.0.1:{_llama_cpp_port()}/v1"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    llm_base_url: str
    llm_model: str
    llm_timeout: float
    llm_temperature: float
    llm_max_tokens: int
    retrieve_top_k: int
    hit_chars: int
    max_agent_steps: int
    context_window: int
    compact_at: float
    compact_to: float

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(environ.get("SENTINEL_DATA_DIR", str(_REPO_DATA_DIR)))
        compact_at = _compact_fraction("SENTINEL_COMPACT_AT", _DEFAULT_COMPACT_AT)
        compact_to = _compact_fraction("SENTINEL_COMPACT_TO", _DEFAULT_COMPACT_TO)
        if compact_to >= compact_at:
            raise ValueError(
                "SENTINEL_COMPACT_TO must be less than SENTINEL_COMPACT_AT, "
                f"got compact_to={compact_to} and compact_at={compact_at}"
            )
        return cls(
            data_dir=data_dir.expanduser().resolve(),
            llm_base_url=_llm_base_url(),
            llm_model=environ.get("SENTINEL_LLM_MODEL", _DEFAULT_LLM_MODEL),
            llm_timeout=_env_float("SENTINEL_LLM_TIMEOUT", _DEFAULT_LLM_TIMEOUT),
            llm_temperature=_env_float(
                "SENTINEL_LLM_TEMPERATURE", _DEFAULT_LLM_TEMPERATURE
            ),
            llm_max_tokens=_env_int("SENTINEL_LLM_MAX_TOKENS", _DEFAULT_LLM_MAX_TOKENS),
            retrieve_top_k=_env_int("SENTINEL_RETRIEVE_TOP_K", _DEFAULT_RETRIEVE_TOP_K),
            hit_chars=_env_int("SENTINEL_HIT_CHARS", _DEFAULT_HIT_CHARS),
            max_agent_steps=_env_int(
                "SENTINEL_MAX_AGENT_STEPS", _DEFAULT_MAX_AGENT_STEPS
            ),
            context_window=_env_int(
                "SENTINEL_CONTEXT_WINDOW", _DEFAULT_CONTEXT_WINDOW
            ),
            compact_at=compact_at,
            compact_to=compact_to,
        )
