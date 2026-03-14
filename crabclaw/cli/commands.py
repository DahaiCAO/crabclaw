"""CLI commands for Crabclaw."""

import asyncio
import os
import select
import signal
import sys
from pathlib import Path

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from crabclaw import __logo__, __version__
from crabclaw.config.loader import get_config_path, load_config, set_config_path
from crabclaw.config.schema import Config
from crabclaw.i18n.translator import detect_system_language, set_language, translate
from crabclaw.utils.helpers import sync_workspace_templates

# Load config and set language (prefer system locale when config is default-en)
config = load_config()
_sys_lang = detect_system_language()
_cfg_lang = getattr(config, "language", "en")
_preferred_lang = _cfg_lang
if _cfg_lang not in ("en", "zh"):
    _preferred_lang = _sys_lang
elif _cfg_lang == "en" and _sys_lang == "zh":
    _preferred_lang = "zh"
set_language(_preferred_lang)

app = typer.Typer(
    name="crabclaw",
    help=translate("cli.app_help", logo=__logo__),
    no_args_is_help=True,
)

console = Console()
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}

# ---------------------------------------------------------------------------
# Config loading utilities
# ---------------------------------------------------------------------------

def _check_port_available(port: int) -> bool:
    """Check if a port is available on IPv4."""
    import socket
    # Check on localhost (127.0.0.1)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
    except OSError:
        return False
    
    # Check on all interfaces (0.0.0.0)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', port))
    except OSError:
        return False
    
    return True

def _suggest_available_ports(base_port: int, count: int = 2) -> list:
    """Suggest available ports near the base port."""
    import socket
    available_ports = []
    port = base_port + 1
    while len(available_ports) < count and port < 65536:
        if _check_port_available(port):
            available_ports.append(port)
        port += 1
    return available_ports

def _load_runtime_config(config_path: str | None = None, workspace: str | None = None) -> Config:
    """Load config and optionally override active workspace.
    
    This function supports multi-instance configuration by allowing
    specification of a custom config file path.
    
    Args:
        config_path: Optional path to config file. If provided, sets the
                     global config path for this instance.
        workspace: Optional workspace directory override.
        
    Returns:
        Loaded configuration object.
    """
    path = None
    if config_path:
        path = Path(config_path).expanduser().resolve()
        if not path.exists():
            console.print(f"[red]Error: Config file not found: {path}[/red]")
            raise typer.Exit(1)
        set_config_path(path)
        console.print(f"[dim]Using config: {path}[/dim]")
    
    loaded = load_config(path)
    if workspace:
        loaded.workspace_path = workspace
    return loaded

# ---------------------------------------------------------------------------
# CLI input: prompt_toolkit for editing, paste, history, and display
# ---------------------------------------------------------------------------

_PROMPT_SESSION: PromptSession | None = None
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _init_prompt_session() -> None:
    """Create the prompt_toolkit session with persistent file history."""
    global _PROMPT_SESSION, _SAVED_TERM_ATTRS

    # Save terminal state so we can restore it on exit
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".crabclaw" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,   # Enter submits (single line mode)
    )


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with consistent terminal styling."""
    content = response or ""
    if not content.strip():
        content = translate("cli.agent.empty_response")
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    console.print(f"[cyan]{__logo__}[/cyan]")
    console.print(body)
    console.print()


def _is_exit_command(command: str) -> bool:
    """Return True when input should end interactive chat."""
    return command.lower() in EXIT_COMMANDS


async def _read_interactive_input_async() -> str:
    """Read user input using prompt_toolkit (handles paste, history, display).

    prompt_toolkit natively handles:
    - Multiline paste (bracketed paste mode)
    - History navigation (up/down arrows)
    - Clean display (no ghost characters or artifacts)
    """
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='ansiblue'>You:</b> "),
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc



def version_callback(value: bool):
    if value:
        console.print(translate("cli.version", logo=__logo__, version=__version__))
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """crabclaw - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


# ============================================================================
# Onboard Command Group
# ============================================================================

onboard_app = typer.Typer(help="Initialize and manage crabclaw configuration")
app.add_typer(onboard_app, name="onboard")


def _initialize_crabclaw():
    """Initialize crabclaw configuration and workspace."""
    from crabclaw.config.loader import get_config_path, load_config, save_config
    from crabclaw.config.schema import Config
    from crabclaw.utils.helpers import get_workspace_path

    config_path = get_config_path()

    if config_path.exists():
        console.print(f"[yellow]{translate('cli.onboard.config_exists', path=config_path)}[/yellow]")
        console.print(translate("cli.onboard.overwrite_option"))
        console.print(translate("cli.onboard.refresh_option"))
        if typer.confirm(translate("cli.onboard.overwrite_confirm")):
            config = Config()
            save_config(config)
            console.print(f"[green]✓[/green] {translate('cli.onboard.config_reset', path=config_path)}")
        else:
            config = load_config()
            save_config(config)
            console.print(f"[green]✓[/green] {translate('cli.onboard.config_refreshed', path=config_path)}")
    else:
        save_config(Config())
        console.print(f"[green]✓[/green] {translate('cli.onboard.config_created', path=config_path)}")

    # Create workspace
    workspace = get_workspace_path()

    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] {translate('cli.onboard.workspace_created', path=workspace)}")

    sync_workspace_templates(workspace)

    console.print(f"\n{translate('cli.onboard.ready', logo=__logo__)}")
    console.print(f"\n{translate('cli.onboard.next_steps')}")
    console.print(f"  1. {translate('cli.onboard.add_api_key')}")
    console.print(f"     {translate('cli.onboard.get_api_key')}")
    console.print(f"  2. {translate('cli.onboard.chat_command')}")
    console.print(f"\n[dim]{translate('cli.onboard.chat_apps')}[/dim]")


@onboard_app.callback(invoke_without_command=True)
def onboard_callback():
    """Initialize and configure crabclaw (interactive wizard)."""
    # When no subcommand is provided, run the setup wizard
    setup()


