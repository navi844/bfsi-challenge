"""Simple pricing helper: USD per million tokens for input/output.

This module contains conservative example prices for the models used in
this project and a helper to compute cost from token counts.
"""
from typing import Dict

# Prices are USD per 1,000,000 tokens. Values are illustrative.
PRICING_PER_MILLION: Dict[str, Dict[str, float]] = {
    # model: {"input": usd_per_million, "output": usd_per_million}
    "gpt-4o-mini": {"input": 3.50, "output": 7.00},
    "gpt-4o": {"input": 6.00, "output": 12.00},
    "gpt-4o-mini-preview": {"input": 2.50, "output": 5.00},
    # fallback/default
    "default": {"input": 3.50, "output": 7.00},
}


def compute_cost_usd(prompt_tokens: int, completion_tokens: int, model: str | None = None) -> float:
    """Compute approximate USD cost given token counts for prompt and completion.

    Returns a float cost in USD.
    """
    model_key = (model or "default").lower()
    prices = PRICING_PER_MILLION.get(model_key, PRICING_PER_MILLION["default"])

    input_cost = (prompt_tokens or 0) * (prices["input"] / 1_000_000)
    output_cost = (completion_tokens or 0) * (prices["output"] / 1_000_000)
    return round(input_cost + output_cost, 8)
