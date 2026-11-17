# Design

## Context
`Passage` (flow/evidence.py) holds `text`, which starts with the heading path, plus path and heading path. The chunker (`retrieval/chunking.py`) builds `text` as heading path + body; the body is what must match the file.

## Decisions

**D-1. Verbatim is checked, not assumed.** The first task verifies with a test that a passage body is a contiguous substring of its source file for every document of the sample data. Where the chunker normalizes text (whitespace, code fences), the exposed text is taken from the file by the chunk's recorded position, or the passage is marked `exact: false` and the prompt tells the model not to quote from it. The choice is made when the test shows what the chunker does; it does not weaken the spec (an exact passage is a substring of the file).

**D-2. Where it lives.** `Answer` gets a `passages` field (`id`, `path`, `heading_path`, `text`, `truncated`, `exact`). `agent/knowledge.py:render` adds it to the JSON. The flow's behavior (planning, retrieval, checking) is unchanged.

**D-3. Size.** A passage is cut at 1,500 characters with `truncated: true`. The prompt rule says that a truncated passage is not a valid source for a quote.

**D-4. The prompt rule is guidance.** Tests with a scripted model prove the tool returns the passages and that a scripted turn can quote one and edit successfully; how well a real model quotes is measured by the routing evaluation and the PR review evaluation of the next change.
