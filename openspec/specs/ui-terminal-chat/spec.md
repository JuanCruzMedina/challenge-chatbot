# ui-terminal-chat Specification

## Purpose
Defines the terminal chat: a passive loop that forwards what a person types to the agent and prints what comes back.

## Requirements

### Requirement: The terminal chat only forwards and prints
The terminal chat SHALL send each line the person types, with the conversation so far, to the agent and print the agent's reply followed by the name of each tool the agent called in that turn. It MUST NOT inspect the text of a message to decide anything other than whether it is the exit command, and MUST NOT call the knowledge flow or an MCP tool by itself.

#### Scenario: A reply is printed with the tools that were called
- **GIVEN** an agent that calls `query_knowledge` and replies "tracking-team owns it"
- **WHEN** the person types a question
- **THEN** the reply is printed
- **AND** a line names `query_knowledge` as called in that turn

#### Scenario: A turn with no tool prints only the reply
- **GIVEN** an agent that replies "Hello!" without tools
- **WHEN** the person types "hi"
- **THEN** only the reply is printed

#### Scenario: The terminal chat has no routing of its own
- **GIVEN** the source of the chat package
- **WHEN** it is checked for imports of the actions or knowledge packages and for string inspection of messages
- **THEN** none is found

### Requirement: The conversation is kept between turns
The terminal chat SHALL pass the earlier messages and replies of the session to the agent on every turn, and MUST end the session on `/exit`, on an empty end of input, or on an interrupt, closing the MCP server.

#### Scenario: The second turn receives the first
- **GIVEN** two lines typed in one session
- **WHEN** the second turn runs
- **THEN** the agent receives the first question, its reply and the second question

#### Scenario: Leaving closes everything
- **GIVEN** a session in progress
- **WHEN** the person types `/exit`
- **THEN** the loop ends and no MCP server process remains

### Requirement: Failures are shown as messages, not tracebacks
When the model server is unavailable or the model cannot call tools, the terminal chat SHALL print the message of the error and keep the session open. Other exceptions MUST NOT be hidden.

#### Scenario: An unreachable model keeps the session alive
- **GIVEN** an agent whose model server is down
- **WHEN** the person types a question
- **THEN** the message that says to run `ollama serve` is printed
- **AND** the next line typed is still processed

#### Scenario: A bug is not disguised
- **GIVEN** an agent that raises an unexpected exception
- **WHEN** the person types a question
- **THEN** the exception reaches the caller

### Requirement: A missing workspace is reported before the chat starts
The terminal chat SHALL exit with a message telling the person to run `uv run python scripts/seed_workspace.py` when the workspace does not exist.

#### Scenario: No workspace
- **GIVEN** no workspace folder
- **WHEN** the terminal chat starts
- **THEN** it exits with code 2 and prints the seed command
