# Proposal

## Why

The document search returns the five sections that best match the question. A runbook is several sections (symptom, diagnosis, fix) and a question such as "a customer sees a stale price, what should we do?" matches the symptom section best. The steps are in the other sections, which are not returned, so the answer says the procedure is not available. The result depends on how the agent words the question: when it adds keywords (for example "pricing cache") the steps are found, when it passes the question as written they are not. In repeated runs that single question passed 6 of 9 times before the last changes and 1 to 2 of 6 after them.

## What Changes

- After the ranked sections, the search adds the other sections of the best-ranked document, in document order, up to 4. They are marked `neighbour` so they can be told apart from the ranked ones. Nothing is added from other documents, and nothing when no section reaches the minimum score.
- The passages in the `query_knowledge` result carry the `neighbour` mark. The added sections are also exact passages the agent can quote when it edits a document.
- The 12,000-character budget for evidence still decides how many fit: ranked sections go first.

## Capabilities

### Modified Capabilities
- `knowledge-flow-answers`.

## Impact

- `knowledge/flow/evidence.py`, `knowledge/flow/answer.py`, tests, `docs/informational-flow.md`. A question may carry up to 4 more sections (a few hundred tokens each). The real-model checks are announced first (about $0.03).

## Non-goals

- Changing the ranking, the chunking, the embedder or the number of ranked results.
- Adding sections of the documents ranked second or later.
- Rewriting the question before searching.
