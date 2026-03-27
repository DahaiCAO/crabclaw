# 测试飞书消息处理

import asyncio
from crabclaw.channels.feishu import FeishuChannel
from crabclaw.bus.queue import MessageBus
from crabclaw.config.schema import FeishuConfig

# 模拟消息数据
class MockEvent:
    def __init__(self):
        self.message = MockMessage()
        self.sender = MockSender()

class MockMessage:
    def __init__(self):
        self.message_id = "test_message_id"
        self.content = '{"text": "test message"}'
        self.chat_type = "p2p"
        self.message_type = "text"
        self.chat_id = "test_chat_id"
        self.parent_id = None
        self.root_id = None

class MockSender:
    def __init__(self):
        self.sender_type = "user"
        self.sender_id = MockSenderID()

class MockSenderID:
    def __init__(self):
        self.open_id = "test_open_id"

# 创建配置 - 注意 allow_from 为空列表
config = FeishuConfig(
    enabled=True,
    app_id="test_app_id",
    app_secret="test_app_secret",
    allow_from=[],  # 空列表会拒绝所有访问
    group_policy="open"
)

# 创建消息总线
bus = MessageBus()

# 创建 Feishu 通道
channel = FeishuChannel(config, bus)

# 模拟事件数据
data = MockEvent()

# 测试 is_allowed 方法
print(f"Is allowed (empty allow_from): {channel.is_allowed('test_open_id')}")

# 修改配置为允许所有人
config.allow_from = ["*"]
print(f"Is allowed (allow all): {channel.is_allowed('test_open_id')}")

# 修改配置为允许特定用户
config.allow_from = ["test_open_id"]
print(f"Is allowed (specific user): {channel.is_allowed('test_open_id')}")
print(f"Is allowed (other user): {channel.is_allowed('other_open_id')}")