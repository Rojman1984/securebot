"""
GLiClass zero-shot intent classifier.
Singleton — loads ONCE at startup, reused for every request.
NEVER instantiate the model inside classify_intent() — that adds 3-5s per call.

Model: knowledgator/gliclass-small-v1.0 (144M params, ~10ms GPU inference)
Validated results on GTX 1050 Ti:
  search  1.000  |  What are the showtimes for GOAT in McAllen TX today?
  task    1.000  |  what are my pending tasks?
  chat    1.000  |  hello how are you
  search  1.000  |  search for AI news today
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Intent labels — maps to routing branches in orchestrator
INTENT_LABELS = ["search", "action", "task", "memory", "knowledge", "chat"]
CLASSIFICATION_THRESHOLD = 0.3

# Regex pre-filter: zero-cost fast path for obvious search triggers
SEARCH_TRIGGERS = re.compile(
    r'\b(today|tonight|right now|currently|showtimes?|playing near|'
    r'weather|score|news today|price of|stock price|open now|hours today|'
    r'near me|latest|breaking|what.s happening)\b',
    re.IGNORECASE
)

_pipeline = None  # module-level singleton — never reassign per request


def load_classifier(device: str = "cuda:0") -> bool:
    """
    Load GLiClass model into GPU memory.
    Call ONCE at startup from gateway startup event.
    Returns True on success, False on failure.
    """
    global _pipeline
    try:
        from gliclass import GLiClassModel, ZeroShotClassificationPipeline
        from transformers import AutoTokenizer

        logger.info("Loading GLiClass classifier on %s...", device)
        model = GLiClassModel.from_pretrained("knowledgator/gliclass-small-v1.0")
        tokenizer = AutoTokenizer.from_pretrained(
            "knowledgator/gliclass-small-v1.0"
        )
        _pipeline = ZeroShotClassificationPipeline(
            model, tokenizer,
            classification_type='multi-label',
            device=device
        )
        logger.info(
            "GLiClass ready on %s — zero-shot intent classification active", device
        )
        return True
    except Exception as e:
        logger.warning("GLiClass GPU load failed: %s — trying CPU", e)
        try:
            from gliclass import GLiClassModel, ZeroShotClassificationPipeline
            from transformers import AutoTokenizer
            model = GLiClassModel.from_pretrained(
                "knowledgator/gliclass-small-v1.0"
            )
            tokenizer = AutoTokenizer.from_pretrained(
                "knowledgator/gliclass-small-v1.0"
            )
            _pipeline = ZeroShotClassificationPipeline(
                model, tokenizer,
                classification_type='multi-label',
                device='cpu'
            )
            logger.info("GLiClass on CPU fallback (~50ms per call)")
            return True
        except Exception as e2:
            logger.error("GLiClass failed entirely: %s", e2)
            return False


def classify_intent(text: str) -> tuple[str, float]:
    """
    Classify user query intent. Returns (label, confidence).
    Safe to call from async context — runs synchronously.
    Fast path: regex pre-filter catches obvious search queries in 0ms.
    """
    # Zero-cost fast path
    if SEARCH_TRIGGERS.search(text):
        logger.debug("Regex pre-filter: search | %s", text[:60])
        return "search", 1.0

    if _pipeline is None:
        logger.warning("GLiClass not loaded — defaulting to knowledge")
        return "knowledge", 0.0

    try:
        results = _pipeline(
            text, INTENT_LABELS, threshold=CLASSIFICATION_THRESHOLD
        )[0]
        if not results:
            return "knowledge", 0.5
        top = max(results, key=lambda x: x['score'])
        logger.info(
            "GLiClass: %s (%.3f) | %s", top['label'], top['score'], text[:60]
        )
        return top['label'], top['score']
    except Exception as e:
        logger.error("GLiClass error: %s — defaulting to knowledge", e)
        return "knowledge", 0.0
