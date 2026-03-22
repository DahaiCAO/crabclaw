"""Memory system for persistent agent memory."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from crabclaw.utils.helpers import ensure_dir, safe_filename

if TYPE_CHECKING:
    from crabclaw.providers.base import LLMProvider
    from crabclaw.session.manager import Session


_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save the memory consolidation result to persistent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "global_semantic_updates": {
                        "type": "object",
                        "description": "Updated GLOBAL knowledge base (key-value pairs). Extract ONLY generic knowledge, rules, code patterns, or abstract concepts here. NO USER PRIVATE INFO. Return empty object if nothing new.",
                    },
                    "user_semantic_updates": {
                        "type": "object",
                        "description": "Updated user-specific long-term facts (preferences, private data, ongoing project context). Return empty object if nothing new.",
                    },
                    "user_episodic_entry": {
                        "type": "string",
                        "description": "A paragraph (2-5 sentences) summarizing key events/decisions/topics for this user. Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search.",
                    },
                },
                "required": ["global_semantic_updates", "user_semantic_updates", "user_episodic_entry"],
            },
        },
    }
]


def _ensure_text(value: Any) -> str:
    """Normalize tool-call payload values to text for file storage."""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _ensure_dict(value: Any) -> dict:
    """Normalize tool-call payload values to dict for json storage."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}


