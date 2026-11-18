# knowledge-flow-answers Specification

## Purpose
Defines the centralized informational flow: a single entry that answers a question by planning graph queries, searching the documents, and synthesizing a cited answer from that evidence, with explicit statuses, fallbacks and an evaluation. It is the only informational path the agent will use.

## Requirements

### Requirement: Every question goes through one centralized pipeline
The flow SHALL answer every question by running the same stages in the same order: plan, graph queries, document search, answer, check. Document search MUST run for every question, including those the graph can answer. The answer MUST report which stages ran and what each produced.

#### Scenario: The stages run in order and are reported
- **GIVEN** a flow with a scripted language model
- **WHEN** a question is asked
- **THEN** the trace lists the stages plan, graph queries, document search, answer and check in that order, each with its outcome

#### Scenario: A question the graph can answer still searches the documents
- **GIVEN** a question whose plan contains graph queries only
- **WHEN** it is asked
- **THEN** a document search runs as well and its passages are part of the evidence

#### Scenario: A combined question uses and cites both sources
- **GIVEN** a question that needs an ownership fact from the graph and a procedure from a runbook
- **WHEN** it is asked
- **THEN** the evidence contains graph facts and document passages, and the answer cites at least one of each

### Requirement: The model plans graph queries from a fixed, validated catalog
The language model SHALL propose a plan: graph queries (a method and its entity arguments), optional document filters (client, application, service) and whether obsolete documents are wanted. The flow MUST accept only methods of the fixed catalog, run at most four graph queries, drop any query with unknown methods or wrong arguments (recording why), drop filters that name unknown clients, applications or services, and resolve entity names with the graph's tolerant name matching. Invalid output MUST be retried once; if it is still invalid the flow MUST continue with a document search alone.

#### Scenario: A valid plan is executed
- **GIVEN** a plan with a graph query for the consumers of `payments api`
- **WHEN** the flow runs
- **THEN** that query runs against the graph and its result appears in the evidence

#### Scenario: Unknown methods and bad arguments are dropped and recorded
- **GIVEN** a plan with a method outside the catalog and a query missing its required argument
- **WHEN** the flow runs
- **THEN** neither runs, both are listed in the trace as dropped with a reason, and the valid queries still run

#### Scenario: Too many queries are cut
- **GIVEN** a plan with six graph queries
- **WHEN** the flow runs
- **THEN** only the first four run and the trace says the rest were cut

#### Scenario: Unknown filters are dropped
- **GIVEN** a plan whose filter names a client that does not exist
- **WHEN** the flow runs
- **THEN** the search runs without that filter and the trace says it was dropped

#### Scenario: An invalid plan is retried once, then falls back to document search
- **GIVEN** a model that returns text that is not a valid plan, twice
- **WHEN** a question is asked
- **THEN** the model is asked a second time, and then the flow continues with a document search only and the status is `degraded`

### Requirement: Answers are grounded in numbered evidence with citations
The flow SHALL give the model the evidence as numbered items: graph facts `K1..` and document passages `D1..`. The answer MUST cite the items it uses. The check stage MUST remove citations that do not exist, resolve each valid citation to its source (graph source files or document path and heading), and set the grounded flag only when at least one valid citation remains.

#### Scenario: Valid citations are resolved to sources
- **GIVEN** an answer citing `K1` and `D2`
- **WHEN** the check stage runs
- **THEN** the result lists both citations resolved to their source files, and the answer is grounded

#### Scenario: Invented citations are removed
- **GIVEN** an answer citing `K1` and `D9` when only `D1` to `D3` exist
- **WHEN** the check stage runs
- **THEN** `D9` is removed, `K1` stays, and the trace records the removal

#### Scenario: An answer with no valid citation is flagged ungrounded
- **GIVEN** an answer that cites nothing valid while evidence exists
- **WHEN** the check stage runs
- **THEN** the answer is returned with the grounded flag false

### Requirement: Missing evidence is stated without calling the model
When the graph queries return nothing found and no document passage reaches the minimum score, the flow SHALL return the status `insufficient_evidence` with a fixed message saying that nothing was found, and MUST NOT call the model for the answer. Passages below the minimum score MUST NOT reach the model as evidence.

#### Scenario: No evidence gives an honest answer
- **GIVEN** a question about something absent from the data
- **WHEN** it is asked
- **THEN** the status is `insufficient_evidence`, the message says nothing was found, and the model was called only for planning

#### Scenario: Weak passages are not evidence
- **GIVEN** a minimum score above every passage score
- **WHEN** a question is asked
- **THEN** no passage is passed to the model as evidence

#### Scenario: Obsolete documents are excluded unless the plan asks for them
- **GIVEN** a document marked obsolete that matches the question
- **WHEN** the plan does not ask for obsolete documents, and again when it does
- **THEN** the first run has none of its passages in the evidence and the second has them marked obsolete

### Requirement: The flow survives a misbehaving model
When the answer stage fails or returns invalid output, the flow SHALL retry once and then return an answer built from the evidence alone (the facts and the best passages with their sources), with status `degraded` and the grounded flag false. A model that cannot be reached MUST produce an error that tells how to start it, and MUST NOT be replaced silently by another provider.

#### Scenario: A failing synthesis falls back to the evidence
- **GIVEN** a model that fails when asked to write the answer
- **WHEN** a question with evidence is asked
- **THEN** the result lists the evidence with its sources, the status is `degraded` and the grounded flag is false

