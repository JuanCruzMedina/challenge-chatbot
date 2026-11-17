# Design

## Context

- Two places use a model: the informational flow through the `LLM` port (`complete`, `complete_json`, built by `llm_from_env`) and the agent through a LangChain chat model with tool calling (`chat_model_from_env`, with `translate_model_error`). Both read their provider from the environment, so adding one does not touch agent or flow logic (D9).
- D9 (`docs/design-decisions.md`) already accepted the API as an opt-in alternative: Claude Haiku 5.5 (`claude-haiku-5-5`), $0.10 per million input tokens and $0.50 per million output tokens, a cap in code (proposal: $1.00 total), tests without the real model, real calls announced first. Behavior contract: `specs/platform-anthropic-provider/spec.md`.
- Probes done before this proposal (throwaway, outside the repo): the bare `anthropic` SDK authenticates with the `ant auth login` session when no key has a value, and refreshes the token itself; `langchain-anthropic` 1.7.10 passes `api_key=SecretStr('')`, which makes the SDK send `Bearer ` and fail; overriding `_client_params` to drop an empty key fixed sync, async and tool calling.
- The user's machine froze with Ollama running next to the tests; with the API nothing heavy runs locally.

## Goals / Non-Goals

**Goals:** switch both uses of a model with one variable; make overspending impossible by construction; keep the code free of provider `if/else` outside the settings.

**Non-Goals:** streaming, caching, batch, thinking, other providers or models, key management.

## Decisions

**D-1. Provider chosen only in the settings.** `llm_from_env` gets a third branch, `anthropic`, and `PROVIDERS` lists it. `chat_model_from_env` in `agent/settings.py` reads `LLM_PROVIDER` too and returns the Anthropic chat model or the Ollama one. This is the "one place" D9 promised; the agent and the flow still see only a port and a chat model.

**D-2. The flow adapter, `AnthropicLLM`.** Same shape as `OllamaLLM`: `complete` is a plain message call; `complete_json` asks for output that follows the schema and parses it with the shared `parse_json_object`. How to ask for schema-following output (structured outputs, a forced tool, or a JSON instruction) is confirmed by a probe in task 1.2 against the installed SDK, and recorded in the module docstring; the choice must keep the `LLMOutputError` behavior when the text is not valid JSON. Temperature 0 where the model allows it. A short, fixed `max_tokens` per call keeps the output cost bounded.

**D-3. The agent's chat model, `SessionChatAnthropic`, lives in `llm/anthropic_chat.py`.** The architecture tests already forbid `anthropic` imports in the agent, flow, knowledge and retrieval packages, so every Anthropic-specific module (adapter, chat model, error translation, ledger, prices) sits in the `llm` package, next to the Ollama one; `agent/settings.py` only imports from `llm` and never from the SDK. A subclass of `ChatAnthropic` whose `_client_params` drops `api_key` when it is empty (the fix probed above). `_client_params` is private API of `langchain-anthropic`, so the dependency is pinned with `~=` and a test asserts the behavior, so an update that changes it fails a free test instead of failing a user.

**D-4. Price table and the allowed models.** `llm/pricing.py` holds a dictionary from model id to (input, output) price per million tokens, with the date they were taken. Task 1.2 verifies the Haiku 5.5 prices against the installed Claude API reference before they are written. A model not in the table is refused at creation. Adding Sonnet or Opus means adding a line, a deliberate change (D9: not without approval).

**D-5. The ledger and the guard.** `llm/ledger.py`: a JSON file (`.cost_ledger.json`, already git-ignored, path overridable by `ANTHROPIC_LEDGER`) with total input tokens, output tokens and estimated cost, written atomically (temp file and rename) under a file lock so the MCP-free flow and the agent in the same process, or two processes, do not lose updates. `check()` raises `BudgetExceededError` when the total has reached the cap; `record(model, usage)` adds a call. The flow adapter calls `check` before and `record` after each request. For the chat model, a LangChain callback does the same: `check` in `on_chat_model_start`, `record` in `on_llm_end` from `usage_metadata`. `BudgetExceededError` is a subclass of the model-unavailable errors, so both paths show its message without new handling. The estimate counts only input and output tokens; cache and thinking tokens are not used, so it is an estimate, not an invoice, and the Console limit remains the only real guarantee (D9 control 1).

**D-6. Error translation.** The flow adapter maps `anthropic.AuthenticationError`, `PermissionDeniedError`, `RateLimitError`, `InternalServerError` and overloaded responses, and `APIConnectionError`/`APITimeoutError` to `LLMUnavailableError` with a message that says what to do. The class-to-message mapping lives in `llm` (`anthropic_errors`, shared by both paths); `translate_model_error` in `agent/settings.py` calls it for these classes and keeps its Ollama mappings, with no import of the SDK. Anything else is returned untouched.

**D-7. Tests cannot reach the API.** `tests/conftest.py` sets `ANTHROPIC_BASE_URL` to `http://127.0.0.1:9` (discard port) for the whole suite and clears `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and `LLM_PROVIDER` so the developer's `.env` and login cannot leak in. Adapter tests inject a fake client or use `httpx` mock transports. A test proves that a real client created in the suite fails to connect.

**D-8. The live check.** `scripts/live_check.py` prints which calls it will make and their estimated cost, and runs only with `LIVE_LLM=1` and `--yes`: one flow call, one agent call and one tool call, a few hundred tokens in total. It prints the tokens used and the ledger total afterwards. It is the only way this change makes real calls.

**D-9. Which model for which use.** Haiku 5.5 for both by default. Separate overrides (`ANTHROPIC_MODEL`) are not added until a need is measured.
