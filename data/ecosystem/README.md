# Sample ecosystem: "Demo Grocery"

**Everything in this folder is invented.** The company, teams, people, services, APIs, URLs and dates are fictional and do not represent any real organization or person.

```text
repos/       4 microservices (one "repo" per folder, with service.yaml + docs)
product/     product vision and the feature/epic catalog
prs/         simulated PRs used to test incremental ingestion
```

Each service declares in its `service.yaml`: owner, APIs it provides and consumes, events it publishes and subscribes to, docs, and the features it implements. Those relations feed the Knowledge Graph. The text of the `.md` files feeds the RAG.
