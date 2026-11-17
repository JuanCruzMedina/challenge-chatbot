# Spec Delta

## Purpose

Defines how the project uses Claude through the Anthropic API as an opt-in alternative to the local model, with authentication that needs no code change, a hard spending cap and clear failures.

## ADDED Requirements

### Requirement: One variable selects the provider for every use of a model
`LLM_PROVIDER=anthropic` SHALL make both the informational flow and the agent use Anthropic models. Without the variable the provider MUST remain `ollama`. An unknown value MUST fail with a message listing the valid providers. Creating a model MUST NOT make any network call.

#### Scenario: Anthropic is selected for the flow and for the agent
- **GIVEN** `LLM_PROVIDER=anthropic`
- **WHEN** the flow's model and the agent's chat model are created
- **THEN** the first is the Anthropic adapter and the second an Anthropic chat model
- **AND** no network call was made

#### Scenario: The default does not change
- **GIVEN** no `LLM_PROVIDER`
- **WHEN** the models are created
- **THEN** both are the Ollama ones

### Requirement: Authentication uses a key if there is one, otherwise the login session
The Anthropic models SHALL authenticate with `ANTHROPIC_API_KEY` when it has a value and otherwise with the session created by `ant auth login`. An empty key MUST NOT be sent. When neither exists, the error MUST name both ways to authenticate.

#### Scenario: An empty key is not sent
- **GIVEN** `ANTHROPIC_API_KEY` empty
- **WHEN** the agent's chat model builds its client
- **THEN** the client is created without an API key, so the SDK resolves the session

#### Scenario: Missing credentials are explained
- **GIVEN** no key and no login session
- **WHEN** the provider reports an authentication failure
- **THEN** the message mentions `ANTHROPIC_API_KEY` and `ant auth login`

### Requirement: Only models with a known price are used
The provider SHALL default to `claude-haiku-5-5`, allow `ANTHROPIC_MODEL` to choose another model only if it has an entry in the price table, and refuse any other model with a message that explains how prices are added.

#### Scenario: The default is the cheapest model
- **GIVEN** no `ANTHROPIC_MODEL`
- **WHEN** the provider is created
- **THEN** its model is `claude-haiku-5-5`

#### Scenario: A model without a price is refused
- **GIVEN** `ANTHROPIC_MODEL` set to a model absent from the price table
- **WHEN** the provider is created
- **THEN** it fails and names the model

### Requirement: A spending cap refuses calls once reached
Every call made through the Anthropic provider, by the flow or by the agent, SHALL record its input and output tokens and their estimated cost in one persistent ledger. When the recorded total reaches the cap (default 1.00 US dollar, `ANTHROPIC_MAX_USD`), the next call MUST be refused before it is sent, with a message that states the total, the cap and how to change it.

#### Scenario: Calls from both paths add up in one ledger
- **GIVEN** a flow call and an agent call with known token counts
- **WHEN** both finish
- **THEN** the ledger holds the sum of their tokens and estimated cost

#### Scenario: The call after the cap is not sent
- **GIVEN** a ledger whose total equals the cap
- **WHEN** either path tries to call the model
- **THEN** the call is refused before any request is made and the message names the cap

#### Scenario: The ledger survives restarts
- **GIVEN** a recorded total
- **WHEN** a new process opens the ledger
- **THEN** the total is the same

### Requirement: Failures say what to do
Authentication failure, rate limit, overload and connection failure SHALL surface as the project's existing model errors (`LLMUnavailableError` for the flow, `AgentModelError` for the agent) with a message that says what to do. Other exceptions MUST NOT be disguised.

#### Scenario: A rate limit is explained
- **GIVEN** a model that raises a rate-limit error
- **WHEN** the agent runs a turn
- **THEN** it raises `AgentModelError` that says to wait and retry

#### Scenario: A bug is not disguised
- **GIVEN** a model that raises an unexpected exception
- **WHEN** the agent runs a turn
- **THEN** the exception reaches the caller

### Requirement: Automated tests cannot spend money
The test suite SHALL run with the Anthropic API address replaced by an unroutable one, and real calls SHALL be possible only through a script that requires `LIVE_LLM=1` and an explicit confirmation flag, and that prints its estimate first.

#### Scenario: An accidental real call fails to connect
- **GIVEN** the test environment
- **WHEN** code creates an Anthropic client and calls it
- **THEN** the call fails to connect instead of reaching the API

#### Scenario: The live check refuses to run without opt-in
- **GIVEN** `LIVE_LLM` unset, or no confirmation flag
- **WHEN** `scripts/live_check.py` runs
- **THEN** it makes no call and says what to set
