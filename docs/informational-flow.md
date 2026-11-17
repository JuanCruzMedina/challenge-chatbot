# Informational flow

The single entry that answers any informational question: `InformationalFlow.ask(question)`. It combines the knowledge graph (facts and relations) with the document index (passages) and a language model that writes the answer, and it returns the answer **with its citations, a status and a trace**. It is the informational path only: it never calls the MCP actions server and cannot execute actions. The agent will expose it as its one knowledge tool (`design-decisions.md` D3, D7).

Specification: `openspec/specs/knowledge-flow-answers/spec.md` once the change is archived, until then `openspec/changes/add-informational-flow/`.

## The pipeline

A LangGraph graph, the same five stages for every question:

| Stage | What it does |
| --- | --- |
| `plan` | the model proposes which graph questions to ask (and document filters); the plan is validated |
| `graph_queries` | the valid queries run on the knowledge graph and become facts `K1..` |
| `document_search` | the documents are **always** searched; passages that reach the minimum score become `D1..` |
| `answer` | the model writes the answer from the numbered evidence and cites its ids |
| `check` | invented citations are removed, valid ones are resolved to their sources |

When there is no evidence at all (no graph fact found and no passage above the minimum score) the flow goes straight to the end with `insufficient_evidence` and **does not call the model to answer**.

### The plan

The model returns one JSON object. Only methods of this fixed catalog are accepted, at most four per question:

| Method | Argument(s) | Answers |
| --- | --- | --- |
| `client_overview` | `client` | applications and services of a client, and its vision |
| `application_services` | `application` | services of an application |
| `service_owner` | `service` | owning team and tech lead |
| `api_consumers` | `api` | providers, consumers and deprecated versions of an API |
| `event_flow` | `event` | publishers and subscribers |
| `service_product_context` | `service` | application, client, features and product vision |
| `relation_path` | `start`, `end` | shortest chain of relations |
| `describe` | `entity` | every relation of an entity |
| `obsolete_documents` | none | documents marked obsolete |
| `list_entities` | `type` | every entity of a type (team, person, service, ...) |
| `team_overview` | `team` | the services a team owns and the person who leads each |

Unknown methods, missing or extra arguments, filters that name an unknown client, application or service, and queries beyond the fourth are **dropped and recorded** in the trace. Entity names go through the graph's tolerant matching ("payments api" finds `payments-api`). Invalid JSON is retried once; if it fails again the flow continues with a document search alone.

## The answer

```text
Answer(question, text, status, grounded, citations, trace, llm, passages)   # .to_dict() is plain JSON
```

| `status` | Meaning |
| --- | --- |
| `answered` | the model wrote the answer and it was checked |
| `insufficient_evidence` | nothing relevant was found; a fixed message says so |
| `degraded` | the plan failed twice, or the answer failed twice and the flow answered from the evidence itself |

`passages` lists the document passages the flow retrieved (`id`, `path`, `heading_path`, `text`, `truncated`, `exact`). `text` is the section body as it is in the file; `exact` is true only when the flow was given the data root, the text appears in the file exactly as written and it was not cut (a passage over 1,500 characters is cut and marked `truncated`). The agent uses them to quote the text to replace when it edits a document.

`grounded` is true when at least one valid citation remains after the check. **It means "cites evidence that exists", not "is true"** (see Limits). Each citation says whether it comes from the graph or from a document and lists its source files. The trace records every stage, the plan items that were dropped and the citations that were removed.

## Examples

Every example below is executed by `tests/flow/test_docs_examples.py`, and its output must match what is written here. They use a scripted model and the offline embedder, so they need neither Ollama nor any download.

A combined question: an ownership fact from the graph and a procedure from a runbook.

```python
import tempfile
from pathlib import Path

from ecosystem_assistant.knowledge.flow.graph import InformationalFlow
from ecosystem_assistant.knowledge.graph import build_graph
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.port import LLMOutputError
from ecosystem_assistant.llm.scripted import ScriptedLLM

graph = build_graph("data/ecosystem")
index = RetrievalIndex(Path(tempfile.mkdtemp()), HashingEmbedder())
index.sync("data/ecosystem", graph)

llm = ScriptedLLM([
    {"graph_queries": [{"method": "service_owner", "arguments": {"service": "tracking service"}}]},
    {"answer": "tracking-team owns it and Bruno Salas leads it [K1]. When a vehicle disappears, follow the runbook [D1].",
     "citations": ["K1", "D1"]},
])
flow = InformationalFlow(graph, index, llm)
answer = flow.ask("Who owns the tracking service, and what do I do when a vehicle disappears from the map?")
print(answer.status, answer.grounded)
print(answer.text)
for citation in answer.citations:
    print(citation.id, citation.kind, citation.sources)
```

```text
answered True
tracking-team owns it and Bruno Salas leads it [K1]. When a vehicle disappears, follow the runbook [D1].
K1 graph ['repos/tracking-service/service.yaml']
D1 document ['repos/tracking-service/docs/runbook-missing-positions.md']
```

The trace shows that the same five stages ran and that the model was called twice (plan and answer):

```python
for step in answer.trace:
    print(step.stage, "|", step.outcome)
print("model calls:", [call.kind for call in llm.calls])
```

```text
plan | ok
graph_queries | 1 queries
document_search | 5 passages
answer | ok
check | answered
model calls: ['json', 'json']
```

With nothing relevant in the data, the flow says so and the model is called only to plan:

