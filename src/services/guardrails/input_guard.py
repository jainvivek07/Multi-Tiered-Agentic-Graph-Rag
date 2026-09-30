import asyncio
from nemoguardrails import LLMRails, RailsConfig
from src.core.config import settings
from src.core.logger import log

_REJECTION_SENTINELS = (
    "I can only answer questions about company documents",
    "I cannot comply with that request",
)


class NeMoInputGuard:
    _rails: LLMRails | None = None

    @classmethod
    def _get_rails(cls) -> LLMRails:
        if cls._rails is None:
            log.info("Loading NeMo Guardrails config...", path=settings.NEMO_CONFIG_PATH)
            config = RailsConfig.from_path(settings.NEMO_CONFIG_PATH)
            cls._rails = LLMRails(config)
            log.info("NeMo Guardrails loaded.")
        return cls._rails


async def check_input(query: str) -> tuple[bool, str]:
    """
    Runs the incoming query through NeMo Guardrails.
    Returns (is_safe: bool, reason: str).

    NeMo evaluates both topic rails (off-topic rejection) and
    jailbreak rails (prompt-injection patterns) defined in rails.co.
    If the model returns one of the canonical rejection phrases, the
    query is considered unsafe and the pipeline is short-circuited.
    """
    rails = NeMoInputGuard._get_rails()

    loop = asyncio.get_running_loop()

    response = await rails.generate_async(
        messages=[{"role": "user", "content": query}]
    )
    bot_reply: str = response if isinstance(response, str) else response.get("content", "")

    for sentinel in _REJECTION_SENTINELS:
        if sentinel in bot_reply:
            log.warning(
                "Input blocked by NeMo Guardrails",
                query=query[:120],
                reply=bot_reply[:200],
            )
            return False, bot_reply

    return True, "ok"
