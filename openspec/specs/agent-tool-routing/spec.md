# agent-tool-routing Specification

## Purpose
Defines the agent that receives a person's messages and decides, by tool-calling alone, whether to answer from the informational flow, perform an action through the MCP Server, do both, or just reply; and that adapts to new MCP tools without any change to its own logic.

## Requirements

### Requirement: The agent has one knowledge tool and the tools of the MCP Server
The agent SHALL expose to its model exactly one knowledge tool, `query_knowledge`, backed by the informational flow, plus every tool that the MCP Server lists when the agent starts. Each MCP tool MUST keep its name, its description and its input schema as the server declares them. No MCP tool name MAY appear in the agent's source.

#### Scenario: The tool set is the knowledge tool plus the discovered tools
- **GIVEN** an MCP Server with its three default tools
- **WHEN** the agent starts
- **THEN** its tools are `query_knowledge`, `add_document`, `update_document` and `mark_document_obsolete`
- **AND** each MCP tool carries the description and the input schema listed by the server

#### Scenario: The agent source names no MCP tool
- **GIVEN** the source of the agent package
- **WHEN** it is searched for the names of the server's tools
- **THEN** none is found

### Requirement: The model alone chooses the route
The agent SHALL run a loop in which the model receives the conversation and the tools, and either replies or asks for tools; the agent MUST execute exactly the tools the model asked for, with the arguments it gave, and MUST NOT choose, skip, reorder or add tools by inspecting the text of the user's message. The agent MUST end the turn when the model replies without asking for a tool.

#### Scenario: A question is answered through the knowledge tool only
- **GIVEN** a model that asks for `query_knowledge` and then replies
- **WHEN** the person asks a question
- **THEN** the knowledge flow runs once, no MCP tool runs, and the reply is returned

#### Scenario: An action request runs the MCP tool the model asked for
- **GIVEN** a model that asks for `add_document` with arguments and then replies
- **WHEN** the person asks for a document to be created
- **THEN** that MCP tool runs with those arguments, the document exists in the workspace, and the knowledge flow does not run

#### Scenario: A request that needs both runs them in the order the model chose
- **GIVEN** a model that asks for `query_knowledge`, then for an MCP tool, then replies
- **WHEN** the person asks to look something up and then act on it
- **THEN** the tools run in that order and the reply is returned

#### Scenario: A turn that needs no tool calls no tool
- **GIVEN** a model that replies at once
- **WHEN** the person greets the agent
- **THEN** no tool runs and the model's reply is returned

#### Scenario: The route does not depend on the words of the message
- **GIVEN** the same model output and two different user messages
- **WHEN** the agent runs both
- **THEN** it executes the same tools in both cases

#### Scenario: The loop has two nodes and routes only on the model's tool requests
- **GIVEN** the agent's loop
- **WHEN** its structure is inspected
- **THEN** it has a model step and a tools step, and the only branch is whether the model's last message asks for tools

### Requirement: MCP tools are discovered at runtime
The agent SHALL build its MCP tools from the listing the server returns, and MUST offer a refresh that lists them again. A tool added to the server MUST become callable by the agent with its own schema, and a tool removed MUST disappear, without any change to the agent's code.

#### Scenario: A tool added to the server is available to the agent
- **GIVEN** a server started with a tools package that has one more tool than the default
- **WHEN** the agent starts
- **THEN** the new tool is among the agent's tools with the schema the server declares, and the model can call it

#### Scenario: A refresh sees changes in the server's tools
- **GIVEN** a running agent and a server whose tool list changes
- **WHEN** the agent refreshes its tools
- **THEN** added tools appear and removed tools are gone

### Requirement: Failures go back to the model
When a tool fails, the agent SHALL return the failure to the model as a tool message instead of raising: an MCP error result with its message, an arguments error, or a call to a tool that does not exist. A normal result that reports a conflict MUST also reach the model unchanged. The agent MUST stop a turn after six tool calls with a reply that says so.

#### Scenario: An MCP error is shown to the model
- **GIVEN** a model that asks for an MCP tool with an invalid argument
- **WHEN** the tool fails
- **THEN** the model receives the error message as a tool message and can try again or explain

#### Scenario: A conflict outcome is passed on as a result
- **GIVEN** an update whose passage is no longer in the document
- **WHEN** the tool returns the conflict outcome
- **THEN** the model receives the outcome and its reason unchanged

#### Scenario: A tool that does not exist is reported to the model
- **GIVEN** a model that asks for a tool the agent does not have
- **WHEN** the agent processes the request
- **THEN** the model receives an error naming the available tools, and nothing runs

#### Scenario: The number of tool calls in a turn is capped
- **GIVEN** a model that keeps asking for tools
- **WHEN** it reaches six tool calls in one turn
- **THEN** the agent stops and replies that it reached the limit

### Requirement: The knowledge tool reflects the current documents
Before answering, the knowledge tool SHALL refresh the knowledge graph and the document index from the data it reads, so that a document created or changed since the previous question is searchable. It MUST NOT modify the data.

#### Scenario: A document created through the MCP tools is found by the next question
- **GIVEN** a document added to the workspace through an MCP tool
- **WHEN** the knowledge tool is asked about its content
- **THEN** the answer evidence includes that document

