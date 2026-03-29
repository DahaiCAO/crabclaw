"""Configuration schema using Pydantic."""

from pathlib import Path
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """Base model that accepts both camelCase and snake_case keys."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class WhatsAppConfig(Base):
    """WhatsApp channel configuration."""

    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    bridge_token: str = ""  # Shared token for bridge auth (optional, recommended)
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class TelegramConfig(Base):
    """Telegram channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames
    proxy: str | None = None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"
    reply_to_message: bool = False  # If true, bot replies quote the original message


class FeishuConfig(Base):
    """Feishu/Lark channel configuration using WebSocket long connection."""

    enabled: bool = False
    app_id: str = ""  # App ID from Feishu Open Platform
    app_secret: str = ""  # App Secret from Feishu Open Platform
    encrypt_key: str = ""  # Encrypt Key for event subscription (optional)
    verification_token: str = ""  # Verification Token for event subscription (optional)
    allow_from: list[str] = Field(default_factory=list)  # Allowed user open_ids
    react_emoji: str = "THUMBSUP"  # Emoji type for message reactions (e.g. THUMBSUP, OK, DONE, SMILE)
    group_policy: Literal["open", "mention"] = "mention"  # Group chat response policy
    reply_to_message: bool = False  # If True, bot replies quote the user's original message


class DingTalkConfig(Base):
    """DingTalk channel configuration using Stream mode."""

    enabled: bool = False
    client_id: str = ""  # AppKey
    client_secret: str = ""  # AppSecret
    allow_from: list[str] = Field(default_factory=list)  # Allowed staff_ids


