# knowledge-graph-queries Specification

## Purpose
Defines the in-memory Knowledge Graph of the ecosystem: how it is built from the data, how entities are found, which structural questions it answers and how, and the guarantees on provenance and isolation that the informational flow relies on.

## Requirements

### Requirement: The graph is built from the ecosystem data
The graph SHALL be built from a data root containing the company file, the service manifests, the client product catalogs and the document files. It MUST represent companies, clients, applications, services, teams, people, APIs, events, epics, features and documents as entities, and the relations the data declares between them: a company has clients, a client has applications, an application has services; a service is owned by a team, led by a person, provides and consumes APIs, publishes and subscribes to events, is documented by documents and implements features; a feature is part of an epic, an epic belongs to a client, and a client has a product vision document.

#### Scenario: The hierarchy is represented
- **GIVEN** the committed sample data
- **WHEN** the graph is built
- **THEN** the company has two clients, the clients have three applications in total, and the applications have seven services
- **AND** each service is linked to exactly one application

#### Scenario: Service manifests become entities and relations
- **GIVEN** the manifest of `orders-service`
- **WHEN** the graph is built
- **THEN** `orders-service` is linked to its team and its lead, provides `orders-api`, consumes `catalog-api` and `payments-api`, publishes `order.created` and subscribes to `payment.confirmed`

#### Scenario: Product data becomes entities and relations
- **GIVEN** the product catalogs of both clients
- **WHEN** the graph is built
- **THEN** every feature is part of an epic, every epic belongs to a client, every feature is linked to the services that implement it, and every client is linked to its vision document

#### Scenario: Documents carry their title and status
- **GIVEN** a document whose front matter says `status: obsolete`
- **WHEN** the graph is built
- **THEN** the document entity is reported with status `obsolete`, and the other documents with status `current`
- **AND** each document entity has the title of its first heading

#### Scenario: Every entity and relation records its source
- **GIVEN** the committed sample data
- **WHEN** the graph is built
- **THEN** every entity and every relation lists at least one source file path relative to the data root, and each of those files exists

#### Scenario: Building twice gives the same graph
- **GIVEN** an unchanged data root
- **WHEN** the graph is built twice
- **THEN** both graphs have the same entities, relations and attributes

#### Scenario: A dangling reference fails the build
- **GIVEN** a manifest that consumes an API that no service provides
- **WHEN** the graph is built
- **THEN** the build fails with an error naming the manifest file and the missing API instead of creating a partial graph

### Requirement: Entities can be found by name
The graph SHALL resolve a name or id typed in loose form (any letter case, with spaces or hyphens interchangeable) to ranked candidate entities, each with its type and id. An exact id or name MUST rank before partial matches. A name matching nothing MUST give an empty list, not an error.

#### Scenario: An exact name resolves to one entity
- **GIVEN** the sample graph
- **WHEN** a client searches for `orders-service`
- **THEN** the first candidate is the service `orders-service` and it is the only exact match

#### Scenario: Loose wording resolves to the right entity
- **GIVEN** the sample graph
- **WHEN** a client searches for `Payments API`
- **THEN** the first candidate is the API `payments-api`

#### Scenario: An ambiguous name returns several candidates
- **GIVEN** the sample graph
- **WHEN** a client searches for `payments`
- **THEN** the candidates include the service `payments-service`, the API `payments-api` and the team `payments-team`, each with its type

#### Scenario: An unknown name returns no candidates
- **GIVEN** the sample graph
- **WHEN** a client searches for a name that matches nothing
- **THEN** the result is an empty list and no error is raised

### Requirement: Structural questions are answered from the graph
The graph SHALL answer these questions with plain data, without any language model: the applications and services of a client; the services of an application; the services that consume an API, each with its application and client and the status of the API; the team and lead that own a service; the publishers and subscribers of an event; the features of a service and the services of a feature; the product vision document of the client a service belongs to; the shortest chain of relations between two entities; the documents whose status is obsolete; and a description of any entity listing its relations grouped by kind.

#### Scenario: A client's applications and services
- **GIVEN** the sample graph
- **WHEN** the applications and services of `demo-logistics` are requested
- **THEN** the result lists `fleet-tracker` with `routing-service` and `tracking-service`, and `driver-app` with `driver-service`

#### Scenario: Consumers of an API
- **GIVEN** the sample graph
- **WHEN** the consumers of `payments-api` are requested
- **THEN** the result lists `orders-service` with its application `storefront` and its client `demo-grocery`

#### Scenario: A deprecated API is reported with its consumers
- **GIVEN** data where `payments-api` v1 is marked deprecated with a sunset date and `orders-service` consumes it
- **WHEN** the consumers of `payments-api` are requested
- **THEN** the result reports the deprecated version, its sunset date and `orders-service` as an affected consumer

#### Scenario: Owner and lead of a service
- **GIVEN** the sample graph
- **WHEN** the owner of `tracking-service` is requested
- **THEN** the result names the team `tracking-team` and the lead `Bruno Salas`

#### Scenario: Publishers and subscribers of an event
- **GIVEN** the sample graph
- **WHEN** the flow of `route.assigned` is requested
- **THEN** the publisher is `routing-service` and the subscriber is `driver-service`

#### Scenario: Features and product vision of a service
- **GIVEN** the sample graph
- **WHEN** the product context of `driver-service` is requested
- **THEN** the result lists its features with their epics and the vision document of `demo-logistics`, and not the one of `demo-grocery`

#### Scenario: A path between two entities
- **GIVEN** the sample graph
- **WHEN** the path from `tracking-service` to `driver-service` is requested
- **THEN** the result is a chain of entities and named relations that starts and ends at those services and passes through a shared event or API
- **AND** requesting a path between entities with no connection returns an empty path

#### Scenario: Obsolete documents
- **GIVEN** data in which one document is marked obsolete
- **WHEN** the obsolete documents are requested
- **THEN** the result lists that document with its service and path, and no other

#### Scenario: Describing an entity
- **GIVEN** the sample graph
- **WHEN** `payments-service` is described
- **THEN** its relations are grouped by kind, each listing the related entities with their types

### Requirement: Query results are plain data with provenance
Every query result SHALL be made of plain values that serialize to JSON, and MUST include the source files that support it. A query about an entity that does not exist MUST return a not-found result with suggestions of close names and MUST NOT raise an error.

#### Scenario: Results serialize and cite sources
- **GIVEN** any answered question
- **WHEN** its result is serialized to JSON
- **THEN** serialization succeeds and the result lists the source files of the facts it reports

#### Scenario: An unknown entity gives a not-found result
- **GIVEN** the sample graph
- **WHEN** the owner of `ordres-service` (a misspelling) is requested
- **THEN** the result says the entity was not found and suggests `orders-service`
- **AND** no error is raised

### Requirement: The graph is isolated and read-only
The graph code SHALL NOT depend on the actions server, the agent, any LLM client or any network library, and MUST NOT create, modify or delete anything under the data root.

#### Scenario: No forbidden imports
- **GIVEN** the source of the graph package
- **WHEN** its imports are inspected
- **THEN** none refers to the actions package, the agent, an LLM client library or a network library

#### Scenario: The data is never modified
- **GIVEN** a checksum of every file under the data root
- **WHEN** the graph is built and every kind of query is run
- **THEN** the checksum is unchanged