def _get_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class MemoryStore:
    """Two-layer memory: semantic.json (long-term facts) + episodic.jsonl (grep-searchable log)."""

    _MAX_FAILURES_BEFORE_RAW_ARCHIVE = 3

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.global_memory_dir = ensure_dir(workspace / "memory")
        self.global_semantic_file = self.global_memory_dir / "semantic.json"
        self.global_episodic_file = self.global_memory_dir / "episodic.jsonl"
        self.portfolios_root = ensure_dir(workspace / "portfolios")
        self._consecutive_failures = 0
        
        # Ensure global semantic exists
        if not self.global_semantic_file.exists():
            self.global_semantic_file.write_text("{}", encoding="utf-8")

    @staticmethod
    def _normalize_user_scope(user_scope: str | None) -> str | None:
        if user_scope is None:
            return None
        value = str(user_scope).strip()
        return value or None

    def _get_user_memory_dir(self, user_scope: str) -> Path:
        """Get local memory directory within user portfolio."""
        user_dir = ensure_dir(self.portfolios_root / safe_filename(user_scope) / "memory")
        return user_dir

    def _get_user_memory_paths(self, user_scope: str) -> tuple[Path, Path]:
        user_dir = self._get_user_memory_dir(user_scope)
        semantic_file = user_dir / "semantic.json"
        episodic_file = user_dir / "episodic.jsonl"
        
        if not semantic_file.exists():
            semantic_file.write_text("{}", encoding="utf-8")
            
        return semantic_file, episodic_file

    def read_global_semantic(self) -> dict:
        if self.global_semantic_file.exists():
            try:
                return json.loads(self.global_semantic_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def read_user_semantic(self, user_scope: str) -> dict:
        semantic_file, _ = self._get_user_memory_paths(user_scope)
        if semantic_file.exists():
            try:
                return json.loads(semantic_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def write_global_semantic(self, data: dict) -> None:
        self.global_semantic_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_user_semantic(self, data: dict, user_scope: str) -> None:
        semantic_file, _ = self._get_user_memory_paths(user_scope)
        semantic_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_global_episodic(self, entry: str) -> None:
        with open(self.global_episodic_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": _get_timestamp(), "entry": entry}, ensure_ascii=False) + "\n")

    def append_user_episodic(self, entry: str, user_scope: str) -> None:
        _, episodic_file = self._get_user_memory_paths(user_scope)
        with open(episodic_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": _get_timestamp(), "entry": entry}, ensure_ascii=False) + "\n")

    def get_memory_context(self, user_scope: str | None = None, query: str | None = None, max_items: int = 20) -> str:
        """Called by ContextBuilder to inject JSON data into prompt.
        If the memory is too large, it uses BM25 to retrieve the most relevant items based on the query.
        """
        global_sem = self.read_global_semantic()
        user_sem = self.read_user_semantic(user_scope) if user_scope else {}
        
        # Check if we need to filter
        total_items = len(global_sem) + len(user_sem)
        if total_items > max_items and query:
            from crabclaw.agent.retriever import BM25Retriever
            retriever = BM25Retriever()
            
            docs = []
            for k, v in global_sem.items():
                docs.append({"id": f"global:{k}", "type": "global", "key": k, "content": f"{k}: {v}", "raw_val": v})
            for k, v in user_sem.items():
                docs.append({"id": f"user:{k}", "type": "user", "key": k, "content": f"{k}: {v}", "raw_val": v})
                
            retriever.add_documents(docs)
            results = retriever.search(query, top_k=max_items)
            
            # Reconstruct filtered dictionaries
            filtered_global = {}
            filtered_user = {}
            for res in results:
                if res["type"] == "global":
                    filtered_global[res["key"]] = res["raw_val"]
                else:
                    filtered_user[res["key"]] = res["raw_val"]
                    
            global_sem = filtered_global
            user_sem = filtered_user
        
        context_parts = []
        if global_sem:
            context_parts.append(f"## 全局认知 (Global Semantic)\n```json\n{json.dumps(global_sem, ensure_ascii=False, indent=2)}\n```")
            
        if user_sem:
            context_parts.append(f"## 当前用户档案 (User Specific)\n```json\n{json.dumps(user_sem, ensure_ascii=False, indent=2)}\n```")
                
        return "\n\n".join(context_parts)

    def search_episodic_memory(self, query: str, user_scope: str | None = None, top_k: int = 10) -> str:
        """Search through episodic JSONL files using BM25."""
        from crabclaw.agent.retriever import BM25Retriever
        retriever = BM25Retriever()
        docs = []
        
        # Load global episodic
        if self.global_episodic_file.exists():
            with open(self.global_episodic_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        data = json.loads(line)
                        docs.append({"content": data.get("entry", ""), "type": "global", "timestamp": data.get("timestamp", "")})
                    except Exception: pass
                    
        # Load user episodic
        if user_scope:
            _, episodic_file = self._get_user_memory_paths(user_scope)
            if episodic_file.exists():
                with open(episodic_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            data = json.loads(line)
                            docs.append({"content": data.get("entry", ""), "type": "user", "timestamp": data.get("timestamp", "")})
                        except Exception: pass
                        
        retriever.add_documents(docs)
        results = retriever.search(query, top_k=top_k)
        
        if not results:
            return "No relevant memories found."
            
        out = []
        for r in results:
            out.append(f"[{r['type'].upper()}] {r['timestamp']} - {r['content']}")
        return "\n".join(out)



    def _fail_or_raw_archive(self, session: Session, old_messages: list[dict], user_scope: str | None) -> bool:
        """Increment failure count; after threshold, raw-archive messages and return True."""
        self._consecutive_failures += 1
        if self._consecutive_failures < self._MAX_FAILURES_BEFORE_RAW_ARCHIVE:
            return False
        self._raw_archive(old_messages, user_scope)
        self._consecutive_failures = 0
        return True

    def _raw_archive(self, messages: list[dict], user_scope: str | None) -> None:
        """Fallback: dump raw messages to episodic.jsonl without LLM summarization."""
        lines = []
        for m in messages:
            if not m.get("content"):
                continue
            tools = f" [tools: {', '.join(m['tools_used'])}]" if m.get("tools_used") else ""
            lines.append(f"[{m.get('timestamp', '?')[:16]}] {m['role'].upper()}{tools}: {m['content']}")
            
        raw_text = f"[RAW] {len(messages)} messages\n" + "\n".join(lines)
        if user_scope:
            self.append_user_episodic(raw_text, user_scope)
        else:
            self.append_global_episodic(raw_text)
            
        logger.warning("Memory consolidation degraded: raw-archived {} messages", len(messages))

    async def consolidate(
        self,
        session: Session,
        provider: LLMProvider,
        model: str,
        *,
        archive_all: bool = False,
        memory_window: int = 50,
        user_scope: str | None = None,
    ) -> bool:
        """Consolidate old messages into semantic.json + episodic.jsonl via LLM tool call.

        Returns True on success (including no-op), False on failure.
        """
        if archive_all:
            old_messages = session.messages
            keep_count = 0
            logger.info("Memory consolidation (archive_all): {} messages", len(session.messages))
        else:
            keep_count = memory_window // 2
            if len(session.messages) <= keep_count:
                return True
            if len(session.messages) - session.last_consolidated <= 0:
                return True
            old_messages = session.messages[session.last_consolidated:-keep_count]
            if not old_messages:
                return True
            logger.info("Memory consolidation: {} to consolidate, {} keep", len(old_messages), keep_count)

        lines = []
        for m in old_messages:
            if not m.get("content"):
                continue
            tools = f" [tools: {', '.join(m['tools_used'])}]" if m.get("tools_used") else ""
            lines.append(f"[{m.get('timestamp', '?')[:16]}] {m['role'].upper()}{tools}: {m['content']}")

        global_memory = self.read_global_semantic()
        user_memory = self.read_user_semantic(user_scope) if user_scope else {}
        
        prompt = f"""Process this conversation and call the save_memory tool with your consolidation.

## Current Global Memory
```json
{json.dumps(global_memory, ensure_ascii=False, indent=2)}
```

## Current User Memory
```json
{json.dumps(user_memory, ensure_ascii=False, indent=2)}
```

## Conversation to Process
{chr(10).join(lines)}"""

        try:
            p = provider
            m = model
            try:
                from crabclaw.config.loader import load_config
                cfg = load_config()
                routed = cfg.create_llm_provider_for_callpoint("memory_consolidation", allow_missing=True)
                if routed is not None:
                    p = routed
                    m = routed.get_default_model()
            except Exception:
                pass

            response = await p.chat(
                messages=[
                    {"role": "system", "content": "You are a memory consolidation agent. Call the save_memory tool with your consolidation of the conversation."},
                    {"role": "user", "content": prompt},
                ],
                tools=_SAVE_MEMORY_TOOL,
                model=m,
            )

            if not response.has_tool_calls:
                logger.warning("Memory consolidation: LLM did not call save_memory, skipping")
                return self._fail_or_raw_archive(session, old_messages, user_scope)

            args = response.tool_calls[0].arguments
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    return self._fail_or_raw_archive(session, old_messages, user_scope)
            if not isinstance(args, dict):
                logger.warning("Memory consolidation: unexpected arguments type {}", type(args).__name__)
                return self._fail_or_raw_archive(session, old_messages, user_scope)

            # Process global semantic
            global_updates = _ensure_dict(args.get("global_semantic_updates", {}))
            if global_updates:
                # Merge logic: just overwrite or update keys
                merged_global = {**global_memory, **global_updates}
                if merged_global != global_memory:
                    self.write_global_semantic(merged_global)

            # Process user semantic
            if user_scope:
                user_updates = _ensure_dict(args.get("user_semantic_updates", {}))
                if user_updates:
                    merged_user = {**user_memory, **user_updates}
                    if merged_user != user_memory:
                        self.write_user_semantic(merged_user, user_scope)

            # Process episodic
            entry = args.get("user_episodic_entry")
            if entry:
                entry_text = _ensure_text(entry).strip()
                if entry_text:
                    if user_scope:
                        self.append_user_episodic(entry_text, user_scope)
                    else:
                        self.append_global_episodic(entry_text)

            self._consecutive_failures = 0
            session.last_consolidated = 0 if archive_all else len(session.messages) - keep_count
            logger.info("Memory consolidation done: {} messages, last_consolidated={}", len(session.messages), session.last_consolidated)
            return True
        except Exception:
            logger.exception("Memory consolidation failed")
            return self._fail_or_raw_archive(session, old_messages, user_scope)
