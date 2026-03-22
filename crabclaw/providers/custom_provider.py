"""Direct OpenAI-compatible provider -bypasses LiteLLM."""

from __future__ import annotations

import re
import hashlib
from typing import Any

import json_repair
from openai import AsyncOpenAI

from crabclaw.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class CustomProvider(LLMProvider):

    def __init__(self, api_key: str = "no-key", api_base: str = "http://localhost:8000/v1", default_model: str = "default"):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self._client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
                   model: str | None = None, max_tokens: int = 4096, temperature: float = 0.7,
                   reasoning_effort: str | None = None) -> LLMResponse:
        
        # Sanitize messages to ensure tool_calls arguments are strings (ModelArts requirement)
        sanitized_messages = self._sanitize_empty_content(messages)
        self._ensure_tool_call_arguments_are_strings(sanitized_messages)

        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": sanitized_messages,
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
        }
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        try:
            return self._parse(await self._client.chat.completions.create(**kwargs))
        except Exception as e:
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    def _ensure_tool_call_arguments_are_strings(self, messages: list[dict[str, Any]]) -> None:
        """Ensure tool_calls arguments are JSON strings, not dicts."""
        import json
        for msg in messages:
            if msg.get("role") == "assistant" and "tool_calls" in msg:
                tool_calls = msg["tool_calls"]
                if not isinstance(tool_calls, list):
                    continue
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    fn = tc.get("function")
                    if not isinstance(fn, dict):
                        continue
                    
                    args = fn.get("arguments")
                    # If arguments is a dict, dump it to string
                    if isinstance(args, dict):
                        fn["arguments"] = json.dumps(args, ensure_ascii=False)
                    # If arguments is None or not string/dict, ensure it's at least an empty JSON object
                    elif args is None:
                        fn["arguments"] = "{}"
    
    def _parse(self, response: Any) -> LLMResponse:
        choice = response.choices[0]
        msg = choice.message
        tool_calls = [
            ToolCallRequest(id=tc.id, name=tc.function.name,
                            arguments=(json_repair.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments) or {})
            for tc in (msg.tool_calls or [])
        ]

        content = msg.content
        if not tool_calls and content and "<|tool_calls_section_begin|>" in content:
            content, parsed_calls = self._parse_text_tool_calls(content)
            tool_calls.extend(parsed_calls)

        u = response.usage
        return LLMResponse(
            content=content, tool_calls=tool_calls, finish_reason=choice.finish_reason or "stop",
            usage={"prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens, "total_tokens": u.total_tokens} if u else {},
            reasoning_content=getattr(msg, "reasoning_content", None) or None,
        )

    def _parse_text_tool_calls(self, content: str) -> tuple[str | None, list[ToolCallRequest]]:
        """Parse text-based tool calls from content (e.g. ModelArts/Kimi format)."""
        tool_calls = []
        clean_content = content

        # Regex to find the tool calls section
        section_pattern = re.compile(r"<\|tool_calls_section_begin\|>(.*?)<\|tool_calls_section_end\|>", re.DOTALL)
        match = section_pattern.search(content)

        if match:
            raw_section = match.group(1)
            # Remove the entire section from content
            clean_content = content.replace(match.group(0), "").strip() or None

            # Split by <|tool_call_begin|>
            parts = raw_section.split("<|tool_call_begin|>")

            for part in parts:
                part = part.strip()
                if not part or "<|tool_call_argument_begin|>" not in part:
                    continue

                try:
                    name_id_part, args_part = part.split("<|tool_call_argument_begin|>", 1)
                    name_id = name_id_part.strip()
                    args_str = args_part.strip()

                    call_id = None
                    name = name_id

                    # Check for ID in name (name:id)
                    if ":" in name_id:
                        possible_name, possible_id = name_id.rsplit(":", 1)
                        if possible_id and all(c.isalnum() or c in "-_" for c in possible_id):
                            name = possible_name
                            call_id = possible_id

                    if not call_id:
                        # Generate deterministic ID based on content hash
                        call_id = "call_" + hashlib.md5(part.encode()).hexdigest()[:8]

                    # Clean up name (remove 'functions.' prefix)
                    if name.startswith("functions."):
                        name = name[10:]

                    args = json_repair.loads(args_str) or {}

                    tool_calls.append(ToolCallRequest(
                        id=call_id,
                        name=name,
                        arguments=args
                    ))
                except Exception:
                    pass  # Skip malformed calls

        return clean_content, tool_calls

    def get_default_model(self) -> str:
        return self.default_model