@onboard_app.command()
def setup():
    """Initialize and configure crabclaw (interactive wizard)."""
    from crabclaw.config.loader import get_config_path, save_config
    from crabclaw.config.schema import Config
    from crabclaw.i18n.translator import get_supported_languages
    from crabclaw.utils.helpers import get_workspace_path

    config_path = get_config_path()

    # Load existing config or create new one in memory
    if config_path.exists():
        console.print(f"[yellow]{translate('cli.onboard.config_exists', path=config_path)}[/yellow]")
        if typer.confirm(translate("cli.onboard.reconfigure_confirm")):
            config = Config()
        else:
            console.print(translate("cli.config.exit_config"))
            return
    else:
        config = Config()

    # Step 1: Select Language
    total_steps = 10
    _print_step(1, total_steps, translate("cli.config.language_step"))
    languages = get_supported_languages()
    language_display = []
    for lang in languages:
        if lang == "en":
            language_display.append("English")
        elif lang == "zh":
            language_display.append("中文")

    selected_language = _ask_choice(translate("cli.config.select_language"), language_display, 0)
    language_key = languages[language_display.index(selected_language)]
    config.language = language_key

    # Update current session language
    set_language(language_key)

    _print_success(translate("cli.config.language_selected", language=selected_language))

    _print_header(translate("cli.onboard.title"))
    console.print(translate("cli.onboard.welcome"))
    _print_info(translate("cli.onboard.exit_hint"))

    # Step 2: Select LLM Provider
    _print_step(2, total_steps, translate("cli.config.step_1_title"))
    console.print("\n" + translate("cli.config.select_provider"))

    provider_names = list(PROVIDERS_INFO.keys())
    provider_display = []
    for p in provider_names:
        provider_name = translate(f"providers.{p}.name")
        provider_desc = translate(f"providers.{p}.description")
        provider_display.append(f"{provider_name} - {provider_desc}")

    selected_provider = _ask_choice(translate("cli.config.select_provider").strip(), provider_display, 0)
    provider_key = provider_names[provider_display.index(selected_provider)]
    provider_info = PROVIDERS_INFO[provider_key]

    provider_name = translate(f"providers.{provider_key}.name")
    _print_success(translate("cli.config.selected_provider", provider=provider_name))

    # Step 3: Select Model
    _print_step(3, total_steps, translate("cli.config.step_2_title", provider=provider_name))
    console.print("\n" + translate("cli.config.available_models", provider=provider_name) + "\n")

    models = provider_info['models']

    # If custom provider, let user enter custom model name
    if provider_key == "custom":
        console.print("\n" + translate("cli.config.custom_model_hint"))
        console.print(translate("cli.config.custom_model_default"))
        custom_model = _ask_text(translate("cli.config.enter_model_name"), default="gpt-3.5-turbo")
        selected_model = custom_model
    else:
        selected_model = _ask_choice(translate("cli.config.select_model"), models, 0)

    # If custom provider, may need to configure base_url
    base_url = provider_info['default_base_url']
    if provider_key == "custom":
        console.print("\n" + translate("cli.config.custom_api_hint"))
        custom_url = _ask_text(translate("cli.config.enter_base_url"),
                                default=base_url)
        base_url = custom_url

    _print_success(translate("cli.config.selected_model", model=selected_model))

    # Step 4: Configure API Key
    _print_step(4, total_steps, translate("cli.config.step_3_title"))

    if provider_info['api_key_url']:
        console.print("\n" + translate("cli.config.get_api_key"))
        console.print(translate("cli.config.api_key_url", url=provider_info['api_key_url']))

    api_key = _ask_password(translate("cli.config.enter_api_key"))
    _print_success(translate("cli.config.api_key_saved"))

    # Step 5: Configure Tools (optional)
    _print_step(5, total_steps, translate("cli.config.step_4_title"))

    enable_exec = typer.confirm("\n" + translate("cli.config.enable_exec"), default=False)

    if enable_exec:
        restrict_workspace = typer.confirm(translate("cli.config.restrict_workspace"), default=True)

        if provider_key == "openrouter":
            # Configure proxy (optional)
            proxy = _ask_text(translate("cli.config.enter_proxy"), default="")
            if proxy:
                config.tools.web.proxy = proxy

    # Step 6: Configure Web Search (optional)
    _print_step(6, total_steps, translate("cli.config.step_5_title"))

    enable_web_search = typer.confirm("\n" + translate("cli.config.enable_web_search"), default=False)

    if enable_web_search:
        console.print(translate("cli.config.brave_api_key_hint"))
        brave_api_key = _ask_text(translate("cli.config.enter_brave_api_key"), default="")
        if brave_api_key:
            config.tools.web.search.api_key = brave_api_key
        proxy = _ask_text(translate("cli.config.enter_proxy"), default="")
        if proxy:
            config.tools.web.proxy = proxy

    # Step 7: Configure MCP Servers (optional)
    _print_step(7, total_steps, translate("cli.config.step_6_title"))

    configure_mcp = typer.confirm("\n" + translate("cli.config.configure_mcp"), default=False)

    mcp_servers_config = {}
    while configure_mcp:
        console.print("\n" + translate("cli.config.mcp_server_name"))
        server_name = _ask_text(translate("cli.config.enter_mcp_server_name"), default="")
        if not server_name:
            break

        console.print(translate("cli.config.mcp_connection_type"))
        conn_type = _ask_choice(translate("cli.config.select_connection_type"), ["Stdio", "HTTP"], 0)

        if conn_type == "Stdio":
            console.print(translate("cli.config.mcp_command"))
            command = _ask_text(translate("cli.config.enter_mcp_command"), default="npx")
            console.print(translate("cli.config.mcp_args"))
            args = _ask_text(translate("cli.config.enter_mcp_args"), default="")
            mcp_servers_config[server_name] = {
                "command": command,
                "args": args.split() if args else [],
                "env": {},
                "tool_timeout": 30
            }
        else:
            console.print(translate("cli.config.mcp_url"))
            url = _ask_text(translate("cli.config.enter_mcp_url"), default="")
            mcp_servers_config[server_name] = {
                "url": url,
                "headers": {},
                "tool_timeout": 30
            }

        add_another = typer.confirm(translate("cli.config.add_another_mcp"), default=False)
        if not add_another:
            break

    if mcp_servers_config:
        from crabclaw.config.schema import MCPServerConfig
        for name, cfg in mcp_servers_config.items():
            config.tools.mcp_servers[name] = MCPServerConfig(**cfg)

    # Step 8: Configure Gateway (optional)
    _print_step(8, total_steps, translate("cli.config.step_7_title"))

    configure_gateway = typer.confirm("\n" + translate("cli.config.configure_gateway"), default=False)

    if configure_gateway:
        console.print("\n" + translate("cli.config.gateway_port_hint"))
        gateway_port = _ask_text(translate("cli.config.enter_gateway_port"), default="18790")
        if gateway_port.isdigit():
            config.gateway.port = int(gateway_port)

        enable_heartbeat = typer.confirm(translate("cli.config.enable_heartbeat"), default=True)
        if enable_heartbeat:
            heartbeat_interval = _ask_text(translate("cli.config.enter_heartbeat_interval"), default="1800")
            if heartbeat_interval.isdigit():
                config.gateway.heartbeat.interval_s = int(heartbeat_interval)

    # Step 9: Configure Dashboard (optional)
    _print_step(9, total_steps, translate("cli.config.step_8_title"))

    configure_dashboard = typer.confirm("\n" + translate("cli.config.configure_dashboard"), default=True)

    if configure_dashboard:
        console.print("\n" + translate("cli.config.dashboard_port_hint"))
        dashboard_port = _ask_text(translate("cli.config.enter_dashboard_port"), default="18791")
        if dashboard_port.isdigit():
            config.dashboard.http_port = int(dashboard_port)

    # Step 10: Configure Channels (optional)
    _print_step(10, total_steps, translate("cli.onboard.channels_step"))

    configure_channels = typer.confirm("\n" + translate("cli.onboard.configure_channels"), default=False)

    if configure_channels:
        # Telegram
        enable_telegram = typer.confirm(translate("cli.onboard.enable_telegram"), default=False)
        if enable_telegram:
            tg_token = _ask_text(translate("cli.onboard.enter_telegram_token"), default="")
            if tg_token:
                config.channels.telegram.enabled = True
                config.channels.telegram.token = tg_token

        # Discord
        enable_discord = typer.confirm(translate("cli.onboard.enable_discord"), default=False)
        if enable_discord:
            dc_token = _ask_text(translate("cli.onboard.enter_discord_token"), default="")
            if dc_token:
                config.channels.discord.enabled = True
                config.channels.discord.token = dc_token

        # Slack
        enable_slack = typer.confirm(translate("cli.onboard.enable_slack"), default=False)
        if enable_slack:
            slack_bot_token = _ask_text(translate("cli.onboard.enter_slack_bot_token"), default="")
            if slack_bot_token:
                config.channels.slack.enabled = True
                config.channels.slack.bot_token = slack_bot_token

        # WhatsApp
        enable_whatsapp = typer.confirm(translate("cli.onboard.enable_whatsapp"), default=False)
        if enable_whatsapp:
            wa_bridge_url = _ask_text(translate("cli.onboard.enter_whatsapp_bridge_url"), default="ws://localhost:3001")
            config.channels.whatsapp.enabled = True
            config.channels.whatsapp.bridge_url = wa_bridge_url

        # Feishu
        enable_feishu = typer.confirm(translate("cli.onboard.enable_feishu"), default=False)
        if enable_feishu:
            fs_app_id = _ask_text(translate("cli.onboard.enter_feishu_app_id"), default="")
            fs_app_secret = _ask_text(translate("cli.onboard.enter_feishu_app_secret"), default="")
            if fs_app_id and fs_app_secret:
                config.channels.feishu.enabled = True
                config.channels.feishu.app_id = fs_app_id
                config.channels.feishu.app_secret = fs_app_secret

        # DingTalk
        enable_dingtalk = typer.confirm(translate("cli.onboard.enable_dingtalk"), default=False)
        if enable_dingtalk:
            dt_client_id = _ask_text(translate("cli.onboard.enter_dingtalk_client_id"), default="")
            dt_client_secret = _ask_text(translate("cli.onboard.enter_dingtalk_client_secret"), default="")
            if dt_client_id and dt_client_secret:
                config.channels.dingtalk.enabled = True
                config.channels.dingtalk.client_id = dt_client_id
                config.channels.dingtalk.client_secret = dt_client_secret

        # Email
        enable_email = typer.confirm(translate("cli.onboard.enable_email"), default=False)
        if enable_email:
            imap_host = _ask_text(translate("cli.onboard.enter_imap_host"), default="")
            imap_user = _ask_text(translate("cli.onboard.enter_imap_username"), default="")
            imap_pass = _ask_password(translate("cli.onboard.enter_imap_password"))
            smtp_host = _ask_text(translate("cli.onboard.enter_smtp_host"), default="")
            if imap_host and imap_user:
                config.channels.email.enabled = True
                config.channels.email.imap_host = imap_host
                config.channels.email.imap_username = imap_user
                config.channels.email.imap_password = imap_pass
                if smtp_host:
                    config.channels.email.smtp_host = smtp_host

    # Apply all configurations to config object (in memory)
    # Use getattr to get provider config and set api key
    provider_config = getattr(config.providers, provider_key, None)
    if provider_config is None:
        from crabclaw.config.schema import ProviderConfig
        provider_config = ProviderConfig()
        setattr(config.providers, provider_key, provider_config)

    provider_config.api_key = api_key

    if base_url != provider_info['default_base_url']:
        provider_config.api_base = base_url

    # Set default model
    if not config.agents:
        from crabclaw.config.schema import AgentsConfig
        config.agents = AgentsConfig()
    if not config.agents.defaults:
        from crabclaw.config.schema import AgentDefaultsConfig
        config.agents.defaults = AgentDefaultsConfig()

    config.agents.defaults.model = selected_model
    config.agents.defaults.provider = provider_key

    if enable_exec:
        from crabclaw.config.schema import ExecToolConfig
        config.tools.exec = ExecToolConfig()
        config.tools.exec.timeout = 60
        config.tools.exec.path_append = ""
        config.tools.restrict_to_workspace = restrict_workspace

    # Final Step: Save and Initialize
    console.print(f"\n{translate('cli.onboard.final_step')}")
    console.print(f"{translate('cli.onboard.config_summary')}")
    console.print(f"  Provider: {provider_name}")
    console.print(f"  Model: {selected_model}")
    console.print(f"  Language: {selected_language}")
    console.print(f"  Exec Tool: {'Enabled' if enable_exec else 'Disabled'}")
    console.print(f"  Web Search: {'Enabled' if enable_web_search else 'Disabled'}")
    console.print(f"  MCP Servers: {len(mcp_servers_config) if mcp_servers_config else 'None'}")
    console.print(f"  Gateway: {'Enabled' if configure_gateway else 'Disabled'}")
    console.print(f"  Dashboard: {'Enabled' if configure_dashboard else 'Disabled'}")
    console.print(f"  Channels: {'Enabled' if configure_channels else 'Disabled'}")

    if typer.confirm(f"\n{translate('cli.onboard.save_confirm')}", default=True):
        # Save config to file
        save_config(config)
        console.print(f"[green]✓[/green] {translate('cli.config.config_saved', path=config_path)}")

        # Create workspace
        workspace = get_workspace_path()
        if not workspace.exists():
            workspace.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]✓[/green] {translate('cli.onboard.workspace_created', path=workspace)}")

        sync_workspace_templates(workspace)

        console.print(f"\n{translate('cli.onboard.ready', logo=__logo__)}")
        console.print(f"\n{translate('cli.onboard.next_steps')}")
        console.print(f"  1. {translate('cli.onboard.chat_command')}")
        console.print(f"  2. {translate('cli.onboard.gateway_command')}")
        if configure_dashboard:
            console.print(f"  3. {translate('cli.onboard.dashboard_command')}")
        console.print(f"\n[dim]{translate('cli.onboard.chat_apps')}[/dim]")
    else:
        console.print(translate("cli.onboard.cancelled"))


