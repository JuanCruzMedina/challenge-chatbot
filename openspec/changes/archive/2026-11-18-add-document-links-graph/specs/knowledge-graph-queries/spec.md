# Spec Delta

## ADDED Requirements

### Requirement: Documents say what they are about
The graph SHALL read the `about` field of the front matter of every markdown document under a service folder, listed in a manifest or not, and link the document to its service and, with the relation `ABOUT`, to each service, API or event it names. A name that matches no entity MUST NOT fail the build: it SHALL be kept as an unresolved link with the document and the name.

#### Scenario: A document that no manifest lists is read
- **GIVEN** a document of `orders-service` that no manifest lists and whose front matter says `about: [payments-service, payments-api]`
- **WHEN** the graph is built
- **THEN** the document is documented by `orders-service` and is about `payments-service` and `payments-api`

#### Scenario: A single name is accepted
- **GIVEN** a document with `about: payments-api`
- **WHEN** the graph is built
- **THEN** it is about `payments-api`

#### Scenario: An unknown name is reported, not fatal
- **GIVEN** a document with `about: [payments-api, ghost-service]`
- **WHEN** the graph is built
- **THEN** the build succeeds, the document is about `payments-api` and the unresolved links list `ghost-service` for that document

#### Scenario: A document listed by a manifest and with links is one entity
- **GIVEN** a document that a manifest lists and that also has `about`
- **WHEN** the graph is built
- **THEN** there is one entity for it, with both relations

### Requirement: The documents about an entity can be listed
The graph SHALL answer `documents_about` for a service, API or event with the documents linked to it by `ABOUT` and, for a service, the documents its manifest lists, each with its service, path, title, status and how it is linked. An unknown entity MUST be a not-found answer with suggestions. The query MUST be in the plan catalog.

#### Scenario: Documents about an API
- **GIVEN** two documents that are about `payments-api`
- **WHEN** `documents_about("payments-api")` runs
- **THEN** both are listed as `about`, with their service, path and title

#### Scenario: A service lists its manifest documents too
- **GIVEN** `payments-service` with manifest documents and one document about it
- **WHEN** `documents_about("payments-service")` runs
- **THEN** the manifest documents are listed as `documented_by` and the other one as `about`

#### Scenario: An unknown entity is not found
- **GIVEN** the name `paymnts-api`
- **WHEN** `documents_about` runs
- **THEN** the answer is not found with `payments-api` among the suggestions

#### Scenario: The query is in the catalog
- **GIVEN** the plan catalog
- **WHEN** a plan asks for `documents_about` with an entity
- **THEN** the plan keeps the query