```python
nothing = ScriptedLLM([{"graph_queries": []}])
lost = InformationalFlow(graph, index, nothing).ask("What is the capital of France?")
print(lost.status, "|", lost.text, "| model calls:", len(nothing.calls))
```

```text
insufficient_evidence | I could not find information about that in the documentation or the knowledge graph. | model calls: 1
```

A model that cannot produce a valid plan twice degrades the answer to a document search, and says so:

```python
broken = ScriptedLLM([LLMOutputError("bad"), LLMOutputError("worse"),
                      {"answer": "Check the runbook [D1].", "citations": ["D1"]}])
slow = InformationalFlow(graph, index, broken).ask("What should I do when a vehicle disappears from the map?")
print(slow.status, slow.grounded, "|", [(s.stage, s.outcome) for s in slow.trace][:2])
```

```text
degraded True | [('plan', 'degraded'), ('graph_queries', '0 queries')]
```

Citations the model invents are removed, and the removal is recorded:

```python
liar = ScriptedLLM([{"graph_queries": []}, {"answer": "See [D1] and [D9].", "citations": ["D1", "D9"]}])
checked = InformationalFlow(graph, index, liar).ask("What should I do when a vehicle disappears from the map?")
print([c.id for c in checked.citations], next(s for s in checked.trace if s.stage == "check").details["removed"])
```

```text
['D1'] ['D9']
```

## The model layer

The flow knows only a small port (`ecosystem_assistant.llm`): `complete(system, user)` and `complete_json(system, user, schema)`. A model that cannot be reached raises `LLMUnavailableError` with how to start it; the flow **never replaces it silently** with another one.

| Setting | Default | Meaning |
| --- | --- | --- |
| `LLM_PROVIDER` | `ollama` | `ollama`, or `fake` (an empty scripted model, for tests) |
| `OLLAMA_HOST` | `http://localhost:11434` | where the Ollama server runs |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | the model; it must be pulled |
| `OLLAMA_TIMEOUT` | `120` | seconds |

Temperature is always 0, and nothing leaves the machine. To run it for real:

```bash
brew install ollama                       # once
ollama serve                              # leave it running (or: brew services start ollama)
ollama pull qwen2.5:7b-instruct           # once, about 4.7 GB
uv run python scripts/eval_flow.py --embedder minilm
```

LangGraph depends on LangSmith, a tracing service. Tracing is **forced off** in code (`LANGSMITH_TRACING` and `LANGCHAIN_TRACING_V2` are set to `false` when the flow is imported), and a test checks it.

## The minimum score

A passage counts as evidence only above a minimum score, the `min_score` parameter of `InformationalFlow` (and `--min-score` of the evaluation script). Scores are not comparable across embedders, so each has its default, calibrated on measured data (`tests/flow/test_calibration.py`); an embedder without a calibrated default must be given one explicitly:

| Embedder | Best score, 22 relevant questions | Off-topic questions (8) | Default |
| --- | --- | --- | --- |
| `hashing` (offline) | 0.13 to 0.54 | 0.06 to 0.30 | 0.15 |
| `minilm-l6-v2` | 0.34 to 0.72 | 0.09 to 0.18 | 0.30 |

Questions about the domain whose answer is **not in the data** ("who is the CEO?") score as high as relevant ones (0.32 to 0.34 with MiniLM), so no threshold rejects them. The answer stage has to say what is missing, and in the measurements it did.

## How good is it

`evaluation/flow.yaml` holds 13 questions of five kinds (graph, document, combined, unknown, absent). `scripts/eval_flow.py` grades them without a judge model: the answer must be `answered` and grounded, cite the expected source files and state every key fact (whole words, ignoring case and separators); `unknown` questions must end in `insufficient_evidence`.

Measured with `qwen2.5:7b-instruct` on Ollama 0.40.16 and MiniLM embeddings, on a 2025 laptop with 18 GB of RAM (about 87 seconds for the 13 questions, roughly 7 seconds each):

| Run | Pass rate |
| --- | --- |
| First run, key facts matched as exact substrings | 12 of 13 = 0.92 |
| After matching facts by whole words | 13 of 13 = 1.00 |

The one failure of the first run was the grader's, not the model's: the answer was correct but wrote "Fleet Tracker" and "Driver App" where the grader looked for `fleet-tracker` and `driver-app`. The grader was fixed **after** seeing that result, which is why both rows are shown. Matching by whole words also stopped a fact like `20` from matching `200`.

An extra probe with five questions that are not in the set gave four right answers (two questions with no answer in the data, a paraphrased runbook question, and a question about API retries) and **one wrong**: asked "who consumes the ordres api?" (with a typo), the graph correctly returned `orders-api` with no consumers and `orders-service` as its provider, and the model answered that `orders-service` consumes it, with a valid citation.

## Limits

- **`grounded` is not truth.** The check verifies that the cited ids exist, not that the statement follows from them. A 7B model can misread a fact (the provider/consumer example above) and still cite it correctly. Sources are always returned so a person can check.
- **Small evaluation set**, written by the author of the system: 100 % on 13 questions is an indicator, not a guarantee. Only one real run was made.
- **The `absent` grade is the weakest**: it accepts an answer that says the information is missing, judged by wording.
- **Prompts are a baseline.** They were not tuned; the provider/consumer confusion is the kind of error better prompts or a clearer fact format could reduce.
- **One question at a time**: no memory of earlier turns.
- **Latency** depends on the machine: about 7 seconds per question here with a 7B model.
- A document written from the chat is searchable but unknown to the graph until its manifest lists it (to be handled by the ingestion change).
