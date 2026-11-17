# The agent

The agent is the one entry point of the assistant. It receives a message, gives it to a chat model together with a list
of tools, runs the tools the model asks for and returns the reply. **The code never decides what a message is.** The
decision belongs to the model, which reads the tool descriptions.

## The tools

| Tool | Where it comes from | What it is for |
|---|---|---|
| `query_knowledge` | `agent/knowledge.py` | Every informational question. It wraps the whole flow of [informational-flow.md](informational-flow.md) (graph + documents, cited answer). It is the **only** way the agent reads knowledge. |
| every tool the MCP server lists | discovered at runtime by `agent/mcp_tools.py` | Actions: today `add_document`, `update_document`, `mark_document_obsolete`. |

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
['query_knowledge', 'add_document', 'update_document', 'mark_document_obsolete']
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

The agent uses the same variables as the informational flow: `OLLAMA_MODEL` (default `qwen2.5:7b-instruct`, which
supports tool calling), `OLLAMA_HOST` (`http://localhost:11434`) and `OLLAMA_TIMEOUT`. Also:

| Variable | Default | Meaning |
|---|---|---|
| `AGENT_DATA_ROOT` | `var/workspace` | The workspace shared by the actions and the knowledge side. |
| `ACTIONS_LOG_LEVEL` | `WARNING` | Log level of the MCP server process (its INFO logs would pollute the terminal). |
| `ACTIONS_TOOLS_PACKAGE` | the built-in package | Where the server finds its tools. |

## The routing evaluation

`evaluation/agent.yaml` has 16 turns of five kinds: questions, actions, mixed (look up, then write), chat and
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

**Measured with:** scripted models only. The grading rules, the report and the isolation between turns are tested; the
rate of a real model has **not** been measured yet (the run with Ollama is optional and was not requested). Until
it is run, no claim is made about how well `qwen2.5:7b-instruct` routes.

## Limits

- Routing quality is whatever the model gives. A small local model may call the wrong tool; the evaluation exists to
  measure that, and tool descriptions are the lever to improve it.
- An informational question costs about four model calls (the agent's decision, the flow's plan, the flow's answer
  and the agent's final reply), so it is slow on a local model.
- Writes have no confirmation step. This is deliberate: the workspace is a throwaway copy and every write is in the
  audit log.
- Documents created from the chat are not known to the graph until a manifest lists them (see
  [roadmap.md](roadmap.md)).
- `grounded` in a knowledge answer means "cites existing evidence", not "is true".
