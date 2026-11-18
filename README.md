# Ecosystem Assistant

A chatbot for the documentation of a microservices ecosystem. It answers questions with citations from a Knowledge Graph and a document index, and it changes documentation through an MCP server. The model alone decides which of the two routes a message needs.

Built for the challenge "Multi-Source Chatbot with Intelligent Agent Orchestration". **All data is invented** (a fictional company, "Demo Studio"). It is a working prototype, not a production system.

## How it works

```
Chat (terminal or Agent Chat UI, passive)
  └─ Agent: a two-node loop (model, tools). The model picks tools by tool calling.
       ├─ query_knowledge ── one centralized flow: plan → graph queries + document search → answer → check
       │                       ├─ Knowledge Graph (NetworkX)
       │                       └─ document index (Chroma, RAG)
       └─ MCP server (stdio) ── 5 write tools, closed JSON Schemas, audit log
                               └─ markdown documents of each service (the workspace)
```

- **Questions** go through one tool, `query_knowledge`, which wraps the whole RAG + Knowledge Graph flow.
- **Actions** go only through the MCP server: `add_document`, `append_to_document`, `update_document`, `mark_document_obsolete`, `link_document`.
- **No routing code.** The agent has no `if/else` on the message and no keyword matching; static tests check the source.
- **Tools are discovered at runtime.** A new tool is a new module in `src/ecosystem_assistant/actions/tools/`; the agent lists the server's tools again at every turn.
- **Ingestion is separate.** Building the graph and syncing the index (only changed files are embedded again) is its own code, run before each question; the agent and the answer flow do not parse documents.
- **PR review.** A command gives a merged pull request to the same agent, which adds documentation, updates it, or changes nothing.

## Run it

Requirements: Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/). For the model, either Claude (an `ANTHROPIC_API_KEY`, or an `ant auth login` session) or a local Ollama with `qwen2.5:7b-instruct`. Everything measured in this repository was measured with Claude Haiku 5.5; Ollama is supported but not measured.

```bash
uv sync
uv run python scripts/seed_workspace.py        # a copy of the invented data that the chat may change (var/workspace)
echo 'LLM_PROVIDER=anthropic' > .env           # leave it out to use Ollama
export ANTHROPIC_API_KEY=...                   # not needed with an `ant auth login` session
uv run langgraph dev --no-browser              # server on http://localhost:2024
```

- Web chat: <https://agentchat.vercel.app/?apiUrl=http://localhost:2024&assistantId=agent>
- Terminal chat: `uv run python -m ecosystem_assistant.chat`

With Claude, spending is estimated in a local ledger and capped (`ANTHROPIC_MAX_USD`, default 1 USD). A question costs about $0.001 to $0.002. Run `seed_workspace.py` again to go back to the initial documents.

## Try it

[docs/guia-de-prueba.md](docs/guia-de-prueba.md) (in Spanish) has the invented data in tables and 17 phrases to paste, each with the answer to expect. A short sample:

| Say | Expect |
| --- | --- |
| `Who owns the tracking service and who leads it?` | `query_knowledge`; tracking-team, Bruno Salas, with citations |
| `In payments-service, in docs/api-v1.md, change the retry rule: v1 now retries up to 3 times.` | A diff and a question; it writes only after you agree |
| `The lead of orders-team is Juan Pérez.` | It says the documentation names Tomás Aguirre and asks which is right; nothing is written |
| `Delete orders-service completely.` | It refuses: no tool deletes |

Review the documentation of a merged pull request (invented PR, nothing is written with `--dry-run`):

```bash
LLM_PROVIDER=anthropic uv run python -m ecosystem_assistant.pr_review data/ecosystem/prs/pr-101-payments-api-v2/pr.yaml --dry-run
```

## The MCP server on its own

The actions server is a normal MCP server over stdio. Any MCP client can start it:

```json
{
  "mcpServers": {
    "ecosystem-assistant-actions": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/this/repo", "python", "-m", "ecosystem_assistant.actions.server"],
      "env": { "DOCS_WORKSPACE": "/path/to/this/repo/var/workspace" }
    }
  }
}
```

Checked with an MCP client (it lists the five tools). Not tried inside an editor such as VS Code.

## Tests

```bash
uv run pytest tests -q        # 712 tests, about 45 s, free: no test calls a real model
```

The scripts in `scripts/eval_*.py` measure a real model and spend a few cents each; see [docs/agent.md](docs/agent.md).

## How it would run in production

None of this is deployed. It is the intended shape, with what exists today:

| Piece | In production | Today |
| --- | --- | --- |
| Chat | The agent server behind the team's chat UI, with the documentation repositories as the workspace | Runs locally with `langgraph dev` and the hosted Agent Chat UI |
| Actions | The MCP server over HTTP with authentication, one scope of services per session | stdio only; the per-session scope (`ACTIONS_ALLOWED_SERVICES`) and edit confirmation exist |
| PR review | A CI job on merge runs `pr_review` and commits the changed documents or opens a pull request | The command and an example job exist ([docs/pr-review.md](docs/pr-review.md)); fetching the PR and committing are not built |
| Data | Real repositories: OpenAPI files, `CODEOWNERS`, ADRs | Invented manifests and markdown only |
| Model | A decision about privacy before real code is sent to an external model | Claude Haiku 5.5 or a local Ollama model |

## Documentation

- [docs/evaluation-criteria.md](docs/evaluation-criteria.md): the six criteria of the brief, with evidence and what is not proven. **Start here.**
- [docs/agent.md](docs/agent.md), [docs/informational-flow.md](docs/informational-flow.md), [docs/knowledge-graph.md](docs/knowledge-graph.md), [docs/retrieval-index.md](docs/retrieval-index.md), [docs/actions-server.md](docs/actions-server.md), [docs/pr-review.md](docs/pr-review.md), [docs/chat-ui.md](docs/chat-ui.md): one per part.
- [docs/design-decisions.md](docs/design-decisions.md) and [docs/roadmap.md](docs/roadmap.md): why it is built this way and what comes next.
- `openspec/specs/`: the behavior, as specifications with scenarios.

## Limits

- Measured with one model (Claude Haiku 5.5) on small sets written by the project: routing 20/20, PR review 5/6 or 6/6 depending on the run.
- An answer that is "grounded" cites existing evidence; that does not prove it is true.
- A question takes about four model calls (4 to 6 seconds).
- A new document can stay unlinked if the model forgets a name; validation stops invented names, not missing ones.
