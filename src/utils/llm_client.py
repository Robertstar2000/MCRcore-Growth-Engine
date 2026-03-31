"""
MCRcore Growth Engine - LLM Client Wrapper

Provides a unified interface to any OpenAI-compatible LLM API.
Configure via environment variables:
    LLM_API_KEY      - API key
    LLM_API_BASE_URL - Base URL (e.g. https://api.openai.com/v1)
    LLM_MODEL        - Model name (e.g. gpt-4)
"""

import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

from src.utils.logger import setup_logger

load_dotenv()

logger = setup_logger("mcr_growth_engine.llm_client")

LLM_API_KEY = os.getenv("LLM_API_KEY", "PLACEHOLDER_your-openai-api-key")
LLM_API_BASE_URL = os.getenv("LLM_API_BASE_URL", "PLACEHOLDER_https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")


def _get_client():
    """Lazily create and return an OpenAI client instance."""
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package not installed. Run: pip install openai")
        raise

    if "PLACEHOLDER" in LLM_API_KEY:
        logger.warning("LLM_API_KEY is still a PLACEHOLDER - API calls will fail")

    base_url = LLM_API_BASE_URL
    if "PLACEHOLDER" in base_url:
        base_url = "https://api.openai.com/v1"

    return OpenAI(api_key=LLM_API_KEY, base_url=base_url)


def generate_text(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    max_tokens: int = 1024,
    temperature: float = 0.7,
    model: str = None,
) -> str:
    """
    Generate text from a prompt using the configured LLM.

    Args:
        prompt: User prompt / instruction.
        system_prompt: System-level instruction for the model.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (0.0 - 2.0).
        model: Override model name.

    Returns:
        Generated text string.
    """
    client = _get_client()
    model = model or LLM_MODEL

    logger.info(f"LLM generate_text: model={model}, max_tokens={max_tokens}")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        result = response.choices[0].message.content.strip()
        logger.debug(f"LLM response length: {len(result)} chars")
        return result
    except Exception as e:
        logger.error(f"LLM generate_text failed: {e}")
        raise


def classify_text(
    text: str,
    categories: List[str],
    model: str = None,
) -> Dict[str, float]:
    """
    Classify text into one or more categories using the LLM.

    Args:
        text: Text to classify.
        categories: List of category labels.

    Returns:
        Dict mapping each category to a confidence score (0.0 - 1.0).
    """
    client = _get_client()
    model = model or LLM_MODEL

    categories_str = ", ".join(categories)
    system_prompt = (
        "You are a text classifier. Given the text and categories, "
        "return a JSON object mapping each category to a confidence score "
        "between 0.0 and 1.0. Only output valid JSON, nothing else."
    )
    user_prompt = (
        f"Categories: {categories_str}\n\n"
        f"Text to classify:\n{text}\n\n"
        f"Return JSON with confidence scores for each category."
    )

    logger.info(f"LLM classify_text: {len(categories)} categories")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=256,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()

        # Parse JSON response
        import json
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        logger.debug(f"Classification result: {result}")
        return result
    except Exception as e:
        logger.error(f"LLM classify_text failed: {e}")
        # Return uniform scores as fallback
        uniform = 1.0 / len(categories) if categories else 0.0
        return {cat: uniform for cat in categories}


def summarize_text(
    text: str,
    max_length: int = 200,
    model: str = None,
) -> str:
    """
    Summarize text into a concise version.

    Args:
        text: Text to summarize.
        max_length: Approximate max length of summary in words.
        model: Override model name.

    Returns:
        Summarized text string.
    """
    system_prompt = (
        f"You are a concise summarizer. Summarize the given text in "
        f"no more than {max_length} words. Be direct and factual."
    )

    logger.info(f"LLM summarize_text: input {len(text)} chars, max {max_length} words")
    return generate_text(
        prompt=f"Summarize this text:\n\n{text}",
        system_prompt=system_prompt,
        max_tokens=max_length * 2,  # rough token estimate
        temperature=0.3,
        model=model,
    )
