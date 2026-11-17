# Spec Delta

## Purpose

Defines the retrieval index over the ecosystem documents: how documents are split and described, how the index is kept in step with the files, how it is searched with filters and citations, how its quality is measured, and the guarantees on offline use and isolation that the informational flow relies on.

## ADDED Requirements

### Requirement: Documents are split into described chunks
The index SHALL cover every markdown file under `repos/<service>/`, under `clients/<client>/product/` and under `company/` of a data root, and nothing else (in particular nothing under `prs/`). Each document MUST be split into chunks by section, one chunk per heading with its text, except that a section longer than 1200 characters is split at paragraph boundaries. Every chunk MUST carry its document title, heading path, file path, scope, service, application, client, status, a content hash of its file, and a deterministic identifier.

#### Scenario: A document becomes one chunk per section
- **GIVEN** a document with a title and three headed sections
- **WHEN** it is chunked
- **THEN** it yields one chunk per section, each beginning with its heading path and containing only the text of that section

#### Scenario: A small document is a single chunk
- **GIVEN** a document with a single heading and a few lines
- **WHEN** it is chunked
- **THEN** it yields exactly one chunk

#### Scenario: A very long section is split at paragraphs
- **GIVEN** a section longer than 1200 characters made of several paragraphs
- **WHEN** it is chunked
- **THEN** it yields several chunks, none longer than 1200 characters except a single paragraph that is itself longer, and no paragraph is cut in the middle

#### Scenario: Chunks carry their metadata
- **GIVEN** the committed sample data
- **WHEN** the index is built
- **THEN** a chunk of `docs/api.md` of `orders-service` records service `orders-service`, application `storefront`, client `demo-grocery`, status `current` and the title of the document
- **AND** a chunk of a client vision records the client and no service, and a chunk of the company overview records neither

#### Scenario: A folder the graph does not know is still indexed
- **GIVEN** a service folder that no manifest of the graph describes
- **WHEN** the index is built
- **THEN** its documents are indexed with the service taken from the folder and with empty application and client, and no error is raised

#### Scenario: Only the intended files are indexed
- **GIVEN** a data root with documents under `repos/`, `clients/` and `company/`, a simulated PR under `prs/`, and a hidden temporary file
- **WHEN** the index is built
- **THEN** only the documents under the three folders are indexed

#### Scenario: Chunk identifiers are deterministic
- **GIVEN** an unchanged data root
- **WHEN** it is chunked twice
- **THEN** both runs produce the same chunk identifiers and the same texts

### Requirement: The index follows the files incrementally
The index SHALL provide a sync operation that compares each file's content hash with the hash stored in the index. It MUST embed only the chunks of files that are new or changed, MUST remove the chunks of files that no longer exist, MUST leave unchanged files untouched, and MUST report how many files were added, updated, removed and unchanged.

#### Scenario: The first sync indexes everything
- **GIVEN** an empty index and the sample data
- **WHEN** a sync runs
- **THEN** every document is added and none is updated, removed or unchanged

#### Scenario: A second sync changes nothing
- **GIVEN** an index just synced with the sample data
- **WHEN** a sync runs again
- **THEN** every file is reported unchanged and no chunk is embedded

#### Scenario: An edited file is re-embedded alone
- **GIVEN** a synced index and one document whose text changed
- **WHEN** a sync runs
- **THEN** exactly that file is reported updated, only its chunks are embedded, and a search finds the new text and no longer the old

#### Scenario: A file created through the actions server becomes searchable
- **GIVEN** a synced index and a new document added to a service folder
- **WHEN** a sync runs
- **THEN** the file is reported added and a search finds its content with the right service and client

#### Scenario: A deleted file leaves the index
- **GIVEN** a synced index and a document that is then deleted
- **WHEN** a sync runs
- **THEN** the file is reported removed and no chunk of it can be found

#### Scenario: A document marked obsolete changes status
- **GIVEN** a synced index and a document that the actions server then marks obsolete
- **WHEN** a sync runs
- **THEN** the file is reported updated and its chunks now have status `obsolete`

### Requirement: Search returns cited chunks, filtered by scope
The search SHALL return at most the requested number of chunks (default 5, never more than 20), best first, each with its text, a score, and a citation made of document title, heading path, file path, service, application, client and status. It MUST support restricting results to a client, an application or a service. Chunks of obsolete documents MUST be excluded unless the caller asks to include them, and an empty question MUST return no results.

