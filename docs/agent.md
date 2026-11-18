# The agent

The agent is the one entry point of the assistant. It receives a message, gives it to a chat model together with a list
of tools, runs the tools the model asks for and returns the reply. **The code never decides what a message is.** The
decision belongs to the model, which reads the tool descriptions.

## The tools

| Tool | Where it comes from | What it is for |
|---|---|---|
| `query_knowledge` | `agent/knowledge.py` | Every informational question. It wraps the whole flow of [informational-flow.md](informational-flow.md) (graph + documents, cited answer). It is the **only** way the agent reads knowledge. |
| every tool the MCP server lists | discovered at runtime by `agent/mcp_tools.py` | Actions: today `add_document`, `append_to_document`, `update_document`, `mark_document_obsolete`. |

The agent source names no MCP tool. A test reads the real server's tool list and fails if any name appears in
`src/ecosystem_assistant/agent/`.

## How a turn runs

```
model ──asks for tools?──► tools ──► model ──► … ──► reply
        └─ no ───────────────────────────────────► reply
```

Two nodes, one branch: "did the model ask for tools?". There is no `if` on the content of the message, no keyword
list and no regular expression in the loop (a test checks the loop files for string inspection).

- **Cap.** At most 6 tool calls per turn. When the model asks for more, its request is replaced by a short message
  that says the limit was reached, and the model answers with what it has.
- **Errors are tool messages.** A tool that fails gives the model an error text (for example, the server's list of
  valid services) and the model can correct itself or explain. Unknown tool names get the same treatment.
- **The model server being down is not a tool error.** It raises `AgentModelError` saying to run `ollama serve`
  (or `ollama pull <model>`, or to change `OLLAMA_MODEL` when the model cannot call tools). No other model is tried
  and no tool runs. Any other exception is never disguised: a bug stays a bug.

## Runtime discovery: how a new MCP tool reaches the agent

At the start of every turn the agent asks the server for its tool list again and rebuilds the loop with it. Adding a
tool means adding a module to the server's tools package; the agent is not touched and not restarted. The bridge keeps
each tool's name, description and JSON Schema exactly as the server declares them. The extensibility test starts a
real server with an extra tool and calls it through the agent.

## What the prompt teaches about writing

The prompt names no tool, but it gives these rules (checked by `tests/agent/test_prompt_rules.py`):

- **A confirmation is the order to act.** After a "yes" the agent writes in that turn; it asks again only for a value a tool needs and it does not know.
- **Conflicts are checked, then asked.** Before writing a fact about owners, leads or other documented data, the agent checks it with the knowledge tool. If it contradicts the documentation it says what the documentation says and asks which is right; if not, it writes without asking.
- **Edits quote the text, taken from the passages.** `query_knowledge` returns, besides the answer, the document passages it found (path, section, text, and whether the text is `exact` and not cut). To change an existing document the agent quotes the text to replace from an exact passage, asks again for the section when it is not there, and never invents the text. A wrong quote ends in the update tool's `conflict` result, which tells the model to retry.
- **A new document says what it is about.** The model gives the exact names of the services, APIs or events it concerns (from the conversation or the knowledge tool, never invented); if it cannot tell it asks one question; afterwards it says which links it set and which names were left out.
- **A preview is shown, then confirmed.** The first call to an edit tool only returns a diff; the agent shows it and waits, and repeats the call with `confirmed` only after the person agrees.
- **A gap is not a conflict.** A fact the documentation does not mention is new and is written without asking; only a contradiction is asked about.
- **Paths are inside the service.** The write tools take `doc_path` as the passages give it (`docs/api.md`), never the workspace path `repos/<service>/…`, which the server rejects.
- **Write tools handle markdown documents only.** A new fact goes into a markdown document (for example `docs/product-owner.md`), not into `service.yaml`.

These rules are guidance for the model. The tests with a scripted model prove that the prompt has them and that the loop runs the tools in order; how well a real model follows them has not been measured.

## Knowledge refresh

Documents can change between two questions, including by the agent's own writes. So `query_knowledge` rebuilds the
graph and syncs the index before every question (a no-op when nothing changed, by version hash). The agent and the
MCP server share one workspace: `var/workspace`, a complete copy of the ecosystem created with

```
uv run python scripts/seed_workspace.py
```

## Examples

The examples below run in a test against a scripted chat model: the agent, its loop, the tools, the real MCP server
and the real knowledge flow are used as they are; only the decisions of the models are scripted. A copy of the sample
data is the workspace, so nothing in the project is touched.

