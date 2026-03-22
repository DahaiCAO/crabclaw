# Semantic Memory Template

This template defines how structured JSON memory is presented to the LLM. It is no longer used for raw text storage.

## Memory Structure

Crabclaw maintains a two-layer memory architecture to ensure both universal learning and strict privacy.

### 1. Global Semantic Memory
These are universal facts, general knowledge, or coding preferences that apply to all users and sessions.
- **Source**: `workspace/memory/semantic.json`

### 2. User Specific Memory
These are personal preferences, private context, or project states specifically tied to the current user.
- **Source**: `workspace/portfolios/<user_id>/memory/semantic.json`

---

*Note: The actual JSON content will be dynamically injected below this template by the ContextBuilder using BM25 RAG when the memory size exceeds the threshold.*

