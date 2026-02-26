#!/usr/bin/env python3
"""
CodeBot GLiClass Coding Gatekeeper.

Classifies a user intent as either "system_bash" (OS/system commands → bash skill)
or "python_api_or_data" (API calls, data processing, or logic → python skill).

Usage:
    python3 skill_router.py "list all running docker containers"
    # → system_bash 0.923

    python3 skill_router.py "fetch the latest bitcoin price from an API"
    # → python_api_or_data 0.887

The result is printed to stdout as "<label> <confidence>" so Pi CLI can
branch on it before selecting a code template.
"""

import sys
import re
import logging
import os

logger = logging.getLogger(__name__)

# Coding classification labels
CODING_LABELS = ["system_bash", "python_api_or_data"]
CLASSIFICATION_THRESHOLD = 0.3

# Regex fast path: obvious bash indicators
_BASH_TRIGGERS = re.compile(
    r'\b(list|show|kill|start|stop|restart|check|monitor|disk|cpu|memory|ram|'
    r'process|port|network|interface|firewall|cron|service|daemon|docker|'
    r'container|systemctl|apt|yum|brew|chmod|chown|mkdir|rm|mv|cp|grep|'
    r'find|tail|head|cat|awk|sed|ping|curl|wget|ssh|scp|tar|zip|unzip|'
    r'ps|top|htop|df|du|free|uname|hostname|whoami|id|groups)\b',
    re.IGNORECASE,
)

# Regex fast path: obvious python/API indicators
_PYTHON_TRIGGERS = re.compile(
    r'\b(api|fetch|request|http|json|parse|calculate|compute|analyze|'
    r'summarize|classify|transform|convert|encode|decode|hash|encrypt|'
    r'decrypt|database|sql|query|pandas|numpy|plot|graph|chart|scrape|'
    r'regex|pattern|format|template|render|generate|predict|model)\b',
    re.IGNORECASE,
)

_pipeline = None  # singleton — loaded once


def load_coding_classifier(device: str = "cpu") -> bool:
    """
    Load GLiClass model for bash vs python classification.
    CodeBot always uses CPU — the GPU is reserved for the Gateway's classifier.
    """
    global _pipeline
    try:
        from gliclass import GLiClassModel, ZeroShotClassificationPipeline
        from transformers import AutoTokenizer

        hf_home = os.getenv("HF_HOME", "/workspace/.cache/huggingface")
        os.makedirs(hf_home, exist_ok=True)

        logger.info("Loading GLiClass coding classifier on %s...", device)
        model = GLiClassModel.from_pretrained("knowledgator/gliclass-small-v1.0")
        tokenizer = AutoTokenizer.from_pretrained("knowledgator/gliclass-small-v1.0")
        _pipeline = ZeroShotClassificationPipeline(
            model, tokenizer,
            classification_type="multi-label",
            device=device,
        )
        logger.info("GLiClass coding classifier ready on %s", device)
        return True
    except Exception as e:
        logger.error("GLiClass load failed: %s — fast-path regex will be used", e)
        return False


def classify_coding_intent(text: str) -> tuple[str, float]:
    """
    Return (label, confidence) for bash vs python routing.

    Fast path: regex pre-filter avoids model inference for clear-cut cases.
    """
    bash_match = bool(_BASH_TRIGGERS.search(text))
    python_match = bool(_PYTHON_TRIGGERS.search(text))

    # Unambiguous fast paths
    if bash_match and not python_match:
        logger.debug("Regex fast path → system_bash | %s", text[:60])
        return "system_bash", 1.0
    if python_match and not bash_match:
        logger.debug("Regex fast path → python_api_or_data | %s", text[:60])
        return "python_api_or_data", 1.0

    # Ambiguous — delegate to GLiClass
    if _pipeline is not None:
        try:
            results = _pipeline(text, CODING_LABELS, threshold=CLASSIFICATION_THRESHOLD)[0]
            if results:
                top = max(results, key=lambda x: x["score"])
                logger.info(
                    "GLiClass coding: %s (%.3f) | %s",
                    top["label"], top["score"], text[:60],
                )
                return top["label"], top["score"]
        except Exception as e:
            logger.error("GLiClass classify error: %s", e)

    # Default: bash (safer — pure bash scripts are more sandboxable)
    logger.debug("Defaulting to system_bash for: %s", text[:60])
    return "system_bash", 0.5


def main():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s - %(message)s",
    )
    if len(sys.argv) < 2:
        print("Usage: skill_router.py <intent_text>", file=sys.stderr)
        sys.exit(1)

    intent_text = " ".join(sys.argv[1:])

    # Load model (best-effort — regex fallback is fine)
    load_coding_classifier(device="cpu")

    label, confidence = classify_coding_intent(intent_text)
    # Print result to stdout — Pi CLI reads this to choose template
    print(f"{label} {confidence:.3f}")


if __name__ == "__main__":
    main()