#### Scenario: A question finds the document that answers it
- **GIVEN** an index of the sample data
- **WHEN** a client searches for what to do when a vehicle disappears from the map
- **THEN** the best chunk comes from the missing-positions runbook of `tracking-service`, and its citation names that file, its title and its heading path

#### Scenario: Results can be limited to a client
- **GIVEN** an index of the sample data
- **WHEN** a client searches for a topic present in both clients, restricted to `demo-logistics`
- **THEN** every result belongs to `demo-logistics`

#### Scenario: Results can be limited to a service
- **GIVEN** an index of the sample data
- **WHEN** a search is restricted to `orders-service`
- **THEN** every result comes from a document of `orders-service`

#### Scenario: Obsolete documents are hidden unless requested
- **GIVEN** an index in which one document is obsolete
- **WHEN** a search that would match it runs with default options, and again asking to include obsolete documents
- **THEN** the first search returns none of its chunks and the second returns them with status `obsolete`

#### Scenario: The number of results is bounded
- **GIVEN** an index of the sample data
- **WHEN** a client asks for 100 results, for 0 results, or searches an empty question
- **THEN** at most 20 results are returned for the first, none for the other two, and no error is raised

#### Scenario: Results are plain data
- **GIVEN** any search result
- **WHEN** it is serialized to JSON
- **THEN** serialization succeeds and the citation fields are present

### Requirement: Embedders are interchangeable and recorded
The index SHALL compute embeddings through an interface, with a deterministic offline embedder that needs no download and a MiniLM embedder backed by a local model. The index MUST record the name of the embedder that built it and MUST refuse to be used with a different embedder, telling the caller to rebuild. The MiniLM embedder MUST NOT download its model unless the caller explicitly opted in, and MUST fail with a message naming the opt-in when the model is not cached.

#### Scenario: The offline embedder is deterministic and needs no model
- **GIVEN** the offline embedder
- **WHEN** the same text is embedded twice
- **THEN** both vectors are equal, and embedding needs no network access and no files outside the project

#### Scenario: Similar texts are closer than unrelated ones with the offline embedder
- **GIVEN** the offline embedder and three texts, two about payment retries and one about vehicle tracking
- **WHEN** their vectors are compared
- **THEN** the two payment texts are closer to each other than to the tracking text

#### Scenario: An index refuses a different embedder
- **GIVEN** an index built with one embedder
- **WHEN** it is opened with another embedder
- **THEN** opening fails with an error that names both embedders and says to rebuild the index

#### Scenario: The model is never downloaded silently
- **GIVEN** a machine where the MiniLM model is not cached and no opt-in is set
- **WHEN** the MiniLM embedder is created
- **THEN** creation fails with a message that names the opt-in setting, and nothing is downloaded

### Requirement: Retrieval quality is measured
The project SHALL include a set of evaluation questions, each with the document that should be found, and a script that runs them against an index and reports, per question and overall, whether the expected document is among the top results. The script MUST exit with a failure status when the overall hit rate is below a minimum given on the command line.

#### Scenario: The evaluation reports per question and overall
- **GIVEN** the evaluation set and an index of the sample data
- **WHEN** the evaluation runs with the offline embedder
- **THEN** it prints one line per question with hit or miss and the rank of the expected document, then the overall hit rate

#### Scenario: A hit rate below the minimum fails the run
- **GIVEN** the evaluation set and a minimum hit rate above what the index achieves
- **WHEN** the evaluation runs
- **THEN** it exits with a failure status

#### Scenario: Every evaluation question points at a real document
- **GIVEN** the evaluation set and the sample data
- **WHEN** the set is checked
- **THEN** every expected document exists under the data root

### Requirement: The retrieval index is isolated, private and read-only on the data
The retrieval package SHALL NOT depend on the actions server, the agent, any LLM client or any network library, MUST NOT send telemetry, and MUST NOT create, modify or delete anything under the data root. Its index MUST live outside the data root, in a configurable location.

#### Scenario: No forbidden imports
- **GIVEN** the source of the retrieval package
- **WHEN** its imports are inspected
- **THEN** none refers to the actions package, the agent, an LLM client library or a network library

#### Scenario: Telemetry is off
- **GIVEN** the vector store created by the package
- **WHEN** its settings are inspected
- **THEN** anonymized telemetry is disabled

#### Scenario: The data is never modified
- **GIVEN** a checksum of every file under the data root
- **WHEN** the index is built, synced and searched
- **THEN** the checksum is unchanged and the index files are outside the data root
