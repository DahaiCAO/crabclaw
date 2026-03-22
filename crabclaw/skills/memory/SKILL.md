---
name: memory
description: Two-layer memory system with grep-based recall.
always: true
---

# Memory

## Structure

- `memory/semantic.json` - Global long-term facts. Always loaded into your context.
- `memory/episodic.jsonl` - Global append-only event log. NOT loaded into context. Search it with grep.
- `portfolios/<user_id>/memory/semantic.json` - User-specific long-term facts. Loaded into context when chatting with that user.
- `portfolios/<user_id>/memory/episodic.jsonl` - User-specific event log. NOT loaded into context.

## Search Past Events

Use the `search_deep_memory` tool to run natural language semantic searches over the episodic event log.
Example: "What did the user say about their project architecture?"
This replaces the old grep method.

## When to Update semantic.json

Write important facts immediately using `edit_file` or `write_file` to the JSON files:
- User preferences ("I prefer dark mode" -> `portfolios/<user_id>/memory/semantic.json`)
- Global technical rules ("Use typing" -> `memory/semantic.json`)

## Auto-consolidation

Old conversations are automatically summarized and appended to episodic.jsonl when the session grows large. Long-term facts are extracted to semantic.json. You don't need to manage this manually unless you want to record an immediate fact.