#### Scenario: An unreachable local model is reported clearly
- **GIVEN** the Ollama adapter configured for a server that is not running
- **WHEN** the flow is asked a question
- **THEN** it raises an error that names the address and says how to start the server, and no other provider is used

### Requirement: The model layer is provider-neutral
The flow SHALL depend only on a small model port that returns text or JSON for a system prompt, a user prompt and an optional JSON schema. The provider MUST be selectable by configuration, with a scripted fake for tests and an Ollama adapter. The adapter MUST read its server address, model name and timeout from configuration and use temperature zero.

#### Scenario: The scripted model replays responses and records calls
- **GIVEN** a scripted model with two responses
- **WHEN** it is called twice and then a third time
- **THEN** it returns the responses in order, records each prompt, and the third call fails with an error saying the script ran out

#### Scenario: The provider is chosen by configuration
- **GIVEN** the provider setting `fake` and, separately, `ollama`
- **WHEN** the model is created from configuration
- **THEN** the corresponding implementation is returned, and an unknown provider name is rejected with the list of valid names

### Requirement: Answers are plain data
Every answer SHALL serialize to JSON and contain the question, the answer text, the status, the grounded flag, the resolved citations, and the trace.

#### Scenario: An answer serializes
- **GIVEN** any answer
- **WHEN** it is serialized to JSON
- **THEN** serialization succeeds and the listed fields are present

### Requirement: The flow is read-only and isolated from actions
The flow package SHALL NOT depend on the actions server or the MCP SDK, and MUST NOT write anything under the data root or call any action.

#### Scenario: No forbidden imports
- **GIVEN** the source of the flow and model packages
- **WHEN** their imports are inspected
- **THEN** none refers to the actions package, the MCP SDK or an LLM provider other than the Ollama client

#### Scenario: The data is never modified
- **GIVEN** a checksum of every file under the data root
- **WHEN** questions of every kind are asked
- **THEN** the checksum is unchanged

### Requirement: Flow quality is measured
The project SHALL include end-to-end evaluation questions, each with the sources an answer should cite and the key facts it should state, and a script that runs them and reports, per question and overall, whether both conditions hold. The script MUST exit with a failure status when the overall rate is below a minimum given on the command line.

#### Scenario: The report is per question and overall
- **GIVEN** the evaluation set and a scripted model
- **WHEN** the script runs
- **THEN** it prints one line per question with its verdict and an overall rate

#### Scenario: A rate below the minimum fails the run
- **GIVEN** a minimum rate above what the run achieves
- **WHEN** the script runs
- **THEN** it exits with a failure status

#### Scenario: Every evaluation question points at real sources
- **GIVEN** the evaluation set and the sample data
- **WHEN** the set is checked
- **THEN** every expected document exists and every expected graph entity exists

### Requirement: The planning catalog offers the listing queries
The flow's query catalog SHALL include `list_entities` and `team_overview`, so a plan can use them, and the planning prompt MUST describe them.

#### Scenario: A plan can request all teams
- **GIVEN** a scripted planner that returns `list_entities` with type `team`
- **WHEN** the question "which teams exist?" runs through the flow
- **THEN** the query executes against the graph and its result is cited as evidence

### Requirement: The answer exposes the document passages it retrieved
The flow's answer SHALL carry the document passages it retrieved, each with its path, heading path and text, and MUST mark a passage that was cut or whose text is not exactly as in the file.

#### Scenario: Passages come with the answer
- **GIVEN** a question that retrieves two document passages
- **WHEN** the flow answers
- **THEN** the answer lists both with path, heading path and text

#### Scenario: A passage is an exact piece of its file
- **GIVEN** every markdown document of the sample data
- **WHEN** its passages are produced
- **THEN** the text of each exact passage appears in the file exactly as written

#### Scenario: A long passage is marked as cut
- **GIVEN** a section longer than 1,500 characters
- **WHEN** its passage is exposed
- **THEN** it is cut and marked truncated

### Requirement: A passage says which service and path it belongs to
Each passage of an answer SHALL carry `service` and `doc_path`, the path inside the service, when the document belongs to a service.

#### Scenario: A service document names its service and inner path
- **GIVEN** a passage of `repos/driver-service/README.md`
- **WHEN** the answer lists it
- **THEN** its service is `driver-service` and its doc_path is `README.md`

#### Scenario: A document outside a service has no service
- **GIVEN** a passage of a client's product vision
- **WHEN** the answer lists it
- **THEN** its service and doc_path are empty

### Requirement: A cut graph answer is marked, and no catalog query is cut on the sample data
A graph answer longer than the cap SHALL be marked as truncated and the flow's trace SHALL record it. Every query of the catalog, run on the sample data, MUST fit under the cap.

#### Scenario: Every catalog query fits
- **GIVEN** the sample data and a representative argument for each catalog query
- **WHEN** each query runs as the flow runs it
- **THEN** no answer is marked truncated

#### Scenario: A new query without a case fails the guard
- **GIVEN** the catalog
- **WHEN** a query exists that the guard has no case for
- **THEN** the guard test fails naming it

#### Scenario: A cut answer is marked and traced
- **GIVEN** a query whose answer is longer than a small cap
- **WHEN** it runs
- **THEN** the fact is marked truncated and the trace step lists it as truncated