# ============================================================================
# Interactive Config Wizard
# ============================================================================

PROVIDERS_INFO = {
    "openrouter": {
        "name": "OpenRouter",
        "description": "统一的 LLM API 聚合服务，支持 Claude、GPT、DeepSeek 等",
        "default_base_url": "https://openrouter.ai/api/v1",
        "models": [
            "anthropic/claude-opus-4-5",
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-3-5-sonnet-20241022",
            "anthropic/claude-3-5-haiku-20241022",
            "anthropic/claude-3-haiku-20240307",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/gpt-4-turbo",
            "openai/gpt-3.5-turbo",
            "deepseek/deepseek-chat",
            "deepseek/deepseek-coder",
            "google/gemini-2.0-flash-exp",
            "google/gemini-1.5-pro",
            "google/gemini-1.5-flash",
            "meta-llama/llama-3.1-70b-instruct",
            "meta-llama/llama-3.1-8b-instruct",
            "meta-llama/llama-3-70b-instruct",
            "mistralai/mistral-7b-instruct",
            "mistralai/mixtral-8x7b-instruct",
            "cognitivecomputations/dolphin-mixtral-8x7b",
        ],
        "api_key_url": "https://openrouter.ai/keys",
    },
    "deepseek": {
        "name": "DeepSeek",
        "description": "深度求索官方 API，性价比高",
        "default_base_url": "https://api.deepseek.com/v1",
        "models": [
            "deepseek-chat",
            "deepseek-coder",
            "deepseek-reasoner",
        ],
        "api_key_url": "https://platform.deepseek.com/api-keys",
    },
    "openai": {
        "name": "OpenAI",
        "description": "OpenAI 官方 API（需要代理）",
        "default_base_url": "https://api.openai.com/v1",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "o1-preview",
            "o1-mini",
        ],
        "api_key_url": "https://platform.openai.com/api-keys",
    },
    "anthropic": {
        "name": "Anthropic",
        "description": "Claude 官方 API（需要代理）",
        "default_base_url": "https://api.anthropic.com/v1",
        "models": [
            "claude-opus-4-5",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-haiku-20240307",
        ],
        "api_key_url": "https://console.anthropic.com/settings/keys",
    },
    "custom": {
        "name": "自定义 / 自建服务",
        "description": "连接自定义的 OpenAI 兼容 API",
        "default_base_url": "http://localhost:8000/v1",
        "models": [
            "gpt-3.5-turbo",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
            "llama2",
            "codellama",
            "mistral",
            "mixtral",
            "qwen",
            "baichuan",
            "chatglm",
            "自定义模型名",
        ],
        "api_key_url": None,
    },
    "zhipu": {
        "name": "智谱清言",
        "description": "清华大学技术，支持中文",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": [
            "glm-4",
            "glm-4-flash",
            "glm-4-plus",
            "glm-4-air",
            "glm-4-airx",
            "glm-3-turbo",
        ],
        "api_key_url": "https://open.bigmodel.cn/usercenter/apikeys",
    },
    "dashscope": {
        "name": "阿里云 DashScope",
        "description": "阿里云百炼服务",
        "default_base_url": "https://dashscope.aliyuncs.com/api/v1",
        "models": [
            "qwen-turbo",
            "qwen-plus",
            "qwen-max",
            "qwen-max-longcontext",
            "qwen-coder-turbo",
            "qwen-coder-plus",
            "qwen-audio-turbo",
            "llama2-7b-chat",
            "llama2-13b-chat",
            "qwen1.5-72b-chat",
        ],
        "api_key_url": "https://dashscope.console.aliyun.com/",
    },
    "moonshot": {
        "name": "月之暗面 Moonshot",
        "description": "Kimi 官方 API",
        "default_base_url": "https://api.moonshot.cn/v1",
        "models": [
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
            "moonshot-v1-8k-vision-preview",
        ],
        "api_key_url": "https://platform.moonshot.cn/",
    },
}


