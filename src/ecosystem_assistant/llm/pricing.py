"""Prices per million tokens and the models the project may use (design.md D-4).

Haiku 5.5 prices ($0.10 input, $0.50 output, for prompts up to 100K tokens) were read from the Claude API
reference (cached 2026-11-03) in task 1.2. Beyond 100K tokens the price is higher; this project never gets there.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

DEFAULT_MODEL = "claude-haiku-5-5"


class UnknownModelError(ValueError):
    """The model has no price, so its cost cannot be limited. The message says how to add one."""


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok: float
    output_per_mtok: float


# Adding a model is a deliberate edit of this table (and needs the user's approval: D9).
PRICES: dict[str, ModelPrice] = {
    "claude-haiku-5-5": ModelPrice(input_per_mtok=0.10, output_per_mtok=0.50),
}


def price_for(model: str) -> ModelPrice:
    try:
        return PRICES[model]
    except KeyError:
        raise UnknownModelError(
            f"The model {model!r} has no price in ecosystem_assistant/llm/pricing.py, so its spending cannot be "
            f"limited. Known models: {', '.join(PRICES)}. To use another model, add its price to that table "
            f"(D9 in docs/design-decisions.md asks for approval before using a more expensive model)."
        ) from None


def cost_decimal(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Exact cost in US dollars (decimal arithmetic, so a cap comparison has no floating-point noise)."""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts cannot be negative")
    price = price_for(model)
    return (Decimal(input_tokens) * Decimal(str(price.input_per_mtok))
            + Decimal(output_tokens) * Decimal(str(price.output_per_mtok))) / Decimal(1_000_000)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimated cost in US dollars of one call (input and output tokens only: an estimate, not an invoice)."""
    return float(cost_decimal(model, input_tokens, output_tokens))


def model_from_env(env: Mapping[str, str] | None = None) -> str:
    """``ANTHROPIC_MODEL`` or the default; a model without a price is refused here, before any call."""
    env = os.environ if env is None else env
    model = env.get("ANTHROPIC_MODEL") or DEFAULT_MODEL
    price_for(model)
    return model