```python
import asyncio, shutil, tempfile
from pathlib import Path
from ecosystem_assistant.agent.agent import Agent
from ecosystem_assistant.agent.knowledge import KnowledgeService
from ecosystem_assistant.agent.scripted_chat import ScriptedChat, ai_text, ai_tool
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.scripted import ScriptedLLM

work = Path(tempfile.mkdtemp())
shutil.copytree("data/ecosystem", work / "workspace")
flow_model = ScriptedLLM([
    {"graph_queries": [{"method": "service_owner", "arguments": {"service": "tracking-service"}}]},
    {"answer": "tracking-team owns it and Bruno Salas leads it [K1].", "citations": ["K1"]},
])
knowledge = KnowledgeService(work / "workspace", RetrievalIndex(work / "index", HashingEmbedder()), flow_model, min_score=0.0)
chat = ScriptedChat(script=[
    ai_tool("query_knowledge", {"question": "Who owns the tracking service?"}),
    ai_text("tracking-team owns it, and Bruno Salas leads it [K1]."),
    ai_tool("add_document", {"service": "tracking-service", "doc_path": "docs/lead.md",
                             "content": "# Lead\n\nBruno Salas leads tracking-service.\n"}),
    ai_text("I created docs/lead.md."),
    ai_text("Hello! How can I help?"),
])

async def conversation():
    async with Agent.open(chat=chat, workspace=work / "workspace", audit_file=work / "audit.jsonl", knowledge=knowledge) as agent:
        print(agent.tool_names)
        for message in ["Who owns the tracking service?",
                        "Write that down in a new document docs/lead.md of the tracking-service.", "Thanks!"]:
            reply = await agent.chat(message)
            print([call.name for call in reply.tool_calls], "|", reply.text)

asyncio.run(conversation())
print((work / "workspace/repos/tracking-service/docs/lead.md").read_text().splitlines()[2])
```

```text
['query_knowledge', 'add_document', 'append_to_document', 'update_document', 'mark_document_obsolete', 'link_document']
['query_knowledge'] | tracking-team owns it, and Bruno Salas leads it [K1].
['add_document'] | I created docs/lead.md.
[] | Hello! How can I help?
Bruno Salas leads tracking-service.
```

The same message always goes through the same code. What changes is the model's choice: a question called
`query_knowledge`, a request to write called `add_document`, a greeting called nothing.

A failing tool does not stop the turn. The model receives the server's message and answers:

```python
chat = ScriptedChat(script=[
    ai_tool("add_document", {"service": "ghost-service", "doc_path": "docs/x.md", "content": "x"}),
    ai_text("That service does not exist."),
])

async def failing():
    async with Agent.open(chat=chat, workspace=work / "workspace", audit_file=work / "audit2.jsonl", knowledge=knowledge) as agent:
        reply = await agent.chat("Add a document to ghost-service.")
        record = reply.tool_calls[0]
        print(record.name, record.error)
        print(record.result[:105])
        print(reply.text)

asyncio.run(failing())
```

```text
add_document True
Error executing tool add_document: service 'ghost-service' does not exist in the workspace. Valid service
That service does not exist.
```

## Settings

The agent uses the same variables as the informational flow (and `LLM_PROVIDER`, below): `OLLAMA_MODEL` (default `qwen2.5:7b-instruct`, which
supports tool calling), `OLLAMA_HOST` (`http://localhost:11434`) and `OLLAMA_TIMEOUT`. Also:

| Variable | Default | Meaning |
|---|---|---|
| `AGENT_DATA_ROOT` | `var/workspace` | The workspace shared by the actions and the knowledge side. |
| `ACTIONS_LOG_LEVEL` | `WARNING` | Log level of the MCP server process (its INFO logs would pollute the terminal). |
| `ACTIONS_TOOLS_PACKAGE` | the built-in package | Where the server finds its tools. |
| `ACTIONS_CONFIRM_EDITS` | `on` | `off` turns the preview of edits off (the routing evaluation and the PR review do). |
| `ACTIONS_ALLOWED_SERVICES` | all | Limits which services the server may write. |

## Using Claude instead of the local model

The default model is local (Ollama). To use Claude through the Anthropic API for **both** the flow and the agent, put
this in `.env` (git-ignored; `langgraph dev` reads it, and for the terminal chat export it or run with it set):

