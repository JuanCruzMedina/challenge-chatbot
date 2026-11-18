# Test guide

Phrases to paste into the chat, with the answer to expect for each one. All data is **invented** (a fictional company, "Demo Studio").

Every phrase below was run in English with Claude Haiku 5.5 on 2026-11-18 (one run, from the initial data), and the expected answers describe what that run returned. The wording changes from run to run; what matters is the data and the tool that was used. The same phrases were tried by hand in Spanish before, with the same results.

## 1. Start it

```bash
uv sync
uv run python scripts/seed_workspace.py          # a clean workspace (var/workspace)
echo 'LLM_PROVIDER=anthropic' > .env             # needs ANTHROPIC_API_KEY or an `ant auth login` session
uv run langgraph dev --no-browser                # server on http://localhost:2024
```

- Web chat: <https://agentchat.vercel.app/?apiUrl=http://localhost:2024&assistantId=agent> (the pencil starts a new thread).
- Terminal chat: `uv run python -m ecosystem_assistant.chat`.
- Spending is capped by `ANTHROPIC_MAX_USD` (1 USD by default). The whole guide costs about 3 cents.
- Without `LLM_PROVIDER=anthropic` the project uses a local Ollama model, which was **not** measured: answers may differ from this guide.

Run `seed_workspace.py` again to go back to the initial documents after trying the writes.

## 2. The invented data

**Company:** Demo Studio. **Clients:** Demo Grocery and Demo Logistics.

| Application | Client | Services |
|---|---|---|
| Storefront | Demo Grocery | catalog, orders, payments, notifications |
| Driver App | Demo Logistics | driver |
| Fleet Tracker | Demo Logistics | tracking, routing |

| Service | Team | Tech lead | Provides API | Consumes API | Publishes events | Subscribes to |
|---|---|---|---|---|---|---|
| catalog-service | catalog-team | Nora Beltrán | catalog-api | — | product.price_changed | — |
| orders-service | orders-team | Tomás Aguirre | orders-api | catalog-api, payments-api | order.created, order.cancelled | payment.confirmed, payment.failed, product.price_changed |
| payments-service | payments-team | Valeria Sosa | payments-api (v1) | — | payment.confirmed, payment.failed | order.created |
| notifications-service | communications-team | Iván Prado | — | — | — | order.created, order.cancelled, payment.failed |
| driver-service | driver-team | Diego Núñez | — | tracking-api | — | route.assigned |
| tracking-service | tracking-team | Bruno Salas | tracking-api | — | vehicle.position_updated | — |
| routing-service | routing-team | Elena Pardo | — | — | route.assigned | vehicle.position_updated |

**Product Owners:** Sofía Mendoza (Demo Grocery) and Camila Ortega (Demo Logistics).

**Documents with concrete answers:**

- `payments-service/docs/api-v1.md`: payments-api v1 does not support automatic retries; the result of a charge is asynchronous (`payment.confirmed` or `payment.failed`). v1 is active. Its deprecation exists only in the simulated pull request PR-101, which is not applied to the data.
- `catalog-service/docs/api.md`: 200 requests per minute per consumer. `tracking-service/docs/api.md`: 300 per minute.
- Runbooks: stale prices (catalog), order stuck in `PAYMENT_PENDING` (orders), failed payments (payments), delayed emails (notifications), vehicle missing from the map (tracking).
- ADR-001 of orders-service: event-driven architecture.

## 3. Phrases and expected answers

Each phrase is in its own block so it can be copied whole. Start a new thread for each group.

### Read and search

**1.**

```text
List every team and who leads each one.
```

**Expect:** `query_knowledge`, then the seven teams with their tech lead: catalog-team (Nora Beltrán), communications-team (Iván Prado), driver-team (Diego Núñez), orders-team (Tomás Aguirre), payments-team (Valeria Sosa), routing-team (Elena Pardo), tracking-team (Bruno Salas).

**2.**

```text
Who owns the tracking service and who leads it?
```

**Expect:** tracking-team owns tracking-service and Bruno Salas leads it, with citations such as `[K1]` (graph) and `[D1]` (README).

**3.**

```text
Who consumes the payments API, and which versions are deprecated?
```

**Expect:** orders-service consumes payments-api. No version is deprecated: v1 is the only one and it is active.

**4.**

```text
A customer sees a stale price. What should we do?
```

**Expect:** the steps of the stale-prices runbook: query `GET /products/{id}` on catalog-service, check whether `product.price_changed` was published, and if orders-service shows another value, invalidate its cache and notify orders-team; if the load failed, retry it from the commercial panel. Escalation: catalog-team.

**5.**

```text
How many requests per minute may a consumer make to the catalog API?
```

**Expect:** 200 per minute per consumer; over the limit it returns `429`.

**6.**

```text
Which applications does Demo Logistics have, and which services does each one have?
```

**Expect:** Driver App (driver-service) and Fleet Tracker (routing-service and tracking-service).

**7.**

```text
Who is the Product Owner of Demo Grocery?
```

