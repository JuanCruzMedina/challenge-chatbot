# Retrieval index (RAG)

A search over the **text** of the ecosystem documents. The knowledge graph answers structural questions (who owns what); this index answers content questions ("what does the runbook say when a vehicle disappears from the map?") and returns the passages with their citation. It belongs to the informational flow: the agent will reach it only through the single knowledge tool (`design-decisions.md` D4, D7), never through the MCP actions server.

Specification: `openspec/specs/knowledge-retrieval-index/spec.md` once the change is archived, until then `openspec/changes/add-retrieval-index/`.

## What is indexed

Every markdown file under `repos/<service>/`, `clients/<client>/product/` and `company/` of a data root. Nothing under `prs/` and no hidden file. A document is cut into **one chunk per section**; a section longer than 1200 characters is split at paragraph boundaries. A heading with no text of its own makes no chunk.

Every chunk stores its title, heading path, file, `scope` (`service`, `client` or `company`), service, application, client, status (`current` or `obsolete`, read from the document's own front matter) and a version. Application and client of a service come from the knowledge graph; a folder the graph does not know is still indexed, with those two empty.

## Keeping it in step with the files

`sync(root)` compares each file with what the index holds and embeds **only what changed**:

| File | Result |
| --- | --- |
| not in the index | added |
| its version changed (text, status, or its service's application or client) | updated |
| gone from disk | removed |
| same version | unchanged |
| a title with no text | empty (nothing to index) |

The version is a hash of the file plus its graph context, so moving a service to another application is noticed even when no file changed. If the graph cannot be built (for example a manifest lists a document that was deleted), `sync` stops with the graph's error and changes nothing.

## Embedders

| Name | What it is | Needs |
| --- | --- | --- |
| `hashing` | counts words (signed hashing of word unigrams and bigrams, 256 dimensions) | nothing; offline and deterministic; used by the tests |
| `minilm` | `all-MiniLM-L6-v2` on Chroma's ONNX runtime, English, 384 dimensions, no PyTorch | the model (about 80 MB) in `~/.cache/chroma/` |

The model is **never downloaded silently**. Without it, creating the embedder fails and names the setting `ALLOW_MODEL_DOWNLOAD=1`, which authorizes the one-time download on first use. After that it works offline. The default embedder comes from the `EMBEDDER` variable (`minilm` if unset). An index remembers which embedder built it and refuses to open with another one; recreate it instead. Telemetry of the vector store is off. The index lives in `var/index/` (override with `VECTOR_INDEX_DIR`), never inside the data.

## Examples

Every example below is executed by `tests/retrieval/test_docs_examples.py`, and its output must match what is written here. They use the offline embedder and a throwaway index.

The first sync indexes everything; the second one finds nothing to do:

```python
import tempfile
from pathlib import Path

from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex

index = RetrievalIndex(Path(tempfile.mkdtemp()), HashingEmbedder())
print(index.sync("data/ecosystem").to_dict())
print(index.sync("data/ecosystem").to_dict())
```

```text
{'added': 22, 'updated': 0, 'removed': 0, 'unchanged': 0, 'empty': 0, 'chunks_embedded': 58}
{'added': 0, 'updated': 0, 'removed': 0, 'unchanged': 22, 'empty': 0, 'chunks_embedded': 0}
```

A question, answered with passages and their citation:

```python
question = "what should I do when a vehicle disappears from the map?"
for hit in index.search(question, k=2):
    print(hit.citation.path, "|", hit.citation.heading_path, "|", hit.citation.client)
```

```text
repos/tracking-service/docs/runbook-missing-positions.md | Runbook: a vehicle disappears from the map | demo-logistics
repos/routing-service/docs/routing-rules.md | Routing rules > Assignment | demo-logistics
```

Note the second line: it is the best of what is left, not a good answer. See "Limits".

Restricting to a client, or to a service:

```python
for hit in index.search("who is on call", k=3, client="demo-logistics"):
    print(hit.citation.client, hit.citation.service)
print([h.citation.service for h in index.search("payments", k=3, service="orders-service")])
```

```text
demo-logistics tracking-service
demo-logistics tracking-service
demo-logistics driver-service
['orders-service', 'orders-service', 'orders-service']
```

Marking a document obsolete (here through the actions server, on a copy of the data) hides it, and the next `sync` re-embeds only that file:

```python
import shutil

from ecosystem_assistant.actions.tools.documents import set_obsolete
from ecosystem_assistant.actions.workspace import Workspace

work = Path(tempfile.mkdtemp())
shutil.copytree("data/ecosystem", work / "ecosystem")
live = RetrievalIndex(work / "index", HashingEmbedder())
live.sync(work / "ecosystem")
asked = "v1 does not support automatic retries"
print("before:", [h.citation.path for h in live.search(asked, k=1)])
set_obsolete(Workspace(root=work / "ecosystem", audit_file=work / "audit.jsonl"), "payments-service",
             "docs/api-v1.md", "Replaced by v2", "docs/api-v2.md")
print(live.sync(work / "ecosystem").to_dict())
print("hidden:", [h.citation.path for h in live.search(asked, k=1)])
print("requested:", [(h.citation.path, h.citation.status) for h in live.search(asked, k=1, include_obsolete=True)])
```

```text
before: ['repos/payments-service/docs/api-v1.md']
{'added': 0, 'updated': 1, 'removed': 0, 'unchanged': 21, 'empty': 0, 'chunks_embedded': 3}
hidden: ['clients/demo-logistics/product/vision.md']
requested: [('repos/payments-service/docs/api-v1.md', 'obsolete')]
```

## How good is it

`evaluation/retrieval.yaml` holds 22 questions, each with the document that answers it; `scripts/eval_retrieval.py` counts a hit when an expected document is among the top 3 distinct documents.

```bash
uv run python scripts/eval_retrieval.py                                   # offline embedder
ALLOW_MODEL_DOWNLOAD=1 uv run python scripts/eval_retrieval.py --embedder minilm
```

Measured when the set was written:

| Embedder | Hits in the top 3 |
| --- | --- |
| `hashing` (words) | 19 of 22 = 0.86 |
| `minilm` (semantic) | 20 of 22 = 0.91 |

Read this with care. The difference is one question, which says nothing with 22 questions. The last four questions are paraphrases that avoid the words of the documents: `minilm` found 3 of them and `hashing` 2. Both miss the question about not billing a shopper twice (the answer is one line about an idempotency key), and `minilm` missed one plain question ("which states can an order go through?") that `hashing` found. A regression floor of 0.7 for the offline embedder is enforced by the tests.

## Limits

- **No relevance threshold.** A search always returns the best of what is left, even when nothing is relevant (see the examples). Callers must look at `score` before trusting a passage. The informational flow will decide what to do with weak results.
- **Hiding obsolete documents can hide the only description of an old behavior**; `include_obsolete=True` brings them back.
- **English only** (the MiniLM model); the `hashing` embedder is lexical and misses paraphrases.
- **Small evaluation set**: an indicator, not a statistic.
- **Documents added from the chat are searchable here but not known to the graph**, because the graph reads only the documents a manifest lists. To be handled by the ingestion change.
- Syncing is a function you call; nothing triggers it automatically yet.