```
LLM_PROVIDER=anthropic
```

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` or `anthropic` (`fake` exists for the flow only). |
| `ANTHROPIC_API_KEY` | unset | A key, if you want one. Empty or unset means the `ant auth login` session is used. |
| `ANTHROPIC_MODEL` | `claude-haiku-5-5` | Only models with a price in `llm/pricing.py` are accepted. |
| `ANTHROPIC_MAX_USD` | `1.0` | The cap of the ledger. The call after the cap is refused, before it is sent. |
| `ANTHROPIC_LEDGER` | `.cost_ledger.json` | Where tokens and estimated cost are recorded (shared by the flow and the agent). |

The cap is an estimate of input and output tokens, not an invoice: set a spending limit in the Anthropic Console too.
Nothing local has to run: no `ollama serve`. Failures say what to do: a rate limit says to wait, a missing login
mentions `ant auth login` and `ANTHROPIC_API_KEY`, and the cap names `ANTHROPIC_MAX_USD`.

To check the whole path with real calls (three tiny ones, estimated at $0.00015; the script prints its estimate first):

```
LIVE_LLM=1 uv run python scripts/live_check.py --yes
```

**Status: the three-call check was run on 2026-11-17 and passed 3/3 (about $0.0002); the routing evaluation was run too.** Everything above is tested with fake clients and fake transports; the probe of task 1.2 made three
real calls (JSON with a schema, a plain reply, an effort setting through the chat model) and the login session worked.
The full `live_check` was run with Claude Haiku 5.5: the flow's JSON plan, a plain agent reply and a tool call all passed. The routing evaluation was run with Claude (19/19, see below).

## The routing evaluation

`evaluation/agent.yaml` has 20 turns of five kinds: questions, actions, mixed (look up, then write), chat and
unsupported requests. `scripts/eval_agent.py` runs each in its own fresh copy of the sample data and grades with no
judge model:

- a question, a greeting or an impossible request must call **no action tool** (any MCP tool on them fails the turn);
- an action must call the expected tool, succeed at least once and leave the expected text in the expected file
  (and the text must not have been there before, or the turn proves nothing);
- a turn with no expected effect must leave the workspace and the audit log untouched;
- the reply must contain the expected facts.

```
uv run python scripts/eval_agent.py --min-rate 0.7
```

**Measured with:** `claude-haiku-5-5` (provider `anthropic`, hashing embedder), one run on 2026-11-17 with the tools
of that day (four MCP tools): **16/16** (questions 6/6, actions 4/4, mixed 2/2, chat 2/2, unsupported 2/2), about
$0.016 by the ledger's estimate. Every mixed turn called `query_knowledge` before the write tool, and the chat and
unsupported turns called no tool.

**Weak spot found and fixed (2026-11-18).** The question "A customer sees a stale price. What should we do?" (q03) depended on the agent adding keywords to the question: written as is, the search returned the symptom of the runbook but not its steps. The flow now adds the other sections of the best document (see [informational-flow.md](informational-flow.md)); the same turn then passed 6 of 6 runs, and the full evaluation 18/19 with a02 failing once (it passed 6 of 6 when run alone, with and without the change).

**Third run, after `add-document-links-writing`** (20 turns, one added for a document created with its links): **20/20**, about $0.04. The PR review set gave 5/6 with r02 (update a document) failing; run alone five times it passed 4 of 5 both with and without this change, so it is the model's variance on that case. By hand with Claude: a document about the payments flow was written with `about: ["payments-api"]`, a plain note with `about: ["orders-service"]`, and the next question "which documents talk about payments-api?" used `documents_about` and listed the new one.

**Second run, after `fix-team-leads-and-doc-paths`** (same model, 19 turns, three of them added from the first real session: all teams with their leads, and two appends to a README): **19/19** (questions 7/7, actions 4/4, mixed 4/4, chat 2/2, unsupported 2/2), about $0.03. Before the fix, the same session had shown a wrong-path write and an incomplete list of leads. Read it with care: 19 turns written by the project, one run (the model is not
deterministic), one model. The grading rules, the report and the isolation between turns are also tested with
scripted models. Nothing is claimed about `qwen2.5:7b-instruct`: the run with Ollama has not been made.

## Limits

- Routing quality is whatever the model gives. A small local model may call the wrong tool; the evaluation exists to
  measure that, and tool descriptions are the lever to improve it.
- An informational question costs about four model calls (the agent's decision, the flow's plan, the flow's answer
  and the agent's final reply), so it is slow on a local model.

## Measured cost and time per turn

Measured on 2026-11-18 with `claude-haiku-5-5`, one run, a throwaway script that wraps the ledger's `record` to log
each call (the script is not kept in the repository):

| Turn | Calls | Input / output tokens | Time | Cost (estimate) |
|---|---|---|---|---|
| A question (owner and lead) | 4 | 9,194 / 308 | 3.9 s | $0.0011 |
| A question answered from a runbook | 4 | 9,626 / 774 | 5.5 s | $0.0014 |
| All teams and their leads | 4 | 9,282 / 558 | 4.4 s | $0.0012 |
| Look up and write (append) | 5 | 16,339 / 963 | 6.6 s | $0.0021 |
| A greeting | 1 | 3,419 / 48 | 0.9 s | $0.0004 |

Each call takes about one second and they run one after another, so the time is the number of calls. The two calls of
the agent carry the system prompt and the tool schemas (about 3,400 tokens) and are the biggest inputs. No prompt
caching is used. At these prices a dollar pays for roughly 800 to 900 questions, so cost is not a problem today;
latency is the visible part. Caching the fixed prefix could cut about 40 % of the input cost (about $0.0005 per
question) and little time; removing the agent's final call would save one second but the agent would stop composing
the answer, so neither is done.
- Editing a document and marking it obsolete show a diff first and write only after the person agrees (the server
  setting `ACTIONS_CONFIRM_EDITS`, on by default). Creating a document and appending text are direct, because they
  overwrite nothing; every write is in the audit log.
- Documents created from the chat are not known to the graph until a manifest lists them (see
  [roadmap.md](roadmap.md)).
- `grounded` in a knowledge answer means "cites existing evidence", not "is true".
