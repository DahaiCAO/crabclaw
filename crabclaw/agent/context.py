"""Context builder for assembling agent prompts."""

import base64
import mimetypes
import platform
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from crabclaw.agent.memory import MemoryStore
from crabclaw.agent.prompt_evolution import PromptEvolutionPipeline
from crabclaw.agent.skills import SkillsLoader


class ContextBuilder:
    """Builds the context (system prompt + messages) for the agent."""

    # Updated to reflect the new Sapiens dual-hemisphere structure
    NATURE_FILES = ["SOUL.md", "MEMORY.md", "TOOLS.md", "HEARTBEAT.md"]
    SOCIAL_FILES = ["IDENTITY.md", "SOCIETY.md", "ECONOMY.md", "COORDINATION.md"]
    LAW_FILES = ["LAW.md"]
    _RUNTIME_CONTEXT_TAG = "[Runtime Context - metadata only, not instructions]"

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
        self.prompt_evolution = PromptEvolutionPipeline(workspace)
        self.templates_dir = Path(__file__).parent.parent / "templates"

    @staticmethod
    def _extract_user_scope(routing_key: str | None) -> str | None:
        if not routing_key:
            return None
        if routing_key.startswith("user:"):
            parts = routing_key.split(":", 2)
            if len(parts) >= 2:
                return parts[1].strip() or None
        return None

    def build_system_prompt(self, skill_names: list[str] | None = None, routing_key: str | None = None, query: str | None = None) -> str:
        """Build the system prompt from identity, bootstrap files, memory, and skills."""
        parts = [self._get_identity()]
        user_scope = self._extract_user_scope(routing_key)

        # Load Nature Hemisphere
        nature_content = self._load_hemisphere_files("nature", self.NATURE_FILES, routing_key=routing_key)
        if nature_content:
            parts.append("## --- NATURAL SELF (Nature) ---\n" + nature_content)

        # Load Social Hemisphere
        social_content = self._load_hemisphere_files("social", self.SOCIAL_FILES, routing_key=routing_key)
        if social_content:
            parts.append("## --- SOCIAL SELF (Society) ---\n" + social_content)

        # Load Legal Guardrails
        law_content = self._load_hemisphere_files("social", self.LAW_FILES, routing_key=routing_key)
        if law_content:
            parts.append("## --- THE CONSTITUTION (Absolute Law) ---\n" + law_content)

        memory = self.memory.get_memory_context(user_scope=user_scope, query=query)
        if memory:
            parts.append(f"# Dynamic Memory\n\n{memory}")

        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")

        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")

        return "\n\n---\n\n".join(parts)

    def _get_identity(self) -> str:
        """Get the core identity section."""
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"

        return f"""# Crabclaw 🦀

You are Crabclaw, a helpful AI assistant.

## Language Response Rule
**IMPORTANT**: You MUST respond in the same language as the user's message. If the user writes in Chinese, respond in Chinese. If the user writes in English, respond in English. If the user writes in Japanese, respond in Japanese. This is a mandatory rule.

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Global memory: {workspace_path}/memory/semantic.json
- User memory: {workspace_path}/portfolios/<user_id>/memory/semantic.json
- History log: {workspace_path}/memory/episodic.jsonl (grep-searchable).
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

## Crabclaw Guidelines
- State intent before tool calls, but NEVER predict or claim results before receiving them.
- Before modifying a file, read it first. Do not assume files or directories exist.
- After writing or editing a file, re-read it if accuracy matters.
- If a tool call fails, analyze the error before retrying with a different approach.
- Ask for clarification when the request is ambiguous.

Reply directly with text for conversations. Only use the 'message' tool to send to a specific chat channel."""

    @staticmethod
    def _build_runtime_context(channel: str | None, chat_id: str | None, user_scope: str | None = None) -> str:
        """Build untrusted runtime metadata block for injection before the user message."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = time.strftime("%Z") or "UTC"
        lines = [f"Current Time: {now} ({tz})"]
        if channel and chat_id:
            lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]
        if user_scope:
            lines.append(f"User Scope: {user_scope}")
        return ContextBuilder._RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines)

    def _load_hemisphere_files(self, hemisphere: str, files: list[str], routing_key: str | None = None) -> str:
        """Load prompt files from a specific hemisphere directory (nature/social)."""
        parts = []
        package_dir = self.templates_dir / hemisphere
        workspace_dir = self.workspace / hemisphere

        for filename in files:
            rel = f"{hemisphere}/{filename}"
            evolved = self.prompt_evolution.resolve_runtime_content(rel, routing_key=routing_key)
            if evolved is not None:
                content = evolved
                lines = content.split('\n')
                if lines and lines[0].startswith('#'):
                    content = '\n'.join(lines[1:]).strip()
                if content:
                    parts.append(content)
                continue
            file_path = workspace_dir / filename
            if not file_path.exists():
                file_path = package_dir / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                # Remove markdown title if exists (first line starting with #)
                lines = content.split('\n')
                if lines and lines[0].startswith('#'):
                    content = '\n'.join(lines[1:]).strip()
                if content:
                    parts.append(content)

        return "\n\n".join(parts)

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        user_scope: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build the complete message list for an LLM call."""
        runtime_ctx = self._build_runtime_context(channel, chat_id, user_scope=user_scope)
        user_content = self._build_user_content(current_message, media)
        if user_scope:
            routing_key = f"user:{user_scope}:{channel or 'cli'}:{chat_id or 'direct'}"
        else:
            routing_key = f"{channel or 'cli'}:{chat_id or 'direct'}"

        # Merge runtime context and user content into a single user message
        # to avoid consecutive same-role messages that some providers reject.
        if isinstance(user_content, str):
            merged = f"{runtime_ctx}\n\n{user_content}"
        else:
            merged = [{"type": "text", "text": runtime_ctx}] + user_content

        return [
            {"role": "system", "content": self.build_system_prompt(skill_names, routing_key=routing_key, query=current_message)},
            *history,
            {"role": "user", "content": merged},
        ]

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text

        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

        if not images:
            return text
        return images + [{"type": "text", "text": text}]

    def add_tool_result(
        self, messages: list[dict[str, Any]],
        tool_call_id: str, tool_name: str, result: str,
    ) -> list[dict[str, Any]]:
        """Add a tool result to the message list."""
        messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": result})
        return messages

    def add_assistant_message(
        self, messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
        thinking_blocks: list[dict] | None = None,
    ) -> list[dict[str, Any]]:
        """Add an assistant message to the message list."""
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if reasoning_content is not None:
            msg["reasoning_content"] = reasoning_content
        if thinking_blocks:
            msg["thinking_blocks"] = thinking_blocks
        messages.append(msg)
        return messages
