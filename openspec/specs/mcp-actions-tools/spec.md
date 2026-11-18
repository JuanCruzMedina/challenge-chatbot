# mcp-actions-tools Specification

## Purpose
Defines the MCP Server that is the only mechanism for executing actions in the chatbot: the documentation tools it exposes, how they are described to a client, how writes and conflicts behave, and how it stays separate from the informational RAG + Knowledge Graph flow.

## Requirements

### Requirement: Tools are discoverable with correct MCP schemas
The MCP Server SHALL list every registered tool through the standard MCP tool listing. Each listed tool MUST carry a unique name, a description that states when the tool should and should not be used, and an `inputSchema` that is a JSON Schema object with `properties`, `required` and `additionalProperties: false`.

#### Scenario: A client lists the available tools
- **GIVEN** the server is running with its default tools
- **WHEN** a client requests the tool list
- **THEN** the list contains `add_document`, `update_document` and `mark_document_obsolete`
- **AND** each tool has a non-empty description and an object `inputSchema` that forbids additional properties

#### Scenario: Required arguments are declared in the schema
- **GIVEN** a listed tool with mandatory arguments
- **WHEN** a client reads its `inputSchema`
- **THEN** every mandatory argument appears in `required` and every optional argument does not

### Requirement: Add a document
The tool `add_document` SHALL accept `service` (a lowercase slug naming a service folder that exists in the workspace), `doc_path` (a relative path ending in `.md` with no `..` segment) and `content` (non-empty text). On success it MUST create the file under that service in the workspace and report its path. It MUST NOT overwrite an existing file.

#### Scenario: A new document is created
- **GIVEN** a workspace with the service `notifications-service` and no `docs/runbook-new.md` for it
- **WHEN** a client calls `add_document` with that service, that path and some content
- **THEN** the result is successful and the file exists with exactly that content

#### Scenario: An existing document is not overwritten
- **GIVEN** a service that already has `docs/api.md`
- **WHEN** a client calls `add_document` for that same path
- **THEN** the result is marked as an error that tells the caller to use `update_document`
- **AND** the file is unchanged

#### Scenario: Unknown service or unsafe path is rejected
- **GIVEN** any workspace
- **WHEN** a client calls `add_document` with a service that has no folder, an absolute `doc_path`, a path containing `..`, or a path that does not end in `.md`
- **THEN** the result is marked as an error that names the offending argument and nothing is written

### Requirement: Update a document with conflict detection
The tool `update_document` SHALL accept `service`, `doc_path`, `old_text` and `new_text`. It MUST replace `old_text` by `new_text` only when `old_text` occurs exactly once in the current file. When `old_text` is absent, or occurs more than once, the tool MUST NOT write and MUST report a `conflict` outcome that includes the reason. A conflict is a normal result for the caller to handle, not an error result.

#### Scenario: A passage is updated
- **GIVEN** a document that contains the sentence "v1 does not support automatic retries" once
- **WHEN** a client calls `update_document` replacing that sentence with new text
- **THEN** the outcome is `updated` and the file contains the new text in place of the old one
- **AND** the rest of the file is unchanged

#### Scenario: The passage changed since the caller read it
- **GIVEN** a document where `old_text` no longer appears because someone else edited it
- **WHEN** a client calls `update_document` with that `old_text`
- **THEN** the outcome is `conflict` with the reason "text not found"
- **AND** the file is unchanged

#### Scenario: The passage is ambiguous
- **GIVEN** a document where `old_text` appears twice
- **WHEN** a client calls `update_document` with that `old_text`
- **THEN** the outcome is `conflict` with the reason "text not unique"
- **AND** the file is unchanged

#### Scenario: The document does not exist
- **GIVEN** a service without the requested document
- **WHEN** a client calls `update_document`
- **THEN** the result is marked as an error that tells the caller to use `add_document`

### Requirement: Mark a document as obsolete
The tool `mark_document_obsolete` SHALL accept `service`, `doc_path`, `reason` and an optional `replaced_by` relative path. It MUST record the state in the document itself as a front-matter block with `status: obsolete`, the reason and the replacement, so that any later reader of the file sees it. Marking a document that is already obsolete MUST NOT change the file.

#### Scenario: A document is marked obsolete
- **GIVEN** an existing document with no front matter
- **WHEN** a client calls `mark_document_obsolete` with a reason and a `replaced_by`
- **THEN** the file starts with a front-matter block containing `status: obsolete`, the reason and the replacement
- **AND** the original body follows unchanged

#### Scenario: Marking twice is idempotent
- **GIVEN** a document already marked obsolete
- **WHEN** a client marks it again
- **THEN** the outcome reports `already_obsolete` and the file is byte-for-byte unchanged

#### Scenario: A missing document is rejected
- **GIVEN** a service without the requested document
- **WHEN** a client calls `mark_document_obsolete`
- **THEN** the result is marked as an error and nothing is written

### Requirement: Writes are confined to the workspace and audited
Every write SHALL happen inside the configured workspace, and the resolved target path MUST stay inside it. Writes MUST be atomic, so a failure never leaves a partial file. The server MUST NOT create, modify or delete anything under the committed sample data. Every successful write MUST append one entry to an audit log with the action, the service, the path and a timestamp.

#### Scenario: The sample data is left untouched
- **GIVEN** a checksum of every file under `data/ecosystem/`
- **WHEN** any tool succeeds, conflicts or fails
- **THEN** the checksum of `data/ecosystem/` is unchanged

#### Scenario: A path that escapes the workspace is rejected
- **GIVEN** a workspace containing a symbolic link that points outside it
- **WHEN** a client calls a tool with a path that resolves through that link
- **THEN** the result is marked as an error and nothing is written outside the workspace

