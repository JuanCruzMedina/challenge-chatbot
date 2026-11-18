# Spec Delta

## ADDED Requirements

### Requirement: The best document is completed with its other sections
After the ranked passages, the document search SHALL add the other sections of the best-ranked document, in document order and at most four, each marked as a neighbour, and MUST NOT add sections of any other document, repeat a section already ranked, or add anything when no section reaches the minimum score. The passages returned to the caller SHALL carry the mark.

#### Scenario: The steps of a runbook come with its symptom
- **GIVEN** the sample documents and a question that best matches the symptom of the stale-prices runbook
- **WHEN** the documents are searched
- **THEN** the "Diagnosis" and "Fix" sections of that runbook are among the passages, marked as neighbours and after the ranked ones

#### Scenario: Neighbours come only from the best document
- **GIVEN** any search that adds neighbours
- **WHEN** the passages are listed
- **THEN** every neighbour has the path of the best-ranked passage, none repeats a ranked section and there are at most four

#### Scenario: Nothing is added without a good match
- **GIVEN** a minimum score that no section reaches
- **WHEN** the documents are searched
- **THEN** no passage is returned

#### Scenario: The caller can tell neighbours from ranked passages
- **GIVEN** a search that added neighbours
- **WHEN** the passages are given to the caller
- **THEN** each one says whether it is a neighbour, and the ids continue the sequence D1, D2, ...
