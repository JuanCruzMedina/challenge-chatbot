"""The persistent spending ledger and its cap (design.md D-5).

One JSON file shared by every path that calls the Anthropic API (the flow and the agent). It keeps token totals per
model; the cost is computed from the price table, so it is an estimate of input and output tokens only, not an
invoice. The only real guarantee is the spending limit in the Anthropic Console (D9).
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from ecosystem_assistant.llm.port import LLMUnavailableError
from ecosystem_assistant.llm.pricing import cost_decimal

DEFAULT_CAP_USD = 1.0
DEFAULT_LEDGER_PATH = ".cost_ledger.json"


class BudgetExceededError(LLMUnavailableError):
    """The spending cap is reached (or the ledger cannot be trusted), so no more calls are made."""


@dataclass(frozen=True)
class Total:
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


def cap_from_env(env: Mapping[str, str]) -> float:
    raw = env.get("ANTHROPIC_MAX_USD")
    if not raw:
        return DEFAULT_CAP_USD
    try:
        cap = float(raw)
    except ValueError:
        cap = float("nan")
    if not math.isfinite(cap) or cap <= 0:
        raise ValueError(f"ANTHROPIC_MAX_USD must be a positive number of US dollars, got {raw!r}")
    return cap


class Ledger:
    def __init__(self, path: Path | str, cap_usd: float = DEFAULT_CAP_USD) -> None:
        self.path = Path(path)
        self.cap_usd = cap_usd

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Ledger":
        env = os.environ if env is None else env
        return cls(env.get("ANTHROPIC_LEDGER") or DEFAULT_LEDGER_PATH, cap_from_env(env))

    # --- reading -------------------------------------------------------------------------------------

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"models": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data.get("models"), dict):
                raise ValueError("no models table")
            return data
        except (ValueError, OSError) as exc:
            raise BudgetExceededError(
                f"The spending ledger {self.path} cannot be read ({exc}). Calls are stopped so the total is not "
                f"lost. Fix or delete the file if you are sure, or set ANTHROPIC_LEDGER to another path."
            ) from exc

    def _cost(self, data: dict[str, Any]) -> Decimal:
        return sum((cost_decimal(model, t["input_tokens"], t["output_tokens"])
                    for model, t in data["models"].items()), Decimal(0))

    def total(self) -> Total:
        data = self._read()
        models = data["models"].values()
        return Total(
            calls=sum(t["calls"] for t in models),
            input_tokens=sum(t["input_tokens"] for t in models),
            output_tokens=sum(t["output_tokens"] for t in models),
            cost_usd=float(self._cost(data)),
        )

    # --- the guard -----------------------------------------------------------------------------------

    def check(self) -> None:
        """Raise before a call is sent when the recorded cost has reached the cap."""
        spent = self._cost(self._read())
        if spent >= Decimal(str(self.cap_usd)):
            raise BudgetExceededError(
                f"The Anthropic spending cap is reached: estimated ${spent:f} of ${self.cap_usd:g} "
                f"(ledger: {self.path}). No call was sent. Raise the cap with ANTHROPIC_MAX_USD, or reset the ledger "
                f"by deleting that file, if you decide to spend more."
            )

    # --- writing -------------------------------------------------------------------------------------

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path.with_name(self.path.name + ".lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Add one call. The model must have a price. The file is replaced atomically under a lock."""
        cost_decimal(model, input_tokens, output_tokens)  # validates the model and the counts before touching disk
        with self._locked():
            data = self._read()
            entry = data["models"].setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
            entry["calls"] += 1
            entry["input_tokens"] += input_tokens
            entry["output_tokens"] += output_tokens
            data["calls"] = sum(t["calls"] for t in data["models"].values())
            data["estimated_cost_usd"] = float(self._cost(data))
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name + ".")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, indent=2)
                os.replace(tmp, self.path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
