"""A few tiny real calls to the Anthropic API, to see that everything works end to end (design.md D-8).

This is the only place in the project that makes real calls on purpose, so it needs two opt-ins:

  LIVE_LLM=1 uv run python scripts/live_check.py --yes

It prints the estimated cost before anything is sent, then makes three calls with the models the project really uses
(one flow call asking for JSON, one plain agent reply, one agent tool call), and prints the tokens used and the
ledger total. Authentication is ANTHROPIC_API_KEY if it has a value, otherwise the `ant auth login` session.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from typing import Any

from langchain_core.tools import tool

EST_CALLS, EST_INPUT_TOKENS, EST_OUTPUT_TOKENS = 3, 500, 200   # deliberately above what the three calls use
FLOW_SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"],
               "additionalProperties": False}


@tool
def ping(x: str) -> str:
    """Return x unchanged."""
    return x


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None, llm: Any | None = None,
         chat: Any | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="confirm that real calls may be made and paid")
    args = parser.parse_args(argv)
    env = os.environ if env is None else env

    if env.get("LIVE_LLM") != "1" or not args.yes:
        print("No call was made. Real calls need both opt-ins: set LIVE_LLM=1 and pass --yes, for example:\n"
              "  LIVE_LLM=1 uv run python scripts/live_check.py --yes")
        return 2

    from ecosystem_assistant.llm.anthropic_chat import anthropic_chat_model
    from ecosystem_assistant.llm.anthropic_llm import AnthropicLLM
    from ecosystem_assistant.llm.ledger import Ledger
    from ecosystem_assistant.llm.pricing import estimate_cost, model_from_env

    ledger = Ledger.from_env(env)
    llm = llm or AnthropicLLM(model=env.get("ANTHROPIC_MODEL") or None, ledger=ledger)
    chat = chat or anthropic_chat_model(model=env.get("ANTHROPIC_MODEL") or None, ledger=ledger)
    ledger = llm.ledger
    model = model_from_env(env)
    before = ledger.total()
    estimate = estimate_cost(model, EST_INPUT_TOKENS, EST_OUTPUT_TOKENS)
    print(f"About to make {EST_CALLS} real calls to {model}: up to ~{EST_INPUT_TOKENS} tokens in and "
          f"~{EST_OUTPUT_TOKENS} out.\nEstimated cost: about ${estimate:.5f}. "
          f"Spent so far: ${before.cost_usd:.5f} of the ${ledger.cap_usd:g} cap ({ledger.path}).")

    failures = 0

    def check(label: str, action) -> None:
        nonlocal failures
        try:
            print(f"{label}: PASS - {action()}")
        except Exception as exc:  # a diagnostic script: show what failed, keep going
            failures += 1
            print(f"{label}: FAIL - {type(exc).__name__}: {str(exc)[:160]}")

    def flow() -> str:
        result = llm.complete_json("Answer in JSON.", "Say hello in one word.", FLOW_SCHEMA)
        assert isinstance(result.get("answer"), str), result
        return f"JSON with an answer ({result['answer'][:30]!r})"

    def agent_reply() -> str:
        return f"reply {chat.invoke('Reply with: ok').content[:30]!r}"

    def agent_tool() -> str:
        message = chat.bind_tools([ping]).invoke("Call the ping tool with x=hi.")
        assert message.tool_calls and message.tool_calls[0]["name"] == "ping", message.content
        return f"tool call {message.tool_calls[0]['name']}({message.tool_calls[0]['args']})"

    check("flow:  complete_json", flow)
    check("agent: plain reply", agent_reply)
    check("agent: tool call", agent_tool)

    after = ledger.total()
    print(f"tokens used: {after.input_tokens - before.input_tokens} in, {after.output_tokens - before.output_tokens} out "
          f"({after.calls - before.calls} calls recorded)")
    print(f"ledger total: ${after.cost_usd:.5f} of the ${ledger.cap_usd:g} cap")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
