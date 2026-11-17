# Design

## Context
Motivation in `proposal.md`. Invariants: informational reads go only through `query_knowledge`; writes only through MCP tools; the agent code does not name tools and has no routing.

## Decisions

**D-1. Listing is a graph query, not a new tool.** `list_entities(type)` returns the name and id of every node of that type (`team`, `person`, `service`, `client`, `application`, `api`, `event`, `feature`), sorted, with the files they come from. An unknown type returns the valid types, as `NotFound` does elsewhere. Alternative: a second agent tool; rejected, it would split reads across two paths.

**D-2. `team_overview(team)`** returns the team, the services it owns (OWNED_BY) and the person leading each (LED_BY), so "who is in each team" is one query per team. Today the only people in the data are tech leads; the answer says so through the data, not through code.

**D-3. `append_to_document`.** Same path rules as the other tools (`resolve_doc`, `.md` only, existing service). If the file exists, the text is added after a blank line, keeping the file's newline style and ensuring one trailing newline; otherwise the file is created with the text. Writes are atomic and audited with the action name. Empty text is rejected. Outcomes: `appended` or `created`. It cannot conflict with another writer in a way that loses data, because it reads and writes in one atomic replace; two simultaneous appends could still overwrite one another, which is a documented limit of the single-user workspace.

**D-4. Conflicts are the model's judgment, taught by the prompt.** The prompt says: before writing a statement about owners, leads, dependencies or other facts, check it with the knowledge tool; if it contradicts the documentation, tell the person what exists and ask which is right; if it does not, write. A "yes" ends the asking. No code inspects text. The test uses a scripted model, so it proves the prompt contains the rules and the loop runs the tools in the scripted order, not how well Claude follows them; that is measured only in the optional real run.

## Risks
- A model may still over-ask; the optional real-model run measures it.
- Prompt growth: kept under 30 lines.
