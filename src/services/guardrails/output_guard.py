import asyncio
from lettucedetect.models.inference import HallucinationDetector
from src.core.logger import log


class LettuceOutputGuard:
    """
    Singleton wrapper around LettuceDetect's HallucinationDetector.
    """
    _detector: HallucinationDetector | None = None

    @classmethod
    def _get_detector(cls) -> HallucinationDetector:
        if cls._detector is None:
            log.info("Loading LettuceDetect hallucination detector...")
            cls._detector = HallucinationDetector(
                method="transformer",
                model_path="KRLabsOrg/lettucedect-base-modernbert-en-v1",
            )
            log.info("LettuceDetect detector loaded.")
        return cls._detector


async def check_output(
    answer: str,
    context_chunks: list[dict],
    query: str,
) -> tuple[bool, str]:
    """
    Checks whether the generated answer is grounded in the retrieved context.
    Returns (is_hallucinated: bool, detail: str).

    - is_hallucinated=True  → hallucinated spans were detected; caller should regenerate.
    - is_hallucinated=False → answer is grounded; safe to return to the user.

    The detector runs in a thread-pool executor to avoid blocking the event loop.
    """
    if not context_chunks:
        log.warning("Output guard: no context chunks — skipping LettuceDetect, flagging as hallucinated.")
        return True, "No context was retrieved — answer cannot be verified."

    if not answer or len(answer.strip()) < 10:
        return True, "Answer is empty or too short."

    contexts = [c.get("content", "") for c in context_chunks if c.get("content")]
    if not contexts:
        return True, "Context chunks contained no text content."

    detector = LettuceOutputGuard._get_detector()
    loop = asyncio.get_running_loop()

    predictions = await loop.run_in_executor(
        None,
        lambda: detector.predict(
            context=contexts,
            question=query,
            answer=answer,
            output_format="spans",
        ),
    )

    hallucinated_spans = [p for p in predictions if p.get("label") == "hallucinated"]

    if hallucinated_spans:
        detail = f"Detected {len(hallucinated_spans)} hallucinated span(s): " + str(
            [s.get("text", "")[:80] for s in hallucinated_spans]
        )
        log.warning("LettuceDetect: hallucination detected", detail=detail, query=query[:120])
        return True, detail

    return False, "ok"