def _print_header(title: str) -> None:
    console.print(f"\n[bold cyan]{'=' * 50}[/bold cyan]")
    console.print(f"[bold cyan]{title.center(50)}[/bold cyan]")
    console.print(f"[bold cyan]{'=' * 50}[/bold cyan]")


def _print_step(step: int, total: int, title: str) -> None:
    console.print(f"\n[bold yellow]{translate('cli.config.step_prefix', step=step, total=total)}[/bold yellow] [bold]{title}[/bold]")


def _ask_choice(prompt: str, options: list[str], default: int = 0) -> str:
    console.print(f"\n[bold]{prompt}[/bold]")
    for i, option in enumerate(options, 1):
        marker = "[green]✓[/green] " if i == default + 1 else "  "
        console.print(f"{marker}{i}. {option}")

    while True:
        try:
            choice = console.input(f"\n{translate('cli.config.enter_choice', min=1, max=len(options), default=default + 1)}").strip()
            if not choice:
                return options[default]
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
            else:
                console.print(f"[red]{translate('cli.config.invalid_choice', min=1, max=len(options))}[/red]")
        except ValueError:
            console.print("[red]" + translate("cli.config.invalid_number") + "[/red]")


def _ask_text(prompt: str, default: str = "", required: bool = False) -> str:
    while True:
        default_hint = f" [{default}]" if default else ""
        value = console.input(f"{prompt}{default_hint}: ").strip()
        if not value:
            if required:
                console.print("[red]" + translate("cli.config.required_field") + "[/red]")
                continue
            return default
        return value


def _ask_password(prompt: str) -> str:
    while True:
        value = console.input(f"{prompt}: ").strip()
        if not value:
            console.print("[red]" + translate("cli.config.api_key_required") + "[/red]")
            continue
        return value


def _print_success(msg: str) -> None:
    console.print(f"[green]✓ {msg}[/green]")


def _print_info(msg: str) -> None:
    console.print(f"[dim]{msg}[/dim]")