class DiscordConfig(Base):
    """Discord channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from Discord Developer Portal
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377  # GUILDS + GUILD_MESSAGES + DIRECT_MESSAGES + MESSAGE_CONTENT


class MatrixConfig(Base):
    """Matrix (Element) channel configuration."""

    enabled: bool = False
    homeserver: str = "https://matrix.org"
    access_token: str = ""
    user_id: str = ""  # @bot:matrix.org
    device_id: str = ""
    e2ee_enabled: bool = True # Enable Matrix E2EE support (encryption + encrypted room handling).
    sync_stop_grace_seconds: int = 2 # Max seconds to wait for sync_forever to stop gracefully before cancellation fallback.
    max_media_bytes: int = 20 * 1024 * 1024 # Max attachment size accepted for Matrix media handling (inbound + outbound).
    allow_from: list[str] = Field(default_factory=list)
    group_policy: Literal["open", "mention", "allowlist"] = "open"
    group_allow_from: list[str] = Field(default_factory=list)
    allow_room_mentions: bool = False


class EmailConfig(Base):
    """Email channel configuration (IMAP inbound + SMTP outbound)."""

    enabled: bool = False
    consent_granted: bool = False  # Explicit owner permission to access mailbox data

    # IMAP (receive)
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True

    # SMTP (send)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    from_address: str = ""

    # Behavior
    auto_reply_enabled: bool = True  # If false, inbound email is read but no automatic reply is sent
    poll_interval_seconds: int = 30
    mark_seen: bool = True
    max_body_chars: int = 12000
    subject_prefix: str = "Re: "
    allow_from: list[str] = Field(default_factory=list)  # Allowed sender email addresses


class MochatMentionConfig(Base):
    """Mochat mention behavior configuration."""

    require_in_groups: bool = False


class MochatGroupRule(Base):
    """Mochat per-group mention requirement."""

    require_mention: bool = False


class MochatConfig(Base):
    """Mochat channel configuration."""

    enabled: bool = False
    base_url: str = "https://mochat.io"
    socket_url: str = ""
    socket_path: str = "/socket.io"
    socket_disable_msgpack: bool = False
    socket_reconnect_delay_ms: int = 1000
    socket_max_reconnect_delay_ms: int = 10000
    socket_connect_timeout_ms: int = 10000
    refresh_interval_ms: int = 30000
    watch_timeout_ms: int = 25000
    watch_limit: int = 100
    retry_delay_ms: int = 500
    max_retry_attempts: int = 0  # 0 means unlimited retries
    claw_token: str = ""
    agent_user_id: str = ""
    sessions: list[str] = Field(default_factory=list)
    panels: list[str] = Field(default_factory=list)
    allow_from: list[str] = Field(default_factory=list)
    mention: MochatMentionConfig = Field(default_factory=MochatMentionConfig)
    groups: dict[str, MochatGroupRule] = Field(default_factory=dict)
    reply_delay_mode: str = "non-mention"  # off | non-mention
    reply_delay_ms: int = 120000


class SlackDMConfig(Base):
    """Slack DM policy configuration."""

    enabled: bool = True
    policy: str = "open"  # "open" or "allowlist"
    allow_from: list[str] = Field(default_factory=list)  # Allowed Slack user IDs


class SlackConfig(Base):
    """Slack channel configuration."""

    enabled: bool = False
    mode: str = "socket"  # "socket" supported
    webhook_path: str = "/slack/events"
    bot_token: str = ""  # xoxb-...
    app_token: str = ""  # xapp-...
    user_token_read_only: bool = True
    reply_in_thread: bool = True
    react_emoji: str = "eyes"
    allow_from: list[str] = Field(default_factory=list)  # Allowed Slack user IDs (sender-level)
    group_policy: str = "mention"  # "mention", "open", "allowlist"
    group_allow_from: list[str] = Field(default_factory=list)  # Allowed channel IDs if allowlist
    dm: SlackDMConfig = Field(default_factory=SlackDMConfig)


class QQConfig(Base):
    """QQ channel configuration using botpy SDK."""

    enabled: bool = False
    app_id: str = ""  # Bot ID (AppID) from q.qq.com
    secret: str = ""  # Bot Secret (AppSecret) from q.qq.com
    allow_from: list[str] = Field(default_factory=list)  # Allowed user openids (empty = public access)

class ChannelsConfig(Base):
    """Configuration for chat channels."""

    send_progress: bool = True    # stream agent's text progress to the channel
    send_tool_hints: bool = False  # stream tool-call hints (e.g. read_file("-))
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    mochat: MochatConfig = Field(default_factory=MochatConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    qq: QQConfig = Field(default_factory=QQConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)


class MessagingConfig(Base):
    """Message streaming behavior for outbound responses."""

    send_progress: bool = True    # stream agent's text progress to the channel
    send_tool_hints: bool = False  # stream tool-call hints (e.g. read_file("-))


class AgentDefaults(Base):
    """Default agent configuration."""

    workspace: str = "~/.crabclaw/workspace"
    model: str = ""
    provider: str = "auto"  # Provider name (e.g. "anthropic", "openrouter") or "auto" for auto-detection
    max_tokens: int = 8192
    temperature: float = 0.1
    max_tool_iterations: int = 40
    memory_window: int = 100
    reasoning_effort: str | None = None  # low / medium / high -enables LLM thinking mode


class AgentsConfig(Base):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(Base):
    """LLM provider configuration."""

    api_key: str = ""
    api_base: str | None = None
    model: str = ""
    extra_headers: dict[str, str] | None = None  # Custom headers (e.g. APP-Code for AiHubMix)


class ProvidersConfig(Base):
    """Configuration for LLM providers."""

    custom: ProviderConfig = Field(default_factory=ProviderConfig)  # Any OpenAI-compatible endpoint
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)  # Alibaba Cloud Tongyi Qianwen
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    siliconflow: ProviderConfig = Field(default_factory=ProviderConfig)  # SiliconFlow API gateway
    volcengine: ProviderConfig = Field(default_factory=ProviderConfig)  # VolcEngine API gateway
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)  # AiHubMix API gateway
    openai_codex: ProviderConfig = Field(default_factory=ProviderConfig)  # OpenAI Codex (OAuth)
    github_copilot: ProviderConfig = Field(default_factory=ProviderConfig)  # Github Copilot (OAuth)
    user_providers: dict[str, ProviderConfig] = Field(default_factory=dict)


class GatewayConfig(Base):
    """Gateway/server configuration."""

    host: str = "0.0.0.0"
    port: int = 18790


class DashboardConfig(Base):
    """Dashboard configuration (static UI + WS event stream)."""

    enabled: bool = True
    http_port: int = 18791
    ws_port: int = 18792
    state_push_interval_s: float = 1.0
    audit_tail_enabled: bool = True
    audit_tail_from_end: bool = False


class SchedulerConfig(Base):
    """Configuration for the Behavior Scheduler."""
    save_interval: int = 600 # seconds


class WebSearchConfig(Base):
    """Web search tool configuration."""

    api_key: str = ""  # Brave Search API key
    max_results: int = 5


class WebToolsConfig(Base):
    """Web tools configuration."""

    proxy: str | None = None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(Base):
    """Shell exec tool configuration."""

    timeout: int = 60
    path_append: str = ""


class MCPServerConfig(Base):
    """MCP server connection configuration (stdio or HTTP)."""

    command: str = ""  # Stdio: command to run (e.g. "npx")
    args: list[str] = Field(default_factory=list)  # Stdio: command arguments
    env: dict[str, str] = Field(default_factory=dict)  # Stdio: extra env vars
    url: str = ""  # HTTP: streamable HTTP endpoint URL
    headers: dict[str, str] = Field(default_factory=dict)  # HTTP: Custom HTTP Headers
    tool_timeout: int = 30  # Seconds before a tool call is cancelled


class ToolsConfig(Base):
    """Tools configuration."""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = False  # If true, restrict all tool access to workspace directory
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


def generate_agent_id() -> str:
    """Generate a globally unique Agent ID: AGT + YYYYMMDDHHMMSSsss + ISO-3166-1 (3 letters) + 4 random digits."""
    import random
    from datetime import datetime
    now = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    rand = random.randint(1000, 9999)
    return f"AGT{now}CHN{rand}"


class Config(BaseSettings):
    """Root configuration for crabclaw."""

    agent_id: str = Field(default_factory=generate_agent_id)
    agent_name: str | None = None  # User-defined display name
    nickname: str | None = None  # Agent nickname (网名)
    
    # New profile fields
    status: str = "offline"  # online/offline
    work_status: str = "idle"  # idle, busy, super_busy, waiting, meeting, communicating
    country: str = "Unknown"
    age: int = 22
    gender: str = "male"
    dob: str = Field(default_factory=lambda: __import__('datetime').datetime.now().strftime("%Y-%m-%d"))  # YYYY-MM-DD
    height: int = 180  # cm
    weight: int = 70  # kg
    hobbies: list[str] = Field(default_factory=list)
    portrait: str | None = None  # Will be set based on language
    
    # Internal State Persistence
    psychology: dict[str, Any] = Field(default_factory=dict)
    
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    language: str = "en"  # Language code (e.g., "en", "zh")
    clawsociety_enabled: bool = False  # Enable/disable connection to ClawSociety (Social vs Solo mode)
    clawsocial_url: str = "http://127.0.0.1:8000"  # URL for ClawSociety/ClawSocialGraph (legacy)
    clawsocial_connections: dict[str, dict[str, Any]] = Field(default_factory=dict)  # Multiple ClawSocial connections: {conn_id: {"enabled": bool, "url": str, "status": "connected"|"disconnected"|"unknown", "description": str}}
    llm_routes: dict[str, str] = Field(default_factory=dict)
    provider_test_status: dict[str, bool] = Field(default_factory=dict)  # Track provider test results
    channel_mode: str = "multi"  # Channel communication mode: "multi" (multi-channel subscription) or "single" (single-channel subscription)
    workspace_path: str | None = None  # Workspace path (for multi-instance support)

    @property
    def expanded_workspace_path(self) -> Path:
        """Get expanded workspace path."""
        if self.workspace_path:
            return Path(self.workspace_path).expanduser()
        return Path(self.agents.defaults.workspace).expanduser()

    def _match_provider(self, model: str | None = None) -> tuple["ProviderConfig | None", str | None]:
        """Match provider config and its registry name. Returns (config, spec_name)."""
        from crabclaw.providers.registry import PROVIDERS

        forced = self.agents.defaults.provider
        if forced != "auto":
            p = getattr(self.providers, forced, None)
            return (p, forced) if p else (None, None)

        model_lower = (model or "").lower()
        model_normalized = model_lower.replace("-", "_")
        model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
        normalized_prefix = model_prefix.replace("-", "_")

        def _kw_matches(kw: str) -> bool:
            kw = kw.lower()
            return kw in model_lower or kw.replace("-", "_") in model_normalized

        # Explicit provider prefix wins -prevents `github-copilot/...codex` matching openai_codex.
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and model_prefix and normalized_prefix == spec.name:
                if spec.is_oauth or p.api_key:
                    return p, spec.name

        # Match by keyword (order follows PROVIDERS registry)
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(_kw_matches(kw) for kw in spec.keywords):
                if spec.is_oauth or p.api_key:
                    return p, spec.name

        # Fallback: gateways first, then others (follows registry order)
        # OAuth providers are NOT valid fallbacks -they require explicit model selection
        for spec in PROVIDERS:
            if spec.is_oauth:
                continue
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return p, spec.name
        return None, None

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config (api_key, api_base, extra_headers). Falls back to first available."""
        p, _ = self._match_provider(model)
        return p

    def get_provider_name(self, model: str | None = None) -> str | None:
        """Get the registry name of the matched provider (e.g. "deepseek", "openrouter")."""
        _, name = self._match_provider(model)
        return name

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model. Falls back to first available key."""
        p = self.get_provider(model)
        return p.api_key if p else None

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL for the given model. Applies default URLs for known gateways."""
        from crabclaw.providers.registry import find_by_name

        p, name = self._match_provider(model)
        if p and p.api_base:
            return p.api_base
        # Only gateways get a default api_base here. Standard providers
        # (like Moonshot) set their base URL via env vars in _setup_env
        # to avoid polluting the global litellm.api_base.
        if name:
            spec = find_by_name(name)
            if spec and spec.is_gateway and spec.default_api_base:
                return spec.default_api_base
        return None

    def create_llm_provider_for_callpoint(self, callpoint: str, allow_missing: bool = True):
        import time

        from crabclaw.providers.custom_provider import CustomProvider
        from crabclaw.providers.litellm_provider import LiteLLMProvider
        from crabclaw.providers.openai_codex_provider import OpenAICodexProvider
        from crabclaw.providers.registry import find_by_name
        from crabclaw.providers.base import LLMProvider
        from crabclaw.utils.audit_logger import AuditEventType, get_audit_logger_for_dir
        workspace_path = self.expanded_workspace_path
        user_prefix = "user:"

        class _AuditedProvider(LLMProvider):
            def __init__(self, inner: LLMProvider, *, provider_name: str, default_model: str | None):
                super().__init__(api_key=None, api_base=None)
                self._inner = inner
                self._provider_name = provider_name
                self._default_model = default_model or inner.get_default_model()

            async def chat(
                self,
                messages: list[dict[str, Any]],
                tools: list[dict[str, Any]] | None = None,
                model: str | None = None,
                max_tokens: int = 4096,
                temperature: float = 0.7,
                reasoning_effort: str | None = None,
            ):
                start = time.time()
                used_model = (model or self._default_model or "").strip()
                try:
                    resp = await self._inner.chat(
                        messages=messages,
                        tools=tools,
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        reasoning_effort=reasoning_effort,
                    )
                    elapsed_ms = int((time.time() - start) * 1000)

                    usage_raw = getattr(resp, "usage", None) or {}
                    usage = {}
                    try:
                        usage = {
                            "prompt": int(usage_raw.get("prompt_tokens") or 0),
                            "completion": int(usage_raw.get("completion_tokens") or 0),
                            "total": int(usage_raw.get("total_tokens") or 0),
                        }
                    except Exception:
                        usage = {}

                    audit_dir = workspace_path / "audit"
                    audit_logger = get_audit_logger_for_dir(audit_dir)
                    result = "error" if getattr(resp, "finish_reason", None) == "error" else "ok"
                    audit_logger.log_security_event(
                        event_type=AuditEventType.LLM_CALL,
                        action="chat",
                        resource=used_model or None,
                        result=result,
                        details={
                            "callpoint": callpoint,
                            "provider": self._provider_name,
                            "model": used_model,
                            "latency_ms": elapsed_ms,
                            "usage": usage,
                            "finish_reason": getattr(resp, "finish_reason", None),
                        },
                    )
                    return resp
                except Exception as e:
                    elapsed_ms = int((time.time() - start) * 1000)
                    audit_dir = workspace_path / "audit"
                    audit_logger = get_audit_logger_for_dir(audit_dir)
                    audit_logger.log_security_event(
                        event_type=AuditEventType.LLM_CALL,
                        action="chat",
                        resource=used_model or None,
                        result="error",
                        details={
                            "callpoint": callpoint,
                            "provider": self._provider_name,
                            "model": used_model,
                            "latency_ms": elapsed_ms,
                            "error": str(e),
                        },
                    )
                    raise

            def get_default_model(self) -> str:
                return self._default_model

        def _wrap(p: LLMProvider, *, provider_name: str, default_model: str | None = None):
            return _AuditedProvider(p, provider_name=provider_name, default_model=default_model)

        routes = getattr(self, "llm_routes", {}) or {}
        forced = routes.get(callpoint)

        if forced and isinstance(forced, str) and forced.startswith(user_prefix):
            user_name = forced[len(user_prefix):].strip()
            p_forced = (getattr(self.providers, "user_providers", {}) or {}).get(user_name)
            if not p_forced:
                return None
            model = (getattr(p_forced, "model", "") or "").strip()
            if not model and allow_missing:
                return None
            return _wrap(CustomProvider(
                api_key=getattr(p_forced, "api_key", None) or "no-key",
                api_base=getattr(p_forced, "api_base", None) or "http://localhost:8000/v1",
                default_model=model or "default",
            ), provider_name=forced, default_model=model or None)

        if forced and forced != "auto":
            p_forced = getattr(self.providers, forced, None)
            if p_forced is None:
                return None
            spec = find_by_name(forced)
            model = (getattr(p_forced, "model", "") or "").strip() or ""
            api_base = getattr(p_forced, "api_base", None) or None
            if not api_base and spec and spec.default_api_base:
                api_base = spec.default_api_base

            if forced == "openai_codex" or (model and model.startswith("openai-codex/")):
                return _wrap(OpenAICodexProvider(default_model=model), provider_name=forced, default_model=model)

            if forced == "custom":
                return _wrap(CustomProvider(
                    api_key=getattr(p_forced, "api_key", None) or "no-key",
                    api_base=api_base or "http://localhost:8000/v1",
                    default_model=model,
                ), provider_name="custom", default_model=model)

            if not (model and model.startswith("bedrock/")) and not (getattr(p_forced, "api_key", "") or "") and not (spec and spec.is_oauth):
                return None if allow_missing else None

            return _wrap(LiteLLMProvider(
                api_key=getattr(p_forced, "api_key", None) or None,
                api_base=api_base,
                default_model=model,
                extra_headers=getattr(p_forced, "extra_headers", None) or None,
                provider_name=forced,
            ), provider_name=forced, default_model=model)

        model = ""  # Don't use self.agents.defaults.model, require explicit model or provider
        if not model and allow_missing:
            return None
        provider_name = self.get_provider_name(model) or "custom"
        p = self.get_provider(model)

        if provider_name == "openai_codex" or (model and model.startswith("openai-codex/")):
            return _wrap(OpenAICodexProvider(default_model=model), provider_name=provider_name, default_model=model)

        if provider_name == "custom":
            return _wrap(CustomProvider(
                api_key=p.api_key if p else "no-key",
                api_base=self.get_api_base(model) or "http://localhost:8000/v1",
                default_model=model,
            ), provider_name="custom", default_model=model)

        spec = find_by_name(provider_name)
        if not (model and model.startswith("bedrock/")) and not (p and p.api_key) and not (spec and spec.is_oauth):
            return None if allow_missing else None

        return _wrap(LiteLLMProvider(
            api_key=p.api_key if p else None,
            api_base=self.get_api_base(model),
            default_model=model,
            extra_headers=p.extra_headers if p else None,
            provider_name=provider_name,
        ), provider_name=provider_name, default_model=model)

    model_config = ConfigDict(
        env_prefix="CRABCLAW_", 
        env_nested_delimiter="__",
        alias_generator=to_camel, 
        populate_by_name=True
    )
