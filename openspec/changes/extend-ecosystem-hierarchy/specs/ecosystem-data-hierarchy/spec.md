# Spec Delta

## Purpose

Defines the company, client and application structure of the invented sample ecosystem, the per-client product vision, and the consistency rules that the data validator enforces so that later stages (ingestion, knowledge graph, retrieval) can rely on it.

## ADDED Requirements

### Requirement: A company file describes clients and applications
The sample data SHALL include a company file that names the company and lists its clients and, for each client, its applications. Every client MUST have a unique identifier, a name, and the paths of its product vision and of its feature catalog; every application MUST have a unique identifier, a name and exactly one client. The sample data MUST contain one company, at least two clients, and at least three applications, with one client owning more than one application.

#### Scenario: The company file loads and is complete
- **GIVEN** the committed sample data
- **WHEN** the validator reads the company file
- **THEN** it finds one company, two clients and three applications
- **AND** each application belongs to exactly one client

#### Scenario: A client with several applications exists
- **GIVEN** the committed sample data
- **WHEN** the applications are grouped by client
- **THEN** at least one client has two or more applications

### Requirement: Every service declares its client and application
Every service manifest SHALL declare the `client` and the `application` it belongs to. The validator MUST report an error when either is missing, unknown, or when the application does not belong to the declared client. A manifest's `name` MUST equal the name of its folder under `repos/` (the folder name is what the actions server uses as the service), and service names MUST stay unique across the whole company.

#### Scenario: A consistent manifest passes
- **GIVEN** a service whose client and application exist and match
- **WHEN** the validator runs
- **THEN** no error is reported for that service

#### Scenario: An unknown application is rejected
- **GIVEN** a service that declares an application missing from the company file
- **WHEN** the validator runs
- **THEN** it reports an error naming the service and the application
- **AND** exits with a non-zero status

#### Scenario: An application of another client is rejected
- **GIVEN** a service declaring client A and an application that belongs to client B
- **WHEN** the validator runs
- **THEN** it reports an error naming the service, the client and the application

#### Scenario: A duplicate service name is rejected
- **GIVEN** two manifests declaring the same `name`
- **WHEN** the validator runs
- **THEN** it reports an error naming the duplicate, even though one of the two is overwritten when services are indexed by name

#### Scenario: A manifest name that differs from its folder is rejected
- **GIVEN** a service folder `repos/orders-service/` whose manifest declares `name: order-service`
- **WHEN** the validator runs
- **THEN** it reports an error naming the folder and the declared name

### Requirement: Product vision is per client
Each client SHALL have its own product vision document and its own catalog of epics and features. A feature MUST reference only services that belong to applications of the same client. The visions of different clients MUST differ in content.

#### Scenario: Every client has a vision and a feature catalog
- **GIVEN** the committed sample data
- **WHEN** the validator runs
- **THEN** every client has an existing vision document and an existing feature catalog

#### Scenario: A feature that points at another client's service is rejected
- **GIVEN** a feature of client A listing a service of client B
- **WHEN** the validator runs
- **THEN** it reports an error naming the feature, the service and both clients

#### Scenario: A missing vision is rejected
- **GIVEN** a client whose vision file does not exist
- **WHEN** the validator runs
- **THEN** it reports an error naming the client and the missing path

### Requirement: Identifiers are unique across the company
Epic ids, feature ids and API ids SHALL be unique across the whole company, so that every reference to them is unambiguous when two clients are present. The validator MUST report an error naming each duplicated id and the places that declare it.

#### Scenario: A feature id repeated by two clients is rejected
- **GIVEN** two clients whose feature catalogs both declare `FEAT-101`
- **WHEN** the validator runs
- **THEN** it reports an error naming `FEAT-101` and both clients

#### Scenario: An API id provided by two services is rejected
- **GIVEN** two services of different clients that both provide `orders-api`
- **WHEN** the validator runs
- **THEN** it reports an error naming `orders-api` and both services

### Requirement: Existing relations and simulated PRs stay valid
All the relations that existed before the hierarchy (APIs consumed, events published and subscribed, documents, features) SHALL remain valid and checked. The simulated PR MUST still validate against the extended data, and the service folder names under `repos/` MUST NOT change for existing services.

#### Scenario: The full committed data validates
- **GIVEN** the committed sample data and the simulated PR
- **WHEN** the validator runs
- **THEN** it exits with status zero and reports the deprecated API and its affected consumer as before

#### Scenario: A simulated PR manifest declares its client and application
- **GIVEN** a simulated PR that replaces a service manifest
- **WHEN** the validator checks the state after that PR
- **THEN** the replacing manifest is held to the same client and application rules as any other
- **AND** a replacing manifest without `client` or `application` is reported as an error

#### Scenario: Existing service folders keep their names
- **GIVEN** the committed sample data
- **WHEN** the folders under `repos/` are listed
- **THEN** `catalog-service`, `orders-service`, `payments-service` and `notifications-service` are present

### Requirement: The validator reports the hierarchy
The validator SHALL print a summary of the hierarchy (company, clients, applications and their services) and MUST be usable as a function that returns its errors, warnings and summary, so tests can run it on modified copies of the data.

#### Scenario: A summary is printed
- **GIVEN** valid sample data
- **WHEN** the validator runs from the command line
- **THEN** its output lists each client with its applications and their services

#### Scenario: The validator is callable on any data root
- **GIVEN** a copy of the sample data in a temporary folder
- **WHEN** the validation function is called on that root
- **THEN** it returns the errors, warnings and summary for that copy only
