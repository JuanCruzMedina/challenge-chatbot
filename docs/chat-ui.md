# Chat interfaces

Two ways to talk to the same agent. Neither contains logic: they send the conversation and show what comes back. What
the agent does with a message is decided by the model ([agent.md](agent.md)).

## 1. Terminal chat

```
uv run python scripts/seed_workspace.py        # once: the workspace both sides share
uv run python -m ecosystem_assistant.chat      # needs `ollama serve` running
```

Type a message; type `/exit` (or press Ctrl-D / Ctrl-C) to leave. After each reply, a line shows the tools the model
called in that turn, so the routing is visible: `query_knowledge` for a question, an MCP tool for an action, nothing for
small talk. The conversation is kept in memory for the session only.

If the model server is down, or the model cannot call tools, the message of the error is printed (for example "start
it with `ollama serve`") and the session stays open. Any other error is a bug and is not hidden. `--workspace PATH`
overrides `AGENT_DATA_ROOT` (default `var/workspace`).

A session, run by a test with the agent's real loop, real tools and real MCP server, and scripted models:

```python
import shutil, tempfile
from pathlib import Path
from ecosystem_assistant.agent.agent import Agent
from ecosystem_assistant.agent.knowledge import KnowledgeService
from ecosystem_assistant.agent.scripted_chat import ScriptedChat, ai_text, ai_tool
from ecosystem_assistant.chat.__main__ import main
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
    ai_text("Hello! How can I help?"),
])

def factory(workspace):
    return Agent.open(chat=chat, workspace=workspace, audit_file=work / "audit.jsonl", knowledge=knowledge)

typed = iter(["Who owns the tracking service?", "hi", "/exit"])
main(["--workspace", str(work / "workspace")], agent_factory=factory, read=lambda prompt: next(typed))
```

```text
Type your message, or /exit to leave.
assistant> tracking-team owns it, and Bruno Salas leads it [K1].
  ↳ called: query_knowledge
assistant> Hello! How can I help?
```

## 2. The web UI (LangChain Agent Chat UI)

```
uv run langgraph dev --no-browser              # serves the agent on http://localhost:2024
```

Then open the public Agent Chat UI page in your browser and connect it to `http://localhost:2024` with graph ID
`agent`. The page is a ready-made frontend; nothing of it is installed or written here. It shows the messages and the
tool calls and results. The conversation is sent from your browser to your machine; the model is the local Ollama one.

`langgraph.json` registers one graph, `agent`, built by `ecosystem_assistant.chat.server_graph`. LangGraph calls that
factory on every run, so it starts the MCP server, lists its tools again, builds the agent's own loop with them and
stops the server when the run ends. A tool added to the server is therefore available in the next conversation, with
no change to the agent. The settings are the same environment variables as the agent (`OLLAMA_*`, `AGENT_DATA_ROOT`);
LangGraph reads a `.env` file, which is git-ignored.

### What was verified, and what was not

Verified (task 4.3 of the change): `langgraph dev` started with the real factory and scripted models; a question and an
action posted to its API returned the tool call, the tool result and the reply, the action wrote its document, a
streamed run (`threads/.../runs/stream`, what a web client uses) delivered its events, and no process remained after
stopping. Running it also exposed that blocking file-system calls on the event loop are rejected by the server, which
is now covered by a test with the same detector.

**Not verified: the browser page itself.** That the hosted Agent Chat UI renders this server, and that the browser
accepts a connection from that page to `localhost` (cross-origin), was not tried. It is the manual step 5.3: connect,
ask a question, ask for an action, and report what happens.

## Limits

- No streaming of the reply token by token in the terminal; the whole reply is printed when the turn ends.
- The conversation is not saved between sessions in the terminal. The web server keeps threads in memory while it runs.
- Each informational question costs about four model calls, so replies are slow on a local model.
- The routing quality of the real model has not been measured ([agent.md](agent.md)).
