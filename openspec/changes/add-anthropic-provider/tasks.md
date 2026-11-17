# Tasks

## 1. Setup and API check

- [ ] 1.1 Dry-run `uv add "langchain-anthropic~=1.7"`; report what it adds or changes. If it touches `mcp`, `langgraph` or `chromadb`, stop and report. Then add it, run the whole suite and the data validator, and report the `uv.lock` changes.
- [ ] 1.2 With throwaway scripts outside the repo, using the user's login session and at most ten tiny calls (announce the count first), confirm: how to get schema-following JSON from `claude-haiku-5-5` with the installed SDK (and what the response and `usage` fields look like); that `temperature=0` is accepted; the exception classes for authentication, rate limit, overload and connection errors; that `ChatAnthropic.bind_tools` plus a tool call works through the subclass; and the Haiku 5.5 prices from the Claude API reference in the installed skill. Record the facts in the docstrings of the new modules.
- [ ] 1.3 Create the skeleton `llm/{anthropic_llm,pricing,ledger}.py` and `agent/anthropic_chat.py` (docstrings only) and the test folders.

## 2. Pricing and the ledger

- [ ] 2.1 Write failing tests for the price table (default model present, unknown model refused with its name, cost computation from tokens) and the ledger (records add up across `record` calls from two instances, survives reopening, `check` raises exactly when the total reaches the cap and not before, the cap is configurable and invalid values fail with the variable's name, a concurrent write does not lose an update, the file is written atomically).
- [ ] 2.2 Implement `pricing.py` and `ledger.py`; make 2.1 pass.

## 3. The flow adapter

- [ ] 3.1 Write failing tests with a fake client for `AnthropicLLM`: `complete` returns text, `complete_json` returns the object and raises `LLMOutputError` on invalid JSON, the guard refuses a call before sending when the cap is reached (the fake client records no request), usage is recorded after a call, and each failure class becomes `LLMUnavailableError` with the advice, while an unexpected exception passes through.
- [ ] 3.2 Implement `AnthropicLLM`; make 3.1 pass.

## 4. The agent's chat model

- [ ] 4.1 Write failing tests for `SessionChatAnthropic`: an empty key is dropped from the client parameters, a non-empty key is kept, a model without a price is refused, the guard refuses before a request and usage is recorded from `usage_metadata` (fake transport), and a rate-limit error becomes `AgentModelError` with the advice while a bug propagates.
- [ ] 4.2 Implement the chat model, the callback and the extra mappings in `translate_model_error`; make 4.1 pass.

## 5. Selection and test safety

- [ ] 5.1 Write failing tests for `LLM_PROVIDER`: `anthropic` gives the adapter and the chat model without any network call, the default stays Ollama, an unknown value lists the providers (flow and agent), and a real client created in the suite fails to connect while `ANTHROPIC_API_KEY`, `LLM_PROVIDER` and the login cannot leak in.
- [ ] 5.2 Implement the branches in `llm/settings.py` and `agent/settings.py` and the `tests/conftest.py` safety; make 5.1 pass. Run the whole suite and confirm it stays green with the user's real `.env` present.
- [ ] 5.3 Isolation test: no module outside the settings and the provider modules mentions `anthropic` or branches on the provider; mutation-check it.

## 6. The live check

- [ ] 6.1 Write failing tests for `scripts/live_check.py` with fake clients: without `LIVE_LLM=1` or without `--yes` it makes no call and says what to set; with both it prints the estimate first, makes its calls, then prints tokens used and the ledger total.
- [ ] 6.2 Implement it and make 6.1 pass.
- [ ] 6.3 (Needs the user's explicit go; the estimate is announced first.) Run `LIVE_LLM=1 uv run python scripts/live_check.py --yes` once and record what it measured. If it is not run, mark it skipped and say so in the documentation.

## 7. Documentation and integration

- [ ] 7.1 Update D9 (what was built, the verified authentication facts, the cap and how to change it, the estimate versus invoice caveat), `docs/agent.md` and `docs/chat-ui.md` (how to run with `LLM_PROVIDER=anthropic`; no local model needed), and `AGENTS.md`/the roadmap. Verify that every documented command exists.
- [ ] 7.2 Run the whole suite, the data validator and `openspec validate add-anthropic-provider --strict`; verify every `#### Scenario:` has a test and list the mapping in the closing report.
