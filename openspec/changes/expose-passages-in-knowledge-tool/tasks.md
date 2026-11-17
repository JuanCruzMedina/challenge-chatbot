# Tasks

## 1. Passages in the answer
- [ ] 1.1 Write a failing test that every passage of the sample data is an exact substring of its file (shows what the chunker does); decide D-1 and record it in the design.
- [ ] 1.2 Write failing tests for the three flow scenarios; add `passages` to the answer with the truncation and exactness marks.

## 2. The tool and the prompt
- [ ] 2.1 Write failing tests for the three agent scenarios (tool result, scripted edit with a quoted passage, prompt rule and no tool names); update `render`, the tool description and the prompt (still under 40 lines).

## 3. Closing
- [ ] 3.1 Update `docs/agent.md` and `docs/informational-flow.md`; run the suite, the data validator and `OPENSPEC_TELEMETRY=0 openspec validate expose-passages-in-knowledge-tool --strict`; map scenarios to tests.
