"""Spec: only models with a known price are used, and the cost estimate follows the table."""
from __future__ import annotations

import pytest

from ecosystem_assistant.llm.pricing import DEFAULT_MODEL, PRICES, UnknownModelError, estimate_cost, price_for


def test_the_default_model_is_the_cheapest_current_one_and_has_a_price() -> None:
    assert DEFAULT_MODEL == "claude-haiku-5-5"
    price = price_for(DEFAULT_MODEL)
    assert (price.input_per_mtok, price.output_per_mtok) == (0.10, 0.50)


def test_cost_is_tokens_times_the_price_per_million() -> None:
    assert estimate_cost("claude-haiku-5-5", 1_000_000, 0) == pytest.approx(0.10)
    assert estimate_cost("claude-haiku-5-5", 0, 1_000_000) == pytest.approx(0.50)
    assert estimate_cost("claude-haiku-5-5", 18_000, 1_500) == pytest.approx(0.00255)
    assert estimate_cost("claude-haiku-5-5", 0, 0) == 0


def test_a_model_without_a_price_is_refused_and_named() -> None:
    with pytest.raises(UnknownModelError, match="claude-sonnet-5-5") as exc:
        price_for("claude-sonnet-5-5")
    assert "pricing" in str(exc.value).lower()  # says where prices are added


def test_only_haiku_is_priced_so_a_pricier_model_needs_a_deliberate_edit() -> None:
    assert list(PRICES) == ["claude-haiku-5-5"]


def test_negative_token_counts_are_rejected() -> None:
    with pytest.raises(ValueError):
        estimate_cost("claude-haiku-5-5", -1, 0)
