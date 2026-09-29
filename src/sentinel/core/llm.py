from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.utils import Secret

from sentinel.config import Settings


def chat_generator(settings: Settings) -> OpenAIChatGenerator:
    return OpenAIChatGenerator(
        api_base_url=settings.llm_base_url,
        api_key=Secret.from_token("local"),
        model=settings.llm_model,
        timeout=settings.llm_timeout,
        max_retries=2,
        tools_strict=False,
        generation_kwargs={
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
        },
    )
