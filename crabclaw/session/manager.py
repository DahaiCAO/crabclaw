"""Session management for conversation history."""

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from crabclaw.utils.helpers import ensure_dir, safe_filename


@dataclass
class Session:
    """
    A conversation session.

    Stores messages in JSONL format for easy reading and persistence.

    Important: Messages are append-only for LLM cache efficiency.
    The consolidation process writes summaries to MEMORY.md/HISTORY.md
    but does NOT modify the messages list or get_history() output.
    """

    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0  # Number of messages already consolidated to files

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(self, max_messages: int = 500) -> list[dict[str, Any]]:
        """Return unconsolidated messages for LLM input, aligned to a user turn."""
        unconsolidated = self.messages[self.last_consolidated:]
        sliced = unconsolidated[-max_messages:]

        # Drop leading non-user messages to avoid orphaned tool_result blocks
        for i, m in enumerate(sliced):
            if m.get("role") == "user":
                sliced = sliced[i:]
                break

        out: list[dict[str, Any]] = []
        for m in sliced:
            entry: dict[str, Any] = {"role": m["role"], "content": m.get("content", "")}
            for k in ("tool_calls", "tool_call_id", "name"):
                if k in m:
                    entry[k] = m[k]
            out.append(entry)
        return out

    def clear(self) -> None:
        """Clear all messages and reset session to initial state."""
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions.

    Sessions are stored as JSONL files in the sessions directory.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(self.workspace / "sessions")
        self.user_sessions_root = ensure_dir(self.workspace / "sessions_by_user")
        self.legacy_sessions_dir = Path.home() / ".crabclaw" / "sessions"
        self._cache: dict[str, Session] = {}

    @staticmethod
    def _normalize_user_scope(user_scope: str | None) -> str | None:
        if user_scope is None:
            return None
        value = str(user_scope).strip()
        return value or None

    def _get_user_sessions_dir(self, user_scope: str) -> Path:
        return ensure_dir(self.user_sessions_root / safe_filename(user_scope))

    def _cache_key(self, key: str, user_scope: str | None = None) -> str:
        normalized = self._normalize_user_scope(user_scope)
        if normalized is None:
            return key
        return f"{normalized}::{key}"

    def _get_session_path(self, key: str, user_scope: str | None = None) -> Path:
        """Get the file path for a session."""
        safe_key = safe_filename(key.replace(":", "_"))
        normalized = self._normalize_user_scope(user_scope)
        if normalized is None:
            return self.sessions_dir / f"{safe_key}.jsonl"
        return self._get_user_sessions_dir(normalized) / f"{safe_key}.jsonl"

    def _get_legacy_session_path(self, key: str) -> Path:
        """Legacy global session path (~/.crabclaw/sessions/)."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.legacy_sessions_dir / f"{safe_key}.jsonl"

    def get_or_create(self, key: str, user_scope: str | None = None) -> Session:
        """
        Get an existing session or create a new one.

        Args:
            key: Session key (usually channel:chat_id).

        Returns:
            The session.
        """
        cache_key = self._cache_key(key, user_scope)
        if cache_key in self._cache:
            return self._cache[cache_key]

        session = self._load(key, user_scope=user_scope)
        if session is None:
            session = Session(key=key)
            if user_scope:
                session.metadata["user_scope"] = user_scope

        self._cache[cache_key] = session
        return session

    def _load(self, key: str, user_scope: str | None = None) -> Session | None:
        """Load a session from disk."""
        path = self._get_session_path(key, user_scope=user_scope)
        if not path.exists():
            normalized_scope = self._normalize_user_scope(user_scope)
            if normalized_scope is None:
                legacy_path = self._get_legacy_session_path(key)
                if legacy_path.exists():
                    try:
                        shutil.move(str(legacy_path), str(path))
                        logger.info("Migrated session {} from legacy path", key)
                    except Exception:
                        logger.exception("Failed to migrate session {}", key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None
            last_consolidated = 0

            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                        last_consolidated = data.get("last_consolidated", 0)
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated
            )
        except Exception as e:
            logger.warning("Failed to load session {}: {}", key, e)
            return None

    def save(self, session: Session) -> None:
        """Save a session to disk."""
        user_scope = session.metadata.get("user_scope")
        path = self._get_session_path(session.key, user_scope=user_scope)

        with open(path, "w", encoding="utf-8") as f:
            metadata_line = {
                "_type": "metadata",
                "key": session.key,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
                "last_consolidated": session.last_consolidated
            }
            f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
            for msg in session.messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        self._cache[self._cache_key(session.key, user_scope)] = session

    def invalidate(self, key: str) -> None:
        """Remove a session from the in-memory cache."""
        self._cache.pop(key, None)

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions.

        Returns:
            List of session info dicts.
        """
        sessions = []

        candidates = list(self.sessions_dir.glob("*.jsonl"))
        for user_dir in self.user_sessions_root.glob("*"):
            if user_dir.is_dir():
                candidates.extend(user_dir.glob("*.jsonl"))

        for path in candidates:
            try:
                # Read just the metadata line
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            key = data.get("key") or path.stem.replace("_", ":", 1)
                            user_scope = ""
                            if path.parent != self.sessions_dir:
                                user_scope = path.parent.name
                            sessions.append({
                                "key": key,
                                "user_scope": user_scope,
                                "created_at": data.get("created_at"),
                                "updated_at": data.get("updated_at"),
                                "path": str(path)
                            })
            except Exception:
                continue

        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
