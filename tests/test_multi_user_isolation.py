from pathlib import Path

from crabclaw.agent.loop import IOProcessor
from crabclaw.agent.memory import MemoryStore
from crabclaw.bus.broadcaster import BroadcastManager
from crabclaw.bus.events import InboundMessage
from crabclaw.bus.queue import MessageBus
from crabclaw.dashboard.server import DashboardServer
from crabclaw.gateway.server import GatewayServer, GatewayServerConfig
from crabclaw.session.manager import SessionManager
from crabclaw.user.manager import UserManager


def test_user_manager_bootstrap_admin_portfolio(tmp_path):
    workspace = Path(tmp_path)
    manager = UserManager(workspace)
    admin = manager.get_user_by_username("admin")
    assert admin is not None
    assert admin.is_admin is True
    portfolio = manager.get_portfolio_dir(admin.user_id)
    assert portfolio.exists()
    assert (portfolio / "portfolio.json").exists()
    assert (portfolio / "memory").exists()
    assert (portfolio / "history").exists()
    assert (portfolio / "channels" / "email").exists()
    assert (portfolio / "channels" / "feishu").exists()


def test_delete_user_removes_portfolio(tmp_path):
    workspace = Path(tmp_path)
    manager = UserManager(workspace)
    user = manager.create_user("alice", "Alice", "pw123456")
    portfolio = manager.get_portfolio_dir(user.user_id)
    assert portfolio.exists()
    assert manager.delete_user(user.user_id) is True
    assert not portfolio.exists()


def test_session_and_memory_are_isolated_per_user(tmp_path):
    workspace = Path(tmp_path)
    sessions = SessionManager(workspace)
    memory = MemoryStore(workspace)

    s1 = sessions.get_or_create("dashboard", user_scope="user-zhang")
    s1.add_message("user", "hello from zhang")
    sessions.save(s1)

    s2 = sessions.get_or_create("dashboard", user_scope="user-li")
    s2.add_message("user", "hello from li")
    sessions.save(s2)

    loaded_zhang = sessions.get_or_create("dashboard", user_scope="user-zhang")
    loaded_li = sessions.get_or_create("dashboard", user_scope="user-li")
    assert loaded_zhang.messages[-1]["content"] == "hello from zhang"
    assert loaded_li.messages[-1]["content"] == "hello from li"

    memory.write_long_term("zhang-memory", user_scope="user-zhang")
    memory.write_long_term("li-memory", user_scope="user-li")
    assert memory.read_long_term(user_scope="user-zhang") == "zhang-memory"
    assert memory.read_long_term(user_scope="user-li") == "li-memory"


def test_channel_configs_are_isolated_in_portfolio(tmp_path):
    workspace = Path(tmp_path)
    manager = UserManager(workspace)
    u1 = manager.create_user("zhang", "Zhang", "pw123456")
    u2 = manager.create_user("li", "Li", "pw123456")

    saved1 = manager.save_channel_config(
        user_id=u1.user_id,
        channel_type="email",
        name="work-email",
        config={"imap_host": "imap.a.com", "imap_username": "a@a.com"},
    )
    saved2 = manager.save_channel_config(
        user_id=u2.user_id,
        channel_type="email",
        name="private-email",
        config={"imap_host": "imap.b.com", "imap_username": "b@b.com"},
    )

    assert saved1 is not None
    assert saved2 is not None
    cfg1 = manager.list_channel_configs(u1.user_id).get("email", [])
    cfg2 = manager.list_channel_configs(u2.user_id).get("email", [])
    assert len(cfg1) == 1
    assert len(cfg2) == 1
    assert cfg1[0]["name"] == "work-email"
    assert cfg2[0]["name"] == "private-email"


def test_identity_mapping_is_user_scoped(tmp_path):
    workspace = Path(tmp_path)
    manager = UserManager(workspace)
    u1 = manager.create_user("zhang", "Zhang", "pw123456")
    u2 = manager.create_user("li", "Li", "pw123456")

    m1 = manager.map_identity(
        user_id=u1.user_id,
        channel="feishu",
        external_id="ou_zhang",
        alias="zhang-feishu",
    )
    m2 = manager.map_identity(
        user_id=u2.user_id,
        channel="email",
        external_id="li@example.com",
        alias="li-email",
    )

    assert m1 is not None
    assert m2 is not None
    assert manager.resolve_user_by_identity("feishu", "ou_zhang") == u1.user_id
    assert manager.resolve_user_by_identity("email", "li@example.com") == u2.user_id

    user1_maps = manager.list_identity_mappings(u1.user_id)
    assert len(user1_maps) == 1
    assert user1_maps[0]["external_id"] == "ou_zhang"


def test_gateway_resolves_user_scope_from_identity(tmp_path):
    workspace = Path(tmp_path)
    manager = UserManager(workspace)
    user = manager.create_user("scope_user", "Scope User", "pw123456")
    manager.map_identity(
        user_id=user.user_id,
        channel="cli",
        external_id="cli_sender_001",
        alias="cli-binding",
    )

    gateway = GatewayServer(
        GatewayServerConfig(),
        bus=MessageBus(),
        broadcast_manager=BroadcastManager(),
        workspace=workspace,
    )
    scope = gateway._resolve_user_scope(
        {
            "channel": "cli",
            "sender_id": "cli_sender_001",
            "chat_id": "direct",
        }
    )
    assert scope == user.user_id


def test_dashboard_channel_catalog_contains_parameter_metadata(tmp_path):
    workspace = Path(tmp_path)
    static_dir = workspace / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    server = DashboardServer(
        BroadcastManager(),
        static_dir=static_dir,
        workspace=workspace,
    )
    channels = server._get_channel_catalog()
    assert isinstance(channels, list)
    assert len(channels) > 0
    first = channels[0]
    assert "name" in first
    assert "parameters" in first
    if first["parameters"]:
        _, p_meta = next(iter(first["parameters"].items()))
        assert "type" in p_meta
        assert "required" in p_meta
        assert "default" in p_meta
        assert "description" in p_meta


class _DummySapiens:
    id = "dummy-sapiens"
    sociology = None


def test_io_processor_echo_guard_and_fanout_skip_origin(tmp_path):
    workspace = Path(tmp_path)
    manager = UserManager(workspace)
    user = manager.create_user("fanout_user", "Fanout User", "pw123456")
    manager.map_identity(user.user_id, "cli", "direct", alias="origin")
    manager.map_identity(user.user_id, "email", "fanout@example.com", alias="secondary")

    io = IOProcessor(MessageBus(), _DummySapiens(), BroadcastManager())
    io._user_manager = manager
    io._scope_origin[user.user_id] = ("cli", "direct", "origin_sender", 0.0)

    io._remember_outbound("cli", "direct", "reply-text")
    echo_msg = InboundMessage(
        channel="cli",
        sender_id="bot-self",
        chat_id="direct",
        content="reply-text",
    )
    assert io._is_inbound_echo(echo_msg) is True

    targets = io._collect_outbound_targets(
        reply_scope=user.user_id,
        recipient="",
        source_channel="",
        source_chat_id="",
    )
    assert ("email", "fanout@example.com") in targets
    assert ("cli", "direct") not in targets