@onboard_app.command("config")
def onboard_config():
    """交互式配置向导 - 配置 crabclaw"""
    from crabclaw.config.loader import get_config_path, save_config
    from crabclaw.config.schema import Config
    from crabclaw.i18n.translator import get_supported_languages
    from crabclaw.utils.helpers import get_workspace_path

    config_path = get_config_path()

    if config_path.exists():
        console.print(f"[yellow]{translate('cli.config.found_config', path=config_path)}[/yellow]")
        if typer.confirm(translate("cli.config.reconfigure_confirm")):
            config = Config()
        else:
            console.print(translate("cli.config.exit_config"))
            return
    else:
        config = Config()

    # Add language selection step
    total_steps = 5

    # Step 1: Select Language
    _print_step(1, total_steps, translate("cli.config.language_step"))
    languages = get_supported_languages()
    language_display = []
    for lang in languages:
        if lang == "en":
            language_display.append("English")
        elif lang == "zh":
            language_display.append("中文")

    selected_language = _ask_choice(translate("cli.config.select_language"), language_display, 0)
    language_key = languages[language_display.index(selected_language)]
    config.language = language_key

    # Update current session language
    set_language(language_key)

    _print_success(translate("cli.config.language_selected", language=selected_language))

    _print_header(translate("cli.config.title"))
    console.print(translate("cli.config.welcome"))
    _print_info(translate("cli.config.exit_hint"))

    # Step 2: Select LLM Provider
    _print_step(2, total_steps, translate("cli.config.step_1_title"))
    console.print("\n" + translate("cli.config.select_provider"))

    provider_names = list(PROVIDERS_INFO.keys())
    provider_display = []
    for p in provider_names:
        provider_name = translate(f"providers.{p}.name")
        provider_desc = translate(f"providers.{p}.description")
        provider_display.append(f"{provider_name} - {provider_desc}")

    selected_provider = _ask_choice(translate("cli.config.select_provider").strip(), provider_display, 0)
    provider_key = provider_names[provider_display.index(selected_provider)]
    provider_info = PROVIDERS_INFO[provider_key]

    provider_name = translate(f"providers.{provider_key}.name")
    _print_success(translate("cli.config.selected_provider", provider=provider_name))

    # Step 3: Select model
    _print_step(3, total_steps, translate("cli.config.step_2_title", provider=provider_name))
    console.print("\n" + translate("cli.config.available_models", provider=provider_name) + "\n")

    models = provider_info['models']

    # If custom, let the user select or enter a custom model name
    if provider_key == "custom":
        console.print("\n" + translate("cli.config.custom_model_hint"))
        console.print(translate("cli.config.custom_model_default"))
        custom_model = _ask_text(translate("cli.config.enter_model_name"), default="gpt-3.5-turbo")
        selected_model = custom_model
    else:
        selected_model = _ask_choice(translate("cli.config.select_model"), models, 0)

    # If custom, may need to configure base_url
    base_url = provider_info['default_base_url']
    if provider_key == "custom":
        console.print("\n" + translate("cli.config.custom_api_hint"))
        custom_url = _ask_text(translate("cli.config.enter_base_url"),
                                default=base_url)
        base_url = custom_url

    _print_success(translate("cli.config.selected_model", model=selected_model))

    # Step 4: Configure API Key
    _print_step(4, total_steps, translate("cli.config.step_3_title"))

    if provider_info['api_key_url']:
        console.print("\n" + translate("cli.config.get_api_key"))
        console.print(translate("cli.config.api_key_url", url=provider_info['api_key_url']))

    api_key = _ask_password(translate("cli.config.enter_api_key"))
    _print_success(translate("cli.config.api_key_saved"))

    # Step 5: Configure tools (optional)
    _print_step(5, total_steps, translate("cli.config.step_4_title"))

    enable_exec = typer.confirm("\n" + translate("cli.config.enable_exec"), default=False)

    if enable_exec:
        restrict_workspace = typer.confirm(translate("cli.config.restrict_workspace"), default=True)

        if provider_key == "openrouter":
            # Configure proxy (optional)
            proxy = _ask_text(translate("cli.config.enter_proxy"), default="")
            if proxy:
                config.tools.web.proxy = proxy

    # Save configuration
    # Use getattr to get provider config and set API key
    provider_config = getattr(config.providers, provider_key, None)
    if provider_config is None:
        from crabclaw.config.schema import ProviderConfig
        provider_config = ProviderConfig()
        setattr(config.providers, provider_key, provider_config)

    provider_config.api_key = api_key

    if base_url != provider_info['default_base_url']:
        provider_config.api_base = base_url

    # Set default model
    if not config.agents:
        from crabclaw.config.schema import AgentsConfig
        config.agents = AgentsConfig()
    if not config.agents.defaults:
        from crabclaw.config.schema import AgentDefaultsConfig
        config.agents.defaults = AgentDefaultsConfig()

    config.agents.defaults.model = selected_model
    config.agents.defaults.provider = provider_key

    if enable_exec:
        from crabclaw.config.schema import ExecToolConfig
        config.tools.exec = ExecToolConfig()
        config.tools.exec.timeout = 60
        config.tools.exec.path_append = ""
        config.tools.restrict_to_workspace = restrict_workspace

    save_config(config)
    _print_success(translate("cli.config.config_saved", path=config_path))

    # Create workspace directory
    workspace = get_workspace_path()
    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)

    _print_header(translate("cli.config.config_completed"))
    console.print("\n" + translate("cli.config.thank_you"))
    console.print("\n" + translate("cli.config.next_steps"))
    console.print(translate("cli.config.start_chat"))
    console.print(translate("cli.config.start_gateway"))
    console.print("\n" + translate("cli.config.reconfigure_hint"))


