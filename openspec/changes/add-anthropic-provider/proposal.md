# Proposal

## Why

The local model (`qwen2.5:7b-instruct` on Ollama) made the user's 18 GB machine freeze while running the suite, tests and `langgraph dev`, and it is also the weakest link for tool routing. The user wants to use Claude through the Anthropic API. D9 in `docs/design-decisions.md` already accepted that as an opt-in alternative, with Haiku 5.5 and spending controls. This change builds it.

## What Changes

- Add `LLM_PROVIDER=anthropic`. One variable switches **both** places that use a model: the informational flow (the `LLM` port) and the agent's chat model. The default stays `ollama`, so nothing spends money by surprise.
- Add an Anthropic adapter for the flow (`complete`, `complete_json` with the flow's JSON schemas) and an Anthropic chat model for the agent's tool-calling, built on `langchain-anthropic`.
- Authentication: `ANTHROPIC_API_KEY` if it has a value, otherwise the session of `ant auth login`. Checked with probes: the bare SDK uses the session, but `langchain-anthropic` sends an empty key and fails, so a small subclass omits an empty key.
- Add the spending controls of D9: only models with a known price are accepted (default `claude-haiku-5-5`), and a persistent ledger of tokens and estimated cost that **refuses** the next call once the cap is reached (default $1.00, `ANTHROPIC_MAX_USD`). Both paths share one ledger.
- Translate Anthropic failures (no credentials, rate limit, overload, no connection, cap reached) into the existing messages that say what to do.
- Make accidental spending in tests impossible: every automated test runs with the API pointed at an unroutable address.
- Add `scripts/live_check.py`, which makes a few tiny real calls only with `LIVE_LLM=1` and `--yes`, and prints the estimated cost first.

Invariants restated: the agent and the flow still know only their ports; routing stays the model's; no `if/else` on providers inside agent or flow logic, only in the settings that build the model.

## Capabilities

### New Capabilities
- `platform-anthropic-provider`: provider selection, authentication, price table, spending cap, error messages, test safety.

### Modified Capabilities
<!-- None: Ollama behavior is unchanged. -->

## Impact

- New `llm/anthropic_llm.py`, `llm/anthropic_chat.py`, `llm/pricing.py`, `llm/ledger.py`, edits in `llm/settings.py` and `agent/settings.py`, `scripts/live_check.py`, tests, and D9, `docs/agent.md`, `docs/chat-ui.md`.
- New dependency `langchain-anthropic` (pinned with `~=`; it brings the `anthropic` SDK). Dry run before installing.
- Money: automated tests cost nothing. Real calls are the user's, each batch announced with its estimate.

## Non-goals

- Streaming, prompt caching, batch API, extended thinking.
- Other providers, Sonnet or Opus models (they need a price entry and the user's explicit approval).
- Running the real routing evaluation (offered afterwards, with its estimate).
- Managing API keys: the user owns the key or the login.