#### Scenario: Asking changes nothing in the data
- **GIVEN** a checksum of every file under the data root
- **WHEN** knowledge questions are asked
- **THEN** the checksum is unchanged

### Requirement: Action and knowledge paths stay separate
The agent SHALL perform actions only through the MCP client and MUST NOT import the actions package or write to the data itself. The informational flow MUST NOT call MCP tools, and the MCP Server MUST NOT receive knowledge questions.

#### Scenario: The agent does not import the actions package
- **GIVEN** the source of the agent package
- **WHEN** its imports are inspected
- **THEN** none refers to the actions package

#### Scenario: A knowledge question leaves no trace in the actions audit log
- **GIVEN** an empty audit log of the actions server
- **WHEN** a question is answered through the knowledge tool
- **THEN** the audit log is still empty

### Requirement: Conversations are plain data and model problems are reported
The agent SHALL accept the messages of a conversation and return the reply together with a record of the tools it called and their results, as plain data. A model that cannot be reached MUST produce an error that says how to start it, and a model that does not support tool-calling MUST produce an error that names the model; neither is replaced by another model.

#### Scenario: A turn returns the reply and the record of tool calls
- **GIVEN** a turn in which two tools ran
- **WHEN** the result is serialized to JSON
- **THEN** it contains the reply and, for each tool, its name, arguments and result

#### Scenario: An unreachable model is reported with how to start it
- **GIVEN** a model server that is not running
- **WHEN** the agent handles a message
- **THEN** it raises an error that says how to start the server

### Requirement: Routing quality is measured
The project SHALL include evaluation turns, each with the tools the agent is expected to call (or none) and, for actions, the effect expected on the workspace, and a script that runs them and reports per turn and overall whether the agent called the right tools and produced the right effect. The script MUST exit with a failure status when the overall rate is below a minimum given on the command line, and MUST count a call to an action tool on a question as a failure.

#### Scenario: The report is per turn and overall
- **GIVEN** the evaluation set and a scripted model
- **WHEN** the script runs
- **THEN** it prints one line per turn with its verdict and an overall rate

#### Scenario: An action tool called for a question is a failure
- **GIVEN** a question turn and a model that asks for an action tool
- **WHEN** the turn is graded
- **THEN** it fails and the reason names the tool

#### Scenario: A rate below the minimum fails the run
- **GIVEN** a minimum rate above what the run achieves
- **WHEN** the script runs
- **THEN** it exits with a failure status

### Requirement: The prompt tells the model to act on confirmations and to check conflicts
The system prompt SHALL state that a confirmation from the person is the order to act and that asking again is only for a value a tool requires and is unknown; that a fact the person gives about owners, leads or other documented data is checked with the knowledge tool before writing and the person is asked only when it contradicts the documentation; and that write tools handle markdown documents only. It MUST name no MCP tool.

#### Scenario: The prompt carries the rules and names no tool
- **GIVEN** the system prompt and the real server's tool list
- **WHEN** the prompt is checked
- **THEN** it contains the confirmation, conflict and markdown-only rules
- **AND** no MCP tool name appears in it

#### Scenario: After a confirmation the scripted model writes in the same turn
- **GIVEN** a conversation where the person has confirmed a proposal, and a scripted model that calls `append_to_document`
- **WHEN** the turn runs
- **THEN** the tool runs once, the file has the text and the reply reports it

### Requirement: The knowledge tool returns passages that can be quoted for an edit
The `query_knowledge` result SHALL include the passages of the answer, and the system prompt SHALL tell the model to quote the text to replace from them when changing an existing document, to ask again for the section when it is not among them, and never to invent it. The prompt MUST still name no MCP tool.

#### Scenario: The tool result includes the passages
- **GIVEN** a question answered with document evidence
- **WHEN** the agent runs `query_knowledge`
- **THEN** the tool message has a `passages` list with exact text

#### Scenario: A scripted turn edits a document using a quoted passage
- **GIVEN** a scripted model that asks the knowledge tool for a section and then calls the update tool with text copied from a returned passage
- **WHEN** the turn runs
- **THEN** the update succeeds and the file has the new text

#### Scenario: The prompt carries the rule and names no tool
- **GIVEN** the system prompt and the real server's tool list
- **WHEN** the prompt is checked
- **THEN** it has the quoting rule and no MCP tool name appears in it

### Requirement: Missing data is written, not confirmed
The system prompt SHALL say that a fact the documentation does not mention is new and is written without asking; only a contradiction is asked about. The prompt MUST still name no MCP tool.

#### Scenario: The prompt separates a gap from a contradiction
- **GIVEN** the system prompt
- **WHEN** it is checked
- **THEN** it says that missing data is not a conflict and that it names no MCP tool

### Requirement: A preview is shown and confirmed before it is repeated
The system prompt SHALL tell the model that when a tool returns a preview that needs confirmation it must show it to the person and wait, and repeat the call as the tool says only after the person agrees. The prompt MUST still name no MCP tool.

#### Scenario: The prompt has the preview rule
- **GIVEN** the system prompt
- **WHEN** it is checked
- **THEN** it has the preview rule and names no MCP tool

#### Scenario: A scripted turn previews, waits and then writes
- **GIVEN** a scripted model that asks for an edit, shows the preview and, after a "yes", repeats the call confirmed
- **WHEN** the two turns run on the real server
- **THEN** the file changes only in the second turn