def _make_provider(config: Config):
    """Create the appropriate LLM provider from config."""
    from crabclaw.providers.custom_provider import CustomProvider
    from crabclaw.providers.litellm_provider import LiteLLMProvider
    from crabclaw.providers.openai_codex_provider import OpenAICodexProvider

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    # OpenAI Codex (OAuth)
    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        return OpenAICodexProvider(default_model=model)

    # Custom: direct OpenAI-compatible endpoint, bypasses LiteLLM
    if provider_name == "custom":
        return CustomProvider(
            api_key=p.api_key if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
        )

    from crabclaw.providers.registry import find_by_name
    spec = find_by_name(provider_name)
    if not model.startswith("bedrock/") and not (p and p.api_key) and not (spec and spec.is_oauth):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.crabclaw/config.json under providers section")
        raise typer.Exit(1)

    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(model),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
    )


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    dashboard_http_port: int = typer.Option(None, "--dashboard-http-port", help="Dashboard HTTP port (overrides config)"),
    dashboard_ws_port: int = typer.Option(None, "--dashboard-ws-port", help="Dashboard WebSocket port (overrides config)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config: str = typer.Option(None, "--config", "-c", help="Path to config file (for multi-instance support)"),
    workspace: str = typer.Option(None, "--workspace", "-w", help="Workspace directory (overrides config)"),
):
    """Start the crabclaw gateway.
    
    Examples:
        # Start with default config (~/.crabclaw/config.json)
        crabclaw gateway
        
        # Start with custom config for multi-instance setup
        crabclaw gateway --config ~/.crabclaw-telegram/config.json
        crabclaw gateway --config ~/.crabclaw-discord/config.json
        
        # Override workspace for one-off runs
        crabclaw gateway --config ~/.crabclaw-telegram/config.json --workspace /tmp/crabclaw-telegram-test
        
        # Override ports for multi-instance setup
        crabclaw gateway --config ~/.crabclaw-2/config.json --port 18780 --dashboard-http-port 18781 --dashboard-ws-port 18782
    """
    from crabclaw.agent.scheduler import BehaviorScheduler

    # Load config with optional custom path and workspace override
    cfg = _load_runtime_config(config, workspace)
    
    # Override gateway port if provided
    if port != 18790:  # If user specified a non-default port
        # Check if the specified gateway port is available
        if not _check_port_available(port):
            console.print(f"[red]Error: Gateway port {port} is not available[/red]")
            suggested_ports = _suggest_available_ports(port, 1)
            if suggested_ports:
                console.print(f"[yellow]Suggested available ports: {suggested_ports}[/yellow]")
            raise typer.Exit(1)
        
        cfg.gateway.port = port
        
        # Auto-adjust dashboard ports to avoid conflicts
        # Dashboard ports are typically gateway_port + 1 and gateway_port + 2
        if not dashboard_http_port:
            http_port = port + 1
            # Find an available HTTP port
            while not _check_port_available(http_port) and http_port < 65536:
                http_port += 1
            if http_port >= 65536:
                console.print("[red]Error: No available dashboard HTTP port found[/red]")
                raise typer.Exit(1)
            cfg.dashboard.http_port = http_port
            console.print(f"[dim]Auto-adjusted dashboard HTTP port to {http_port}[/dim]")
        
        if not dashboard_ws_port:
            ws_port = cfg.dashboard.http_port + 1
            # Find an available WebSocket port
            while not _check_port_available(ws_port) and ws_port < 65536:
                ws_port += 1
            if ws_port >= 65536:
                console.print("[red]Error: No available dashboard WebSocket port found[/red]")
                raise typer.Exit(1)
            cfg.dashboard.ws_port = ws_port
            console.print(f"[dim]Auto-adjusted dashboard WebSocket port to {ws_port}[/dim]")
    else:
        # Use default port from config, but check if it's available
        # If not available, find an alternative port
        if not _check_port_available(cfg.gateway.port):
            console.print(f"[yellow]Warning: Gateway port {cfg.gateway.port} is not available, finding alternative...[/yellow]")
            suggested_ports = _suggest_available_ports(cfg.gateway.port, 1)
            if suggested_ports:
                cfg.gateway.port = suggested_ports[0]
                console.print(f"[dim]Using gateway port {cfg.gateway.port}[/dim]")
            else:
                console.print("[red]Error: No available gateway port found[/red]")
                raise typer.Exit(1)
        
        # Check if dashboard ports are available
        if not dashboard_http_port:
            # Dashboard HTTP port should be gateway port + 1
            http_port = cfg.gateway.port + 1
            # Find an available HTTP port
            while not _check_port_available(http_port) and http_port < 65536:
                http_port += 1
            if http_port >= 65536:
                console.print("[red]Error: No available dashboard HTTP port found[/red]")
                raise typer.Exit(1)
            if http_port != cfg.dashboard.http_port:
                console.print(f"[yellow]Warning: Dashboard HTTP port {cfg.dashboard.http_port} is not available, using alternative...[/yellow]")
                cfg.dashboard.http_port = http_port
                console.print(f"[dim]Using dashboard HTTP port {cfg.dashboard.http_port}[/dim]")
        
        if not dashboard_ws_port:
            # Dashboard WebSocket port should be gateway port + 2
            ws_port = cfg.gateway.port + 2
            # Find an available WebSocket port
            while not _check_port_available(ws_port) and ws_port < 65536:
                ws_port += 1
            if ws_port >= 65536:
                console.print("[red]Error: No available dashboard WebSocket port found[/red]")
                raise typer.Exit(1)
            if ws_port != cfg.dashboard.ws_port:
                console.print(f"[yellow]Warning: Dashboard WebSocket port {cfg.dashboard.ws_port} is not available, using alternative...[/yellow]")
                cfg.dashboard.ws_port = ws_port
                console.print(f"[dim]Using dashboard WebSocket port {cfg.dashboard.ws_port}[/dim]")
    
    # Override dashboard ports if explicitly provided
    if dashboard_http_port:
        if not _check_port_available(dashboard_http_port):
            console.print(f"[red]Error: Dashboard HTTP port {dashboard_http_port} is not available[/red]")
            suggested_ports = _suggest_available_ports(dashboard_http_port, 1)
            if suggested_ports:
                console.print(f"[yellow]Suggested available ports: {suggested_ports}[/yellow]")
            raise typer.Exit(1)
        cfg.dashboard.http_port = dashboard_http_port
    
    if dashboard_ws_port:
        if not _check_port_available(dashboard_ws_port):
            console.print(f"[red]Error: Dashboard WebSocket port {dashboard_ws_port} is not available[/red]")
            suggested_ports = _suggest_available_ports(dashboard_ws_port, 1)
            if suggested_ports:
                console.print(f"[yellow]Suggested available ports: {suggested_ports}[/yellow]")
            raise typer.Exit(1)
        cfg.dashboard.ws_port = dashboard_ws_port
    
    sync_workspace_templates(cfg.workspace_path)

    console.print(translate("cli.gateway.starting", logo=__logo__, port=cfg.gateway.port))
    console.print(f"[dim]Config: {get_config_path()}[/dim]")
    console.print(f"[dim]Data directory: {cfg.workspace_path.parent}[/dim]")
    console.print(f"[dim]Dashboard (if enabled): http://127.0.0.1:{cfg.dashboard.http_port}/[/dim]")

    # Initialize the main scheduler, which will be responsible for managing all engines
    scheduler = BehaviorScheduler(cfg)

    async def run():
        try:
            await scheduler.run()
        except (KeyboardInterrupt, asyncio.CancelledError):
            console.print("\nShutting down...")
        finally:
            await scheduler.stop()

    asyncio.run(run())