#### Scenario: Successful writes are audited
- **GIVEN** an empty audit log
- **WHEN** a client successfully adds, updates and marks one document
- **THEN** the audit log holds three entries in order, each with its action, service, path and timestamp
- **AND** a conflict or an error adds no entry

#### Scenario: A seed script prepares the workspace
- **GIVEN** the committed sample data
- **WHEN** the seed script runs
- **THEN** the workspace holds a copy of every sample repo and running it again leaves a fresh copy

### Requirement: New tools are added without changing existing code
The MCP Server SHALL discover its tools from a tools package at startup. Adding a tool MUST require only adding a module that defines it to that package: no change to the server entry point, to any existing tool, and to any agent code. A newly added tool MUST appear in the tool listing with its own schema.

#### Scenario: A new tool module appears in the listing
- **GIVEN** a tools package with the default tools
- **WHEN** a module defining one more tool is added to the package and the server starts
- **THEN** the tool listing contains the new tool in addition to the default ones
- **AND** the default tools behave exactly as before

#### Scenario: A broken tool module fails loudly
- **GIVEN** a module in the tools package that cannot be imported
- **WHEN** the server starts
- **THEN** startup fails with an error naming that module instead of silently skipping it

### Requirement: The action server is isolated from the informational flow
The MCP Server SHALL NOT depend on the vector store, the knowledge graph, the retrieval pipeline, the agent or any LLM, and MUST run with no network access and no API keys. It MUST NOT answer informational questions about the content of the documentation.

#### Scenario: No informational dependencies
- **GIVEN** the source of the MCP Server package
- **WHEN** its imports are inspected
- **THEN** none of them refers to the retrieval, knowledge-graph or agent packages, or to an LLM client library

#### Scenario: The server runs offline
- **GIVEN** an environment with no network and no API keys
- **WHEN** the server is started over stdio and a tool is called
- **THEN** the call completes successfully

### Requirement: Text can be appended to a document without quoting it
The server SHALL offer `append_to_document(service, doc_path, text)`. It MUST add the text at the end of an existing markdown document, or create the document when it does not exist, using the same path rules as the other tools, and MUST record the action in the audit log.

#### Scenario: Appending to an existing document
- **GIVEN** `docs/lead.md` exists in a service
- **WHEN** the tool is called with new text
- **THEN** the original content is unchanged and the new text follows it
- **AND** the outcome is `appended` and the audit log has one entry

#### Scenario: Appending to a missing document creates it
- **GIVEN** `docs/team.md` does not exist
- **WHEN** the tool is called
- **THEN** the file is created with the text and the outcome is `created`

#### Scenario: Invalid input is refused and nothing is written
- **GIVEN** an unknown service, a path outside the service, a non-markdown path or empty text
- **WHEN** the tool is called
- **THEN** an error is returned and no file changes

#### Scenario: The agent discovers the tool without being changed
- **GIVEN** the real server
- **WHEN** the agent lists its tools
- **THEN** `append_to_document` is present and its name appears nowhere in the agent source

### Requirement: A workspace-relative path is rejected, not misread
A write tool SHALL reject a `doc_path` that starts with `repos/<service>/` for the given service, SHALL write nothing, and its error SHALL name the path inside the service to use.

#### Scenario: A citation path is rejected
- **GIVEN** the service `driver-service`
- **WHEN** `append_to_document` receives `repos/driver-service/README.md`
- **THEN** the call fails naming `README.md` and no file is created

#### Scenario: A path inside the service still works
- **GIVEN** the same service
- **WHEN** `append_to_document` receives `README.md`
- **THEN** the line is appended to the existing README

### Requirement: Edits and obsolete marks show a preview and wait for confirmation
`update_document` and `mark_document_obsolete` SHALL, unless `confirmed` is true, write nothing and return outcome `needs_confirmation` with a diff of the change. With `confirmed: true` they SHALL write. Creating and appending MUST stay direct. A conflict MUST be reported before any preview. The server MUST ask for confirmation unless `ACTIONS_CONFIRM_EDITS` is `off`.

#### Scenario: An unconfirmed edit is only previewed
- **GIVEN** a server that asks for confirmation
- **WHEN** `update_document` runs without `confirmed`
- **THEN** the result is `needs_confirmation` with a diff, the file is unchanged and the audit log is empty

#### Scenario: A confirmed edit is written
- **GIVEN** the same call with `confirmed: true`
- **WHEN** it runs
- **THEN** the file has the new text and the audit log has one entry

#### Scenario: Obsolete marks are previewed too
- **GIVEN** a server that asks for confirmation
- **WHEN** `mark_document_obsolete` runs without `confirmed`
- **THEN** nothing is written and the preview shows the front matter to be added

#### Scenario: Creating and appending are not asked
- **GIVEN** a server that asks for confirmation
- **WHEN** `add_document` or `append_to_document` runs
- **THEN** the document is written at once

#### Scenario: A conflict comes before the preview
- **GIVEN** an edit whose old text is not in the document
- **WHEN** it runs unconfirmed
- **THEN** the result is `conflict`

### Requirement: A session can be limited to some services
The server SHALL read `ACTIONS_ALLOWED_SERVICES` and reject any write to another service with an error that names the allowed services, writing nothing. When it is unset every service is allowed.

#### Scenario: A write outside the scope is rejected
- **GIVEN** a server limited to `payments-service`
- **WHEN** a document of `notifications-service` is created
- **THEN** the call fails naming `payments-service` and no file is created

#### Scenario: A write inside the scope works
- **GIVEN** the same server
- **WHEN** a document of `payments-service` is created
- **THEN** it is written