**Expect:** Sofía Mendoza, from the client's product vision document.

### Write and link

**8.**

```text
Create the document docs/payments-usage.md in orders-service explaining that orders-service consumes the payments API to charge every order.
```

**Expect:** it checks the facts with `query_knowledge`, then calls `add_document` without asking for confirmation, with `about: ["payments-api"]`, and says which links it set. Check it with `cat var/workspace/repos/orders-service/docs/payments-usage.md`.

**9.** (same thread as 8)

```text
Which documents talk about payments-api?
```

**Expect:** `orders-service/docs/payments-usage.md` as the document the graph links to the API. It may also list documents that only name the API in their text (`payments-service/docs/api-v1.md`, the READMEs), saying that those are not linked in the graph.

**10.**

```text
Add to the README of driver-service that Gaspar Noriega is the Product Owner of driver-team.
```

**Expect:** `append_to_document` adds a line at the end of the README of driver-service, with no question first: the documentation had no Product Owner for that team, so it is a new fact and not a conflict. If you ran it before, the line appears twice.

### Edit (these ask for confirmation)

**11.**

```text
In payments-service, in docs/api-v1.md, change the retry rule: v1 now retries up to 3 times.
```

**Expect:** it finds the current rule ("v1 does **not** support automatic retries…"), shows the old and the new text and asks whether to apply it. Nothing is written yet.

Answer:

```text
Yes, apply it.
```

**Expect:** it confirms the rule was replaced; `api-v1.md` now says v1 retries up to 3 times.

**12.**

```text
Mark docs/api-v1.md of payments-service as obsolete, replaced by docs/api-v2.md.
```

**Expect:** it shows the front matter it would add (`status: obsolete`, `obsolete_reason`, `replaced_by: docs/api-v2.md`) and waits.

Answer:

```text
Yes.
```

**Expect:** it confirms the document is marked obsolete; the body is unchanged.

**13.** (needs phrase 8 first)

```text
Change the links of docs/payments-usage.md in orders-service: it is now also about payments-service.
```

**Expect:** `link_document` leaves `about` with `payments-api` and `payments-service`, and reports the previous list (`payments-api`). No confirmation, because only the front matter changes.

### Conflicts and limits

**14.**

```text
The lead of orders-team is Juan Pérez.
```

**Expect:** it says the documentation names Tomás Aguirre as tech lead of orders-service and asks which one is correct. Nothing is modified.

Answer:

```text
Keep the current one, change nothing.
```

**Expect:** it confirms that nothing was changed and Tomás Aguirre stays.

**15.**

```text
Delete orders-service completely.
```

**Expect:** it says it cannot delete services or files (it can read, create, append, edit, mark as obsolete and link) and offers to mark documents as obsolete or to add a note. No write tool is called.

**16.**

```text
Hi, how are you?
```

**Expect:** a short greeting and what it can do. No tool is called.

### Mixed

**17.**

```text
Check who leads tracking-service and write it down in a document docs/lead.md of that service.
```

**Expect:** it asks first (Bruno Salas, tech lead of tracking-team) and then creates `docs/lead.md`, saying it linked it to `tracking-service`.

## 4. Review the documentation of a pull request

This runs in the terminal, not in the chat. The pull request is invented (`data/ecosystem/prs/pr-101-payments-api-v2/pr.yaml`: payments-api v2 with automatic retries, v1 deprecated). `--dry-run` works on a copy and changes nothing; each run costs a few cents.

```bash
LLM_PROVIDER=anthropic uv run python -m ecosystem_assistant.pr_review data/ecosystem/prs/pr-101-payments-api-v2/pr.yaml --dry-run
```

**Expect:** it proposes a change to the documentation of payments-service (the retry rule of `docs/api-v1.md`, or a document for v2) and prints the diff, with the line `dry run: nothing was written for real`. It can differ between runs.

To see the case where **nothing** should change, copy that file, change the id, the title and the description to a refactor (for example `Renames internal functions, no behavior change.`) and run it again:

```bash
cp data/ecosystem/prs/pr-101-payments-api-v2/pr.yaml /tmp/pr-refactor.yaml
# edit /tmp/pr-refactor.yaml: id PR-102, a refactor title and description
LLM_PROVIDER=anthropic uv run python -m ecosystem_assistant.pr_review /tmp/pr-refactor.yaml --dry-run
```

**Expect:** `no documentation change`, with a short explanation of why the documentation does not need to change.

## 5. What to look at critically

- Answers cite evidence (`[K1]` from the graph, `[D2]` from documents). Citing existing evidence does not prove the answer is true.
- The model is not deterministic: a different phrasing, or the same phrase again, can give a different result. The review of the retries pull request is right about 4 times out of 5.
- A new document is searchable from the next question on; the graph sees it through its `about` links.
- A new document can stay unlinked if the model forgets a name; fix it with phrase 13.
- Measured with Claude Haiku 5.5 only: routing 20/20 and pull request review 5/6 or 6/6 depending on the run (small sets, one model).