@app.command()
def dashboard(
    http_port: int = typer.Option(18791, "--http-port", help="HTTP server port"),
    ws_port: int = typer.Option(18792, "--ws-port", help="WebSocket port"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
):
    """Start the crabclaw web dashboard."""
    import asyncio

    from crabclaw.dashboard.broadcaster import DashboardBroadcaster
    from crabclaw.dashboard.server import DashboardConfig, DashboardServer

    console.print(f"{__logo__} Starting crabclaw dashboard...")

    config = load_config()

    static_dir = Path(__file__).parent.parent / "dashboard" / "static"
    if not static_dir.exists():
        console.print(f"[red]Dashboard static files not found at {static_dir}[/red]")
        raise typer.Exit(1)

    dashboard_config = DashboardConfig(
        enabled=True,
        host=host,
        http_port=http_port,
        ws_port=ws_port,
    )

    broadcaster = DashboardBroadcaster()
    server = DashboardServer(
        broadcaster,
        static_dir=static_dir,
        config=dashboard_config,
    )

    async def run_dashboard():
        try:
            await server.start()
            console.print(f"[green]✓[/green] Dashboard running at {server.http_url}")
            console.print("[dim]Press Ctrl+C to stop[/dim]")
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            await server.stop()

    try:
        asyncio.run(run_dashboard())
    except OSError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show Crabclaw runtime logs during chat"),
):
    """Interact with the agent directly."""
    from loguru import logger

    from crabclaw.agent.loop import AgentLoop
    from crabclaw.bus.queue import MessageBus
    from crabclaw.config.loader import get_data_dir, load_config
    from crabclaw.cron.service import CronService

    config = load_config()
    sync_workspace_templates(config.workspace_path)

    bus = MessageBus()
    provider = _make_provider(config)

    # Create cron service for tool usage (no callback needed for CLI unless running)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    if logs:
        logger.enable("crabclaw")
    else:
        logger.disable("crabclaw")

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        reasoning_effort=config.agents.defaults.reasoning_effort,
        brave_api_key=config.tools.web.search.api_key or None,
        web_proxy=config.tools.web.proxy or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
    )

    # Show spinner when logs are off (no output to miss); skip when logs are on
    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        # Animated spinner is safe to use with prompt_toolkit input handling
        return console.status(translate("cli.agent.thinking"), spinner="dots")

    async def _cli_progress(content: str, *, tool_hint: bool = False) -> None:
        ch = agent_loop.channels_config
        if ch and tool_hint and not ch.send_tool_hints:
            return
        if ch and not tool_hint and not ch.send_progress:
            return
        console.print(f"  [dim][OK]?{content}[/dim]")

    if message:
        # Single message mode -direct call, no bus needed
        async def run_once():
            with _thinking_ctx():
                response = await agent_loop.process_direct(message, session_id, on_progress=_cli_progress)
            if response and getattr(response, "content", None):
                _print_agent_response(response.content, render_markdown=markdown)
            await agent_loop.close_mcp()

        asyncio.run(run_once())
    else:
        # Interactive mode -route through bus like other channels
        from crabclaw.bus.events import InboundMessage
        _init_prompt_session()
        console.print(f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n")

        if ":" in session_id:
            cli_channel, cli_chat_id = session_id.split(":", 1)
        else:
            cli_channel, cli_chat_id = "cli", session_id

        def _exit_on_sigint(signum, frame):
            _restore_terminal()
            console.print("\nGoodbye!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)

        async def run_interactive():
            bus_task = asyncio.create_task(agent_loop.run())
            turn_done = asyncio.Event()
            turn_done.set()
            turn_response: list[str] = []

            async def _consume_outbound():
                while True:
                    try:
                        msg = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
                        if msg.metadata.get("_progress"):
                            is_tool_hint = msg.metadata.get("_tool_hint", False)
                            ch = agent_loop.channels_config
                            if ch and is_tool_hint and not ch.send_tool_hints:
                                pass
                            elif ch and not is_tool_hint and not ch.send_progress:
                                pass
                            else:
                                console.print(f"  [dim][OK]?{msg.content}[/dim]")
                        elif not turn_done.is_set():
                            if msg.content:
                                turn_response.append(msg.content)
                            turn_done.set()
                        elif msg.content:
                            console.print()
                            _print_agent_response(msg.content, render_markdown=markdown)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        break

            outbound_task = asyncio.create_task(_consume_outbound())

            try:
                while True:
                    try:
                        _flush_pending_tty_input()
                        user_input = await _read_interactive_input_async()
                        command = user_input.strip()
                        if not command:
                            continue

                        if _is_exit_command(command):
                            _restore_terminal()
                            console.print("\nGoodbye!")
                            break

                        turn_done.clear()
                        turn_response.clear()

                        await bus.publish_inbound(InboundMessage(
                            channel=cli_channel,
                            sender_id="user",
                            chat_id=cli_chat_id,
                            content=user_input,
                        ))

                        with _thinking_ctx():
                            await turn_done.wait()

                        if turn_response:
                            _print_agent_response(turn_response[0], render_markdown=markdown)
                    except KeyboardInterrupt:
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
                    except EOFError:
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
            finally:
                agent_loop.stop()
                outbound_task.cancel()
                await asyncio.gather(bus_task, outbound_task, return_exceptions=True)
                await agent_loop.close_mcp()

        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


# Create channels subcommand group under onboard
onboard_channels_app = typer.Typer(help="Manage channels")
onboard_app.add_typer(onboard_channels_app, name="channels")


@onboard_channels_app.command("status")
def onboard_channels_status():
    """Show channel status."""
    from crabclaw.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    dc = config.channels.discord
    table.add_row(
        "Discord",
        "✓" if dc.enabled else "✗",
        dc.gateway_url
    )

    # Feishu
    fs = config.channels.feishu
    fs_config = f"app_id: {fs.app_id[:10]}..." if fs.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "Feishu",
        "✓" if fs.enabled else "✗",
        fs_config
    )

    # Mochat
    mc = config.channels.mochat
    mc_base = mc.base_url or "[dim]not configured[/dim]"
    table.add_row(
        "Mochat",
        "✓" if mc.enabled else "✗",
        mc_base
    )

    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    # Slack
    slack = config.channels.slack
    slack_config = "socket" if slack.app_token and slack.bot_token else "[dim]not configured[/dim]"
    table.add_row(
        "Slack",
        "✓" if slack.enabled else "✗",
        slack_config
    )

    # DingTalk
    dt = config.channels.dingtalk
    dt_config = f"client_id: {dt.client_id[:10]}..." if dt.client_id else "[dim]not configured[/dim]"
    table.add_row(
        "DingTalk",
        "✓" if dt.enabled else "✗",
        dt_config
    )

    # QQ
    qq = config.channels.qq
    qq_config = f"app_id: {qq.app_id[:10]}..." if qq.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "QQ",
        "✓" if qq.enabled else "✗",
        qq_config
    )

    # Email
    em = config.channels.email
    em_config = em.imap_host if em.imap_host else "[dim]not configured[/dim]"
    table.add_row(
        "Email",
        "✓" if em.enabled else "✗",
        em_config
    )

    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess

    # User's bridge location
    user_bridge = Path.home() / ".crabclaw" / "bridge"

    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge

    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)

    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # crabclaw/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)

    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge

    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall crabclaw-ai")
        raise typer.Exit(1)

    console.print(f"{__logo__} Setting up bridge...")

    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))

    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)

        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)

        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)

    return user_bridge


@onboard_channels_app.command("login")
def onboard_channels_login():
    """Link device via QR code."""
    import subprocess

    from crabclaw.config.loader import load_config

    config = load_config()
    bridge_dir = _get_bridge_dir()

    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")

    env = {**os.environ}
    if config.channels.whatsapp.bridge_token:
        env["BRIDGE_TOKEN"] = config.channels.whatsapp.bridge_token

    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True, env=env)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show crabclaw status."""
    import socket

    import psutil

    from crabclaw.config.loader import get_config_path, load_config

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(translate("cli.status.title", logo=__logo__))

    console.print(translate("cli.status.config", path=config_path, status="[green]✓[/green]" if config_path.exists() else "[red]✗[/red]"))
    console.print(translate("cli.status.workspace", path=workspace, status="[green]✓[/green]" if workspace.exists() else "[red]✗[/red]"))

    # Check running services
    console.print("\n[bold]Services Status:[/bold]")

    # Check gateway service
    gateway_running = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex(("127.0.0.1", config.gateway.port))
        gateway_running = result == 0
        sock.close()
    except:
        pass

    console.print(
        f"Gateway: {'[green]✓ Running[/green]' if gateway_running else '[dim]Not running[/dim]'} (port {config.gateway.port})"
    )

    # Check dashboard service
    dashboard_running = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex(("127.0.0.1", config.dashboard.http_port))
        dashboard_running = result == 0
        sock.close()
    except:
        pass

    console.print(
        f"Dashboard: {'[green]✓ Running[/green]' if dashboard_running else '[dim]Not running[/dim]'} (port {config.dashboard.http_port})"
    )

    # Check WebSocket service
    ws_running = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex(("127.0.0.1", config.dashboard.ws_port))
        ws_running = result == 0
        sock.close()
    except:
        pass

    console.print(
        f"WebSocket: {'[green]✓ Running[/green]' if ws_running else '[dim]Not running[/dim]'} (port {config.dashboard.ws_port})"
    )

    # Check crabclaw processes
    console.print("\n[bold]Processes:[/bold]")
    crabclaw_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'crabclaw' in ' '.join(proc.cmdline()):
                crabclaw_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if crabclaw_processes:
        for proc in crabclaw_processes:
            console.print(f"PID {proc.pid}: {' '.join(proc.cmdline())}")
    else:
        console.print("[dim]No crabclaw processes running[/dim]")

    if config_path.exists():
        from crabclaw.providers.registry import PROVIDERS

        console.print(f"\nModel: {config.agents.defaults.model}")

        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_oauth:
                console.print(f"{spec.label}: [green][OK]?(OAuth)[/green]")
            elif spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green][OK]?{p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(f"{spec.label}: {'[green]✓[/green]' if has_key else '[dim]not set[/dim]'}")


# ============================================================================
# OAuth Login
# ============================================================================

# Create provider subcommand group under onboard
onboard_provider_app = typer.Typer(help="Manage providers")
onboard_app.add_typer(onboard_provider_app, name="provider")


_LOGIN_HANDLERS: dict[str, callable] = {}


def _register_login(name: str):
    def decorator(fn):
        _LOGIN_HANDLERS[name] = fn
        return fn
    return decorator


@onboard_provider_app.command("login")
def provider_login(
    provider: str = typer.Argument(..., help="OAuth provider (e.g. 'openai-codex', 'github-copilot')"),
):
    """Authenticate with an OAuth provider."""
    from crabclaw.providers.registry import PROVIDERS

    key = provider.replace("-", "_")
    spec = next((s for s in PROVIDERS if s.name == key and s.is_oauth), None)
    if not spec:
        names = ", ".join(s.name.replace("_", "-") for s in PROVIDERS if s.is_oauth)
        console.print(f"[red]Unknown OAuth provider: {provider}[/red]  Supported: {names}")
        raise typer.Exit(1)

    handler = _LOGIN_HANDLERS.get(spec.name)
    if not handler:
        console.print(f"[red]Login not implemented for {spec.label}[/red]")
        raise typer.Exit(1)

    console.print(f"{__logo__} OAuth Login - {spec.label}\n")
    handler()


@_register_login("openai_codex")
def _login_openai_codex() -> None:
    try:
        from oauth_cli_kit import get_token, login_oauth_interactive
        token = None
        try:
            token = get_token()
        except Exception:
            pass
        if not (token and token.access):
            console.print("[cyan]Starting interactive OAuth login...[/cyan]\n")
            token = login_oauth_interactive(
                print_fn=lambda s: console.print(s),
                prompt_fn=lambda s: typer.prompt(s),
            )
        if not (token and token.access):
            console.print("[red][OK]?Authentication failed[/red]")
            raise typer.Exit(1)
        console.print(f"[green][OK]?Authenticated with OpenAI Codex[/green]  [dim]{token.account_id}[/dim]")
    except ImportError:
        console.print("[red]oauth_cli_kit not installed. Run: pip install oauth-cli-kit[/red]")
        raise typer.Exit(1)


@_register_login("github_copilot")
def _login_github_copilot() -> None:
    import asyncio

    console.print("[cyan]Starting GitHub Copilot device flow...[/cyan]\n")

    async def _trigger():
        from litellm import acompletion
        await acompletion(model="github_copilot/gpt-4o", messages=[{"role": "user", "content": "hi"}], max_tokens=1)

    try:
        asyncio.run(_trigger())
        console.print("[green][OK]?Authenticated with GitHub Copilot[/green]")
    except Exception as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
